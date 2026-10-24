//! Stored merchant applications: the sealed source PDF, each parse of it, and the revisions people
//! make. A revision selects one parse and holds one override per field (`record::RevisionState`),
//! so every current value derives from what is stored.

pub mod evaluate;
mod seal;

use std::fmt;
use std::path::PathBuf;
use std::sync::{Arc, Mutex, PoisonError};
use std::time::Duration;

use lender_matching_application::extract::{self, Document, ManualEntryReason, Reading, RefusalReason};
use lender_matching_application::fields::{BusinessField, FieldId, PropertyField};
use lender_matching_application::pdf::PageImage;
use lender_matching_application::values::{Country, Currency, Denomination, Entity, StatedDate, YesNo};
use lender_matching_application::worker::{PdfWorker, WorkerError};
use lender_matching_application::{
    FieldValue, PARSER_VERSION, PDFIUM_BUILD, PdfFacts, Record, Resolved, RevisionState, YearMonth,
};
use sha2::{Digest, Sha256};
use time::{Date, OffsetDateTime};
use uuid::Uuid;

use crate::facts::Interval;
use crate::facts::application::{ApplicationFacts, EntityKind};
use crate::store::applications::{NewApplication, NewRevision, ParseRow, RevisionRow, UploadRow};
use crate::store::{ReadTx, Store, StoreError, WriteTx, now};
use seal::{Binding, SealError};
pub use seal::{DataKey, KEY_VARIABLE};

/// The JSON layout of `application_parses.payload`; a bump leaves older parses unreadable without
/// a reader.
pub const PARSE_FORMAT: u32 = 1;
/// The JSON layout of `application_revisions.state`; a bump leaves older revisions unreadable
/// without a reader.
pub const STATE_FORMAT: u32 = 1;
/// The source PDF and a reason are stored as they are.
const BYTES_FORMAT: u32 = 1;

/// A document taking longer than this stops the worker and counts as a timeout.
pub const DOCUMENT_TIMEOUT: Duration = Duration::from_secs(60);

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct ApplicationId(pub Uuid);

impl fmt::Display for ApplicationId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct ParseId(pub Uuid);

/// One revision of one application.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ApplicationRef {
    pub id: ApplicationId,
    pub revision: u32,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum RevisionKind {
    Upload,
    Edit(Cause),
    AdoptParse,
    ConfirmApplication,
}

/// Why a person corrected a field.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Cause {
    /// The parser misread the PDF.
    Reading,
    /// The PDF shows what the merchant typed, and it is wrong.
    Merchant,
}

impl RevisionKind {
    /// The `kind` and `cause` columns.
    pub fn keys(self) -> (&'static str, Option<&'static str>) {
        match self {
            RevisionKind::Upload => ("upload", None),
            RevisionKind::Edit(Cause::Reading) => ("edit", Some("reading")),
            RevisionKind::Edit(Cause::Merchant) => ("edit", Some("merchant")),
            RevisionKind::AdoptParse => ("adopt_parse", None),
            RevisionKind::ConfirmApplication => ("confirm_application", None),
        }
    }

    pub fn from_keys(kind: &str, cause: Option<&str>) -> Option<RevisionKind> {
        Some(match (kind, cause) {
            ("upload", None) => RevisionKind::Upload,
            ("edit", Some("reading")) => RevisionKind::Edit(Cause::Reading),
            ("edit", Some("merchant")) => RevisionKind::Edit(Cause::Merchant),
            ("adopt_parse", None) => RevisionKind::AdoptParse,
            ("confirm_application", None) => RevisionKind::ConfirmApplication,
            _ => return None,
        })
    }
}

/// Names the parser and the pdfium build, so a parse is stored once per parser.
pub fn parser_fingerprint() -> [u8; 32] {
    Sha256::digest(format!("lender_matching_application {PARSER_VERSION} with pdfium {PDFIUM_BUILD}")).into()
}

/// The width of a page image beside the form, in pixels.
pub const PAGE_IMAGE_WIDTH: u32 = 1100;

/// Turns PDF bytes into page data and page images.
pub trait ReadPdf: Send + Sync {
    fn facts(&self, pdf: &[u8]) -> Result<PdfFacts, WorkerError>;
    fn page_png(&self, pdf: &[u8], image: &PageImage) -> Result<Vec<u8>, WorkerError>;
}

/// Reads PDFs in one pdfium worker process, started on first use. The worker's environment holds
/// only `PDFIUM_LIBRARY`, so it gets neither the data key nor the database path.
pub struct WorkerReader {
    program: PathBuf,
    library: Option<PathBuf>,
    worker: Mutex<Option<PdfWorker>>,
}

impl WorkerReader {
    /// Without `library`, every read is `NoEngine`.
    pub fn new(library: Option<PathBuf>) -> Result<WorkerReader, String> {
        let program = std::env::current_exe().map_err(|error| error.to_string())?;
        Ok(WorkerReader { program, library, worker: Mutex::new(None) })
    }
}

impl WorkerReader {
    fn with<T>(&self, ask: impl FnOnce(&mut PdfWorker) -> Result<T, WorkerError>) -> Result<T, WorkerError> {
        let library = self.library.as_deref().ok_or(WorkerError::NoEngine)?;
        let mut worker = self.worker.lock().unwrap_or_else(PoisonError::into_inner);
        let worker = match &mut *worker {
            Some(worker) => worker,
            empty => empty.insert(PdfWorker::start(&self.program, &["pdf-worker"], library)?),
        };
        ask(worker)
    }
}

impl ReadPdf for WorkerReader {
    fn facts(&self, pdf: &[u8]) -> Result<PdfFacts, WorkerError> {
        self.with(|worker| worker.facts(pdf, DOCUMENT_TIMEOUT))
    }

    fn page_png(&self, pdf: &[u8], image: &PageImage) -> Result<Vec<u8>, WorkerError> {
        self.with(|worker| worker.page_png(pdf, image, DOCUMENT_TIMEOUT))
    }
}

/// What `Applications::upload` did with a PDF.
pub enum Intake {
    /// A new application at revision 1. `manual_entry` says why a person types it in;
    /// `same_envelope` names the first application stored from the same DocuSign envelope.
    Stored { reference: ApplicationRef, manual_entry: Option<ManualEntryReason>, same_envelope: Option<ApplicationId> },
    /// These bytes are stored already; this is their current revision.
    AlreadyStored(ApplicationRef),
    /// Not an application: nothing was stored.
    Refused(RefusalReason),
}

/// A stored parse. It holds application data, so it has no `Debug`.
#[cfg_attr(not(test), expect(dead_code))]
pub struct StoredParse {
    pub id: ParseId,
    pub parser_version: u32,
    pub created_at: OffsetDateTime,
    pub reading: Reading,
}

/// A revision's metadata and state. It holds application data, so it has no `Debug`.
#[cfg_attr(not(test), expect(dead_code))]
pub struct Revision {
    pub reference: ApplicationRef,
    pub saved_at: OffsetDateTime,
    pub author: String,
    pub kind: RevisionKind,
    pub reason: Option<String>,
    pub parse: ParseId,
    pub state: RevisionState,
}

/// A revision with the parse it selects.
pub struct Snapshot {
    pub revision: Revision,
    pub parse: StoredParse,
}

impl Snapshot {
    pub fn record(&self) -> Record<'_> {
        Record { reading: &self.parse.reading, state: &self.revision.state }
    }
}

/// Who stored an application and when. It holds no application data.
pub struct Upload {
    pub id: ApplicationId,
    pub at: OffsetDateTime,
    pub by: String,
}

impl From<UploadRow> for Upload {
    fn from(row: UploadRow) -> Self {
        Upload { id: row.id, at: row.uploaded_at, by: row.uploaded_by }
    }
}

/// Which page image to draw.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Cover {
    /// The SSNs and dates of birth painted over.
    Identity,
    /// Nothing painted over, for a person who asked to see the page.
    Nothing,
}

/// A logged look at an application's identity data.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Access {
    /// The page with SSNs, dates of birth and page 1 uncovered.
    Reveal,
}

impl Access {
    pub fn key(self) -> &'static str {
        match self {
            Access::Reveal => "reveal",
        }
    }
}

pub enum Saved {
    New(Snapshot),
    /// The change gave the current state, so nothing was written.
    Unchanged(Snapshot),
}

pub enum ApplicationError {
    NotFound,
    /// Another revision was saved first; `head` is the current one.
    Conflict {
        head: Box<Snapshot>,
    },
    /// The parse reads the document as something other than an application.
    NotAnApplication,
    Pdf(WorkerError),
    /// The parse holds a value that would not read back as stored.
    Unstorable,
    Store(StoreError),
}

impl From<StoreError> for ApplicationError {
    fn from(error: StoreError) -> Self {
        ApplicationError::Store(error)
    }
}

impl fmt::Display for ApplicationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ApplicationError::NotFound => f.write_str("no such application or parse"),
            ApplicationError::Conflict { head } => {
                write!(f, "another revision was saved first: revision {}", head.revision.reference.revision)
            }
            ApplicationError::NotAnApplication => {
                f.write_str("that parse does not read the document as an application")
            }
            ApplicationError::Pdf(error) => write!(f, "the PDF could not be read: {}", worker_error(*error)),
            ApplicationError::Unstorable => f.write_str("the parse could not be stored as read"),
            ApplicationError::Store(error) => error.fmt(f),
        }
    }
}

impl fmt::Debug for ApplicationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}

impl std::error::Error for ApplicationError {}

fn worker_error(error: WorkerError) -> &'static str {
    use lender_matching_application::pdf::ReadError;
    match error {
        WorkerError::Read(ReadError::NotPdf) => "not_pdf",
        WorkerError::Read(ReadError::Encrypted) => "encrypted",
        WorkerError::Read(ReadError::TooLarge) => "too_large",
        WorkerError::Read(ReadError::Engine) => "engine_error",
        WorkerError::Read(ReadError::NoSuchPage) => "no_such_page",
        WorkerError::Timeout => "timeout",
        WorkerError::Crashed => "worker_crashed",
        WorkerError::NoEngine => "no_engine",
    }
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

/// Each sealed column, by the row of the application its value belongs to.
#[derive(Clone, Copy)]
enum Sealed {
    SourcePdf,
    Parse(ParseId),
    State(u32),
    Reason(u32),
}

impl Sealed {
    fn binding(self, application: ApplicationId) -> Binding {
        let (column, row, format) = match self {
            Sealed::SourcePdf => ("applications.source_pdf", String::new(), BYTES_FORMAT),
            Sealed::Parse(id) => ("application_parses.payload", id.0.to_string(), PARSE_FORMAT),
            Sealed::State(revision) => ("application_revisions.state", revision.to_string(), STATE_FORMAT),
            Sealed::Reason(revision) => ("application_revisions.reason", revision.to_string(), BYTES_FORMAT),
        };
        Binding { column, application: application.0, row, format }
    }

    fn seal(self, key: &DataKey, application: ApplicationId, plaintext: &[u8]) -> Vec<u8> {
        key.seal(&self.binding(application), plaintext)
    }

    fn open(self, key: &DataKey, application: ApplicationId, envelope: &[u8]) -> Result<Vec<u8>, StoreError> {
        let binding = self.binding(application);
        key.open(&binding, envelope).map_err(|error| match error {
            SealError::OtherKey => StoreError::Corrupt(format!("{} is sealed with another key", binding.column)),
            SealError::Broken => StoreError::Corrupt(format!("{} does not open", binding.column)),
        })
    }
}

/// The sealed JSON of a reading, refused when it would not read back.
fn seal_parse(
    key: &DataKey,
    application: ApplicationId,
    parse: ParseId,
    reading: &Reading,
) -> Result<Vec<u8>, ApplicationError> {
    let json = serde_json::to_vec(reading).map_err(|_| ApplicationError::Unstorable)?;
    serde_json::from_slice::<Reading>(&json).map_err(|_| ApplicationError::Unstorable)?;
    Ok(Sealed::Parse(parse).seal(key, application, &json))
}

fn open_parse(key: &DataKey, row: ParseRow) -> Result<StoredParse, StoreError> {
    if row.format != PARSE_FORMAT {
        return Err(StoreError::Corrupt(format!("a parse has format {}, unreadable by this build", row.format)));
    }
    let json = Sealed::Parse(row.id).open(key, row.application, &row.payload)?;
    let reading =
        serde_json::from_slice(&json).map_err(|_| StoreError::Corrupt("a parse does not decode".to_string()))?;
    Ok(StoredParse { id: row.id, parser_version: row.parser_version, created_at: row.created_at, reading })
}

fn open_revision(key: &DataKey, row: RevisionRow) -> Result<Revision, StoreError> {
    if row.format != STATE_FORMAT {
        return Err(StoreError::Corrupt(format!("a revision has format {}, unreadable by this build", row.format)));
    }
    let json = Sealed::State(row.revision).open(key, row.application, &row.state)?;
    let state =
        serde_json::from_slice(&json).map_err(|_| StoreError::Corrupt("a revision does not decode".to_string()))?;
    let reason = row
        .reason
        .map(|sealed| {
            let bytes = Sealed::Reason(row.revision).open(key, row.application, &sealed)?;
            String::from_utf8(bytes).map_err(|_| StoreError::Corrupt("a reason does not decode".to_string()))
        })
        .transpose()?;
    Ok(Revision {
        reference: ApplicationRef { id: row.application, revision: row.revision },
        saved_at: row.saved_at,
        author: row.author_name,
        kind: row.kind,
        reason,
        parse: row.selected_parse,
        state,
    })
}

fn snapshot(tx: &ReadTx, key: &DataKey, row: RevisionRow) -> Result<Snapshot, StoreError> {
    let revision = open_revision(key, row)?;
    let parse = tx
        .application_parse(revision.reference.id, revision.parse)?
        .ok_or_else(|| StoreError::Corrupt("a revision's parse is missing".to_string()))?;
    Ok(Snapshot { parse: open_parse(key, parse)?, revision })
}

/// The application's current revision.
pub fn current_in(tx: &ReadTx, key: &DataKey, id: ApplicationId) -> Result<Option<Snapshot>, StoreError> {
    tx.application_head(id)?.map(|row| snapshot(tx, key, row)).transpose()
}

/// What matching reads from an application: its state, start month, entity, estimated FICO,
/// requested amount and history answers. The requested amount counts only for a business in a US
/// jurisdiction, above 0 and not marked CAD. It suggests no industry, which needs a person's
/// confirmation.
pub fn matching_facts(resolved: &Resolved, as_of: Date) -> ApplicationFacts {
    let business = |field| resolved.value(FieldId::Business(field));
    let property = |field| resolved.value(FieldId::Property(field));
    let state = match business(BusinessField::State) {
        Some(FieldValue::Jurisdiction(code)) => Some(*code),
        _ => None,
    };
    let start = match business(BusinessField::StartDate) {
        Some(FieldValue::StatedDate(StatedDate::Day(day))) => Some(YearMonth::of(*day)),
        Some(FieldValue::StatedDate(StatedDate::Month(month))) => Some(*month),
        _ => None,
    };
    let entity = match business(BusinessField::Entity) {
        Some(FieldValue::Entity(entity)) => Some(match entity {
            Entity::Llc => EntityKind::Llc,
            Entity::Corporation | Entity::SCorporation | Entity::CCorporation => EntityKind::Corporation,
            Entity::SoleProprietorship => EntityKind::SoleProprietorship,
            Entity::Partnership => EntityKind::Partnership,
            Entity::NonProfit => EntityKind::NonProfit,
        }),
        _ => None,
    };
    let fico = match property(PropertyField::EstimatedFico) {
        Some(FieldValue::Score(score)) => Interval::between(score.min().into(), score.max().into()),
        _ => None,
    };
    let in_us = state.is_some_and(|code| code.country() == Country::UnitedStates);
    let requested = match property(PropertyField::RequestedAmount) {
        Some(FieldValue::Money(amount))
            if in_us && amount.cents() > 0 && amount.denomination() != Denomination::Explicit(Currency::Cad) =>
        {
            Some(amount.cents())
        }
        _ => None,
    };
    let answer = |field| match property(field) {
        Some(FieldValue::YesNo(YesNo::Yes)) => Some(true),
        Some(FieldValue::YesNo(YesNo::No)) => Some(false),
        _ => None,
    };
    ApplicationFacts {
        business_state: state,
        business_start: start.filter(|month| *month <= YearMonth::of(as_of)),
        entity,
        estimated_fico: fico,
        requested_amount_cents: requested,
        open_judgements: answer(PropertyField::OpenJudgements),
        bankruptcy: answer(PropertyField::Bankruptcy),
        tax_liens: answer(PropertyField::TaxLiens),
        industry_suggestion: None,
    }
}

/// Refuses a key that did not seal the applications already stored.
pub fn check_key(store: &Store, key: &DataKey) -> Result<(), String> {
    let sample = store.read(|tx| tx.some_application_state()).map_err(|error| error.to_string())?;
    match sample {
        Some(envelope) if !key.sealed(&envelope) => {
            Err(format!("{KEY_VARIABLE} is not the key that sealed the stored applications"))
        }
        _ => Ok(()),
    }
}

/// Uploads, reparses and corrections. Every method blocks: it reads PDFs through the worker and
/// writes SQLite.
pub struct Applications {
    store: Arc<Store>,
    key: Arc<DataKey>,
    reader: Arc<dyn ReadPdf>,
    /// `parser_fingerprint()`, which a test replaces to stand for an older parser.
    parser: [u8; 32],
}

impl Applications {
    pub fn new(store: Arc<Store>, key: Arc<DataKey>, reader: Arc<dyn ReadPdf>) -> Applications {
        Applications { store, key, reader, parser: parser_fingerprint() }
    }

    /// Identical bytes give the stored application. The PDF is read outside any transaction; a
    /// refused document stores nothing; otherwise one transaction stores the sealed PDF, its
    /// parse and revision 1.
    pub fn upload(&self, pdf: &[u8], by: i64) -> Result<Intake, ApplicationError> {
        let source_sha256 = sha256(pdf);
        if let Some(stored) = self.store.read(|tx| head_ref(tx, &source_sha256))? {
            return Ok(Intake::AlreadyStored(stored));
        }
        let facts = self.reader.facts(pdf).map_err(ApplicationError::Pdf)?;
        let reading = extract::read(&facts);
        let manual_entry = match reading.document {
            Document::Refused(reason) => return Ok(Intake::Refused(reason)),
            Document::ManualEntry(reason) => Some(reason),
            Document::Application(_) => None,
        };
        let state = RevisionState::initial(&reading.document).expect("only a refused document has no state");
        let envelope_id_sha256 = reading
            .certificate
            .as_ref()
            .and_then(|certificate| certificate.envelope.as_ref())
            .map(|envelope| sha256(envelope.as_str().as_bytes()));
        let id = ApplicationId(Uuid::new_v4());
        let parse = ParseId(Uuid::new_v4());
        let payload = seal_parse(&self.key, id, parse, &reading)?;
        let source_pdf = Sealed::SourcePdf.seal(&self.key, id, pdf);
        let sealed_state = self.seal_state(id, 1, &state);
        self.store.write(|tx| {
            if let Some(stored) = head_ref(tx, &source_sha256)? {
                return Ok(Intake::AlreadyStored(stored));
            }
            let same_envelope =
                envelope_id_sha256.map(|digest| tx.application_by_envelope(&digest)).transpose()?.flatten();
            tx.insert_application(&NewApplication {
                id,
                source_sha256,
                envelope_id_sha256,
                uploaded_by: by,
                source_pdf: &source_pdf,
            })?;
            tx.insert_application_parse(&ParseRow {
                id: parse,
                application: id,
                parser_version: PARSER_VERSION,
                parser_fingerprint: self.parser,
                created_at: now(),
                format: PARSE_FORMAT,
                payload,
            })?;
            tx.insert_application_revision(&NewRevision {
                application: id,
                revision: 1,
                selected_parse: parse,
                author: by,
                kind: RevisionKind::Upload,
                format: STATE_FORMAT,
                state: &sealed_state,
                reason: None,
            })?;
            Ok(Intake::Stored { reference: ApplicationRef { id, revision: 1 }, manual_entry, same_envelope })
        })
    }

    fn seal_state(&self, application: ApplicationId, revision: u32, state: &RevisionState) -> Vec<u8> {
        let json = serde_json::to_vec(state).expect("a revision state serializes");
        Sealed::State(revision).seal(&self.key, application, &json)
    }

    pub fn current(&self, id: ApplicationId) -> Result<Snapshot, ApplicationError> {
        self.store.read(|tx| current_in(tx, &self.key, id))?.ok_or(ApplicationError::NotFound)
    }

    /// The revision `at`, with the parse it selects.
    pub fn at(&self, at: ApplicationRef) -> Result<Snapshot, ApplicationError> {
        let found =
            self.store.read(|tx| tx.application_revision(at)?.map(|row| snapshot(tx, &self.key, row)).transpose())?;
        found.ok_or(ApplicationError::NotFound)
    }

    /// Every application with its current revision, the latest upload first.
    pub fn list(&self) -> Result<Vec<(Upload, Snapshot)>, ApplicationError> {
        Ok(self.store.read(|tx| {
            let uploads = tx.application_uploads()?;
            uploads
                .into_iter()
                .map(|upload| {
                    let head = current_in(tx, &self.key, upload.id)?
                        .ok_or_else(|| StoreError::Corrupt("an application without a revision".to_string()))?;
                    Ok((Upload::from(upload), head))
                })
                .collect::<Result<Vec<_>, StoreError>>()
        })?)
    }

    /// Who stored the application and when, and the first application stored before it from the
    /// same DocuSign envelope.
    pub fn upload_of(&self, id: ApplicationId) -> Result<(Upload, Option<ApplicationId>), ApplicationError> {
        let (upload, earlier) = self.store.read(|tx| Ok((tx.application_upload(id)?, tx.earlier_of_envelope(id)?)))?;
        Ok((upload.ok_or(ApplicationError::NotFound)?.into(), earlier))
    }

    /// Page 1 of the source PDF. With `Cover::Identity`, None when the selected parse locates no
    /// region for some SSN or date of birth, so no covered image can be made.
    pub fn page_image(&self, snapshot: &Snapshot, cover: Cover) -> Result<Option<Vec<u8>>, ApplicationError> {
        let covers = match cover {
            Cover::Identity => match snapshot.parse.reading.masked_covers() {
                Some(covers) => covers,
                None => return Ok(None),
            },
            Cover::Nothing => Vec::new(),
        };
        let id = snapshot.revision.reference.id;
        let source = self.store.read(|tx| tx.application_source(id))?.ok_or(ApplicationError::NotFound)?;
        let pdf = Sealed::SourcePdf.open(&self.key, id, &source)?;
        let image = PageImage { page: 0, width: PAGE_IMAGE_WIDTH, covers };
        self.reader.page_png(&pdf, &image).map(Some).map_err(ApplicationError::Pdf)
    }

    /// Records that `by` looked at the application's identity data.
    pub fn log_access(&self, id: ApplicationId, by: i64, access: Access) -> Result<(), ApplicationError> {
        Ok(self.store.write(|tx| tx.insert_application_access(id, by, access.key()))?)
    }

    /// Every revision, oldest first.
    #[cfg_attr(not(test), expect(dead_code))]
    pub fn history(&self, id: ApplicationId) -> Result<Vec<Revision>, ApplicationError> {
        let rows = self.store.read(|tx| tx.application_revisions(id))?;
        if rows.is_empty() {
            return Err(ApplicationError::NotFound);
        }
        Ok(rows.into_iter().map(|row| open_revision(&self.key, row)).collect::<Result<_, _>>()?)
    }

    #[cfg_attr(not(test), expect(dead_code))]
    pub fn parse(&self, id: ApplicationId, parse: ParseId) -> Result<StoredParse, ApplicationError> {
        let row = self.store.read(|tx| tx.application_parse(id, parse))?.ok_or(ApplicationError::NotFound)?;
        Ok(open_parse(&self.key, row)?)
    }

    /// Stores a parse by the current parser without selecting it, once per parser fingerprint: a
    /// repeat gives the stored one without reading the PDF.
    #[cfg_attr(not(test), expect(dead_code))]
    pub fn reparse(&self, id: ApplicationId) -> Result<ParseId, ApplicationError> {
        let fingerprint = self.parser;
        let (stored, source) = self
            .store
            .read(|tx| Ok((tx.application_parse_by_fingerprint(id, &fingerprint)?, tx.application_source(id)?)))?;
        let source = source.ok_or(ApplicationError::NotFound)?;
        if let Some(stored) = stored {
            return Ok(stored.id);
        }
        let pdf = Sealed::SourcePdf.open(&self.key, id, &source)?;
        let reading = extract::read(&self.reader.facts(&pdf).map_err(ApplicationError::Pdf)?);
        let parse = ParseId(Uuid::new_v4());
        let payload = seal_parse(&self.key, id, parse, &reading)?;
        self.store.write(|tx| {
            if let Some(stored) = tx.application_parse_by_fingerprint(id, &fingerprint)? {
                return Ok(stored.id);
            }
            tx.insert_application_parse(&ParseRow {
                id: parse,
                application: id,
                parser_version: PARSER_VERSION,
                parser_fingerprint: fingerprint,
                created_at: now(),
                format: PARSE_FORMAT,
                payload,
            })?;
            Ok(parse)
        })
    }

    /// A new revision that selects `parse` and keeps every override. A parse that reads the
    /// document as not an application is refused.
    #[cfg_attr(not(test), expect(dead_code))]
    pub fn adopt_parse(&self, base: ApplicationRef, parse: ParseId, by: i64) -> Result<Saved, ApplicationError> {
        self.save(base, by, RevisionKind::AdoptParse, None, |tx, head| {
            let row = tx.application_parse(base.id, parse)?.ok_or(ApplicationError::NotFound)?;
            let candidate = open_parse(&self.key, row)?;
            let state =
                head.revision.state.adopting(&candidate.reading.document).ok_or(ApplicationError::NotAnApplication)?;
            Ok((parse, state))
        })
    }

    /// A new revision with `edits` applied, recording why. Read the edits from the revision shown
    /// with `lender_matching_application::Edits::read`.
    pub fn correct(
        &self,
        base: ApplicationRef,
        edits: &lender_matching_application::Edits,
        cause: Cause,
        reason: Option<&str>,
        by: i64,
    ) -> Result<Saved, ApplicationError> {
        self.save(base, by, RevisionKind::Edit(cause), reason, |_, head| {
            Ok((head.revision.parse, head.revision.state.edited(edits)))
        })
    }

    /// Confirms that a manual-entry draft is an application.
    pub fn confirm_application(&self, base: ApplicationRef, by: i64) -> Result<Saved, ApplicationError> {
        self.save(base, by, RevisionKind::ConfirmApplication, None, |_, head| {
            Ok((head.revision.parse, head.revision.state.confirmed()))
        })
    }

    /// Applies `change` to the current revision. A result equal to it writes nothing, whatever
    /// `base` is, so a repeated submission is a no-op; otherwise a stale `base` is a conflict.
    fn save(
        &self,
        base: ApplicationRef,
        by: i64,
        kind: RevisionKind,
        reason: Option<&str>,
        change: impl FnOnce(&WriteTx, &Snapshot) -> Result<(ParseId, RevisionState), ApplicationError>,
    ) -> Result<Saved, ApplicationError> {
        let reason = reason.map(str::trim).filter(|reason| !reason.is_empty());
        self.store.write(|tx| {
            let head = current_in(tx, &self.key, base.id)?.ok_or(ApplicationError::NotFound)?;
            let (parse, state) = change(tx, &head)?;
            if parse == head.revision.parse && state == head.revision.state {
                return Ok(Saved::Unchanged(head));
            }
            if head.revision.reference != base {
                return Err(ApplicationError::Conflict { head: Box::new(head) });
            }
            let revision = base.revision + 1;
            let sealed_state = self.seal_state(base.id, revision, &state);
            let sealed_reason =
                reason.map(|reason| Sealed::Reason(revision).seal(&self.key, base.id, reason.as_bytes()));
            tx.insert_application_revision(&NewRevision {
                application: base.id,
                revision,
                selected_parse: parse,
                author: by,
                kind,
                format: STATE_FORMAT,
                state: &sealed_state,
                reason: sealed_reason.as_deref(),
            })?;
            Ok(Saved::New(current_in(tx, &self.key, base.id)?.ok_or(ApplicationError::NotFound)?))
        })
    }
}

fn head_ref(tx: &ReadTx, source_sha256: &[u8; 32]) -> Result<Option<ApplicationRef>, StoreError> {
    let Some(id) = tx.application_by_source(source_sha256)? else { return Ok(None) };
    let head =
        tx.application_head(id)?.ok_or_else(|| StoreError::Corrupt("an application without a revision".to_string()))?;
    Ok(Some(ApplicationRef { id, revision: head.revision }))
}

#[cfg(test)]
pub(crate) mod testing;

#[cfg(test)]
mod tests;
