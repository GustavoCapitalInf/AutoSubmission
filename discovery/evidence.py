"""Reading a discovery run back as evidence, hash-keyed and masked.

Both W3-4 commands (`discovery.adjudicate`, `discovery.compare`) read finished
run directories rather than re-running anything, so adjudication and
coverage-movement reporting cost nothing and can be redone at any time over
the frozen artifacts.

**Identity is `content_sha256`, everywhere.** That is what makes two runs
comparable without caring about ordering, run ids, timings, record ids or
which tranche mode produced them - and it is the same identity telemetry
already uses.

**Sensitivity.** The telemetry JSONL is non-sensitive by construction
(H3_SCHEMA I1) and is the primary source. `rows.csv` is the runner's
human-facing artifact and DOES carry relative paths, the extracted bank label
and a masked account fragment; this module reads exactly three of its columns
- `content_sha256`, `folder_label`, `dedup_status` - and nothing here ever
returns a path, a filename, an extracted bank label or an account fragment.
Folder labels are analyst-assigned bank names, already published in
`DISCOVERY_COMBINED_REPORT.md`; paths are not, because customer names live in
them.

**The cache-hit hole, and why the join exists.** H3_SCHEMA §5.4 declared it:
on a D-3 analysis cache hit `analyze_markdown` never runs, so the record
carried `dispatch.source = "cached"/"unavailable"` and no `parser_id`. It was
never benign for coverage - the rate collapsed to 0.0% on a fully warm run -
and it was fatal for W3-4, because "failure class x parser" needs the parser.
Measured on the archive runs:

    ec400125 (tranche 1, first pass)  608 withheld, 608 with a parser_id, 0 diagnosed
    02e90a86 (the W3-2 baseline)      614 withheld,   0 with a parser_id, 614 diagnosed

So the baseline cannot answer its own question alone. `parser_index` fixes it
by joining a companion run on the content hash: the parser claim is a property
of the document and the registry, not of the run that happened to observe it,
so recovering it from another run over the same bytes is sound - and it is
recorded in the output as an enrichment, never silently merged.

**Closed at the source since #TELCOV, and the join is KEPT for the runs that
predate it.** A cache-served record now carries the reconstructed claim
(`telemetry.record.dispatch_section`), so a run emitted today answers its own
class x parser question warm or cold, and `--enrich` is not part of reading it.
It is not dead code: measured over the 43 retained run directories, **11 hold
records with a published outcome and no verdict** - among them the W3-2
baseline `02e90a86` (614 diagnosed, 0 attributed) and the warm archive re-run
`b7b40c73` (2,561) - and those are the frozen evidence W3-2/W3-4 are pointed
at. Retiring the join would make the archive's own history unreadable except
through `--allow-unattributed`, which throws the attribution away rather than
recovering it. So it stays, documented as a BRIDGE FOR PRE-#TELCOV RUNS rather
than as part of the design, and it disappears on its own as those runs age out.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

# The run report's own word for a claim that names no issuer. Imported, never
# restated: one vocabulary across the two artifacts a run produces.
from .report import TEMPLATE_CLAIM

AGREE = "agree"
LABEL_UNMATCHED = "label_unmatched"

TELEMETRY_FILE = "telemetry.jsonl"
ROWS_FILE = "rows.csv"
SUMMARY_FILE = "summary.json"

#: The only `rows.csv` columns that may cross into a W3-4 artifact.
ADMISSIBLE_ROW_COLUMNS = ("content_sha256", "folder_label", "dedup_status")

#: One more column is READ, and its value never crosses (#TELCOV).
#: `statement_bank` is the label the parser extracted from the document and is
#: inadmissible in an artifact for exactly the reason H3_SCHEMA I1 gives; what
#: crosses is one boolean derived from it — whether the claim named an issuer
#: at all — which is a fact about OUR claim, not a fact read out of the paper.
#: The alternative sources were surveyed and rejected: the telemetry record
#: cannot carry the label (I1) and does not carry `model_used`, and sniffing
#: the registration name for "Template"/"Platform" is the name-based rule
#: §DISCOBS DO4 declined to write. DO7#4's registry-side "this label is not an
#: issuer claim" flag is a change to `analysis/parser_registry.py` and is not
#: this cell's to make - and it would NOT simply replace this read: measured on
#: the run of record, `community_section` publishes an issuer on 55 documents
#: and none on 5, so a per-REGISTRATION exemption would also silence 13 live,
#: checkable disagreements that this per-DOCUMENT fact keeps (W3 §TELCOV TC3.1).
DERIVED_ROW_COLUMNS = ("statement_bank",)

#: Folder labels that are not bank labels: a human sorted these as "I could not
#: sort these". They are the generic-understanding test set, not a bank.
UNLABELLED_FOLDERS = frozenset({"misc", "others", "unidentified", "(root)", "root"})


@dataclass(frozen=True)
class Document:
    """One document in one run, masked. No path, no name, no bank label."""

    content_sha256: str
    outcome_class: str
    outcome_reason: str
    dispatch_outcome: str | None
    dispatch_source: str
    parser_id: str | None
    parser_enriched_from: str | None       # run id a joined parser_id came from
    near_miss: tuple[str, ...]
    exceptions: tuple[tuple[str, str, str], ...]
    classification: str
    page_count: int
    byte_size: int
    valid_pdf: bool
    encrypted: bool
    malformed_page_count: int
    source_path: str
    truncated_page_count: int
    diagnostics: dict
    folder_label: str | None = None
    dedup_status: str | None = None
    #: Did the claiming parser publish an issuer for this document? `None` when
    #: the run has no `rows.csv` to answer from. The LABEL is never held here
    #: (see DERIVED_ROW_COLUMNS); this is one bit about our own claim.
    claim_names_issuer: bool | None = None

    @property
    def primary_class(self) -> str | None:
        return self.diagnostics.get("primary_class") if self.diagnostics.get("evaluated") else None

    @property
    def is_unlabelled_folder(self) -> bool:
        return (self.folder_label or "").strip().lower() in UNLABELLED_FOLDERS

    @property
    def is_template_claim(self) -> bool:
        """The claim names no issuer, so no folder label can agree with it.

        The §U honest-unknown-issuer registrations claim a document TEMPLATE
        and publish `Statement.bank = None` on purpose, because the paper names
        no institution. Their registry id and registry bank label are both
        template names, so `registration_labels()` offers a folder matcher two
        template strings to compare against a bank name — a category error,
        which the label check filed as a disagreement (§DISCOBS DO7#3: six
        `Desjardins -> releve_facturation` documents on the run of record).

        The rule is a FACT about the claim, not a name test, and it is the same
        rule `discovery.report.folder_agreement` uses for its `template_claim`
        bucket — deliberately, so the workspace and the run report cannot
        disagree about which documents are template claims. That is the same
        argument `bank_is_registered` makes for sharing the report's matcher.

        Fails CLOSED on `None`: a document whose claim we cannot ask about is
        not exempted from the label check. It cannot arise in practice — the
        folder label the check needs comes from the same file and the same row
        — and a test pins that.
        """
        return self.claim_names_issuer is False


@dataclass
class Run:
    run_id: str
    directory: Path
    documents: dict[str, Document] = field(default_factory=dict)
    enrichment_runs: tuple[str, ...] = ()
    folder_labels_available: bool = False
    #: Telemetry records read. Larger than `len(self)` when the archive holds
    #: the same bytes under more than one path - documents are keyed by content
    #: hash, so duplicates collapse into one, and the difference is reported
    #: rather than left as an unexplained shortfall against the run summary.
    records: int = 0

    def __len__(self) -> int:
        return len(self.documents)

    def values(self):
        return self.documents.values()


def read_telemetry(directory: Path) -> list[dict]:
    path = Path(directory) / TELEMETRY_FILE
    if not path.is_file():
        raise FileNotFoundError(f"no {TELEMETRY_FILE} in {directory}")
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def read_folder_labels(directory: Path) -> dict[str, tuple[str, str, bool]]:
    """sha -> (folder_label, dedup_status, claim_names_issuer).

    The first two are `ADMISSIBLE_ROW_COLUMNS` and are published as they stand.
    The third is derived from `statement_bank` and the label itself stops here
    — see `DERIVED_ROW_COLUMNS` for why that column is read and why nothing
    else could answer the question.

    Absent `rows.csv` is not an error: the telemetry alone is enough for every
    parser- and check-keyed cluster, and only the folder-keyed ones thin out.
    """
    path = Path(directory) / ROWS_FILE
    if not path.is_file():
        return {}
    labels: dict[str, tuple[str, str, bool]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip()
            if sha:
                labels[sha] = (
                    (row.get("folder_label") or "").strip(),
                    (row.get("dedup_status") or "").strip(),
                    bool((row.get("statement_bank") or "").strip()),
                )
    return labels


def parser_index(directories: list[Path]) -> dict[str, tuple[str, str, str]]:
    """sha -> (parser_id, dispatch_outcome, run_id) from a run that dispatched it.

    The bridge for runs emitted before #TELCOV closed the hole at the source;
    see the module docstring for why it is kept and what it is measured to be
    needed for.

    First writer wins, so passing the earliest live run first makes that run
    the authority. Only records with a real parser id are indexed: a record
    with no claim has nothing to contribute and must not overwrite a real one.
    Since #TELCOV a cache-served record usually HAS one, which is a
    reconstruction rather than an observation - and admissible here for
    exactly the reason this join is admissible at all: the parser claim is a
    property of the document and the registry, not of the observation.

    The dispatch OUTCOME travels with the parser id deliberately. Recovering
    `parser_id` without it leaves the document looking like it never
    dispatched, and every cluster keyed on "was this claimed" - misfiled
    labels, claims in unlabelled folders - then silently fails to form. Both
    facts have the same provenance and the same justification, so they move
    together.
    """
    index: dict[str, tuple[str, str, str]] = {}
    for directory in directories:
        for record in read_telemetry(directory):
            dispatch = record.get("dispatch") or {}
            parser = dispatch.get("parser_id")
            sha = ((record.get("document") or {}).get("content_sha256") or "")
            if parser and sha and sha not in index:
                index[sha] = (
                    parser,
                    dispatch.get("outcome") or "claimed",
                    record.get("run_id") or str(directory),
                )
    return index


def load_run(
    directory: str | Path,
    *,
    enrich_parsers_from: list[str | Path] | None = None,
    with_folder_labels: bool = True,
) -> Run:
    """One run directory, as masked hash-keyed evidence."""
    directory = Path(directory)
    records = read_telemetry(directory)
    labels = read_folder_labels(directory) if with_folder_labels else {}
    enrich_dirs = [Path(item) for item in (enrich_parsers_from or [])]
    enrichment = parser_index(enrich_dirs) if enrich_dirs else {}

    documents: dict[str, Document] = {}
    enriched_from: set[str] = set()
    for record in records:
        document = record.get("document") or {}
        sha = document.get("content_sha256") or ""
        if not sha:
            continue
        dispatch = record.get("dispatch") or {}
        source = record.get("source") or {}
        outcome = record.get("outcome") or {}
        parser = dispatch.get("parser_id")
        dispatch_outcome = dispatch.get("outcome")
        enriched: str | None = None
        if not parser and sha in enrichment:
            parser, enriched_outcome, enriched = enrichment[sha]
            dispatch_outcome = dispatch_outcome or enriched_outcome
            enriched_from.add(enriched)
        folder, dedup, names_issuer = labels.get(sha, (None, None, None))
        documents[sha] = Document(
            content_sha256=sha,
            outcome_class=outcome.get("class") or "unknown",
            outcome_reason=outcome.get("reason") or "",
            dispatch_outcome=dispatch_outcome,
            dispatch_source=dispatch.get("source") or "unavailable",
            parser_id=parser,
            parser_enriched_from=enriched,
            near_miss=tuple(
                name for name, score in (dispatch.get("scores") or []) if score < 0.5
            ),
            exceptions=tuple(
                tuple(entry) for entry in (dispatch.get("exceptions") or [])
                if isinstance(entry, list) and len(entry) == 3
            ),
            classification=document.get("classification") or "unknown",
            page_count=document.get("page_count") or 0,
            byte_size=document.get("byte_size") or 0,
            valid_pdf=bool(document.get("valid_pdf")),
            encrypted=bool(document.get("encrypted")),
            malformed_page_count=document.get("malformed_page_count") or 0,
            source_path=source.get("path") or "none",
            truncated_page_count=(source.get("truncation") or {}).get(
                "truncated_page_count"
            ) or 0,
            diagnostics=record.get("diagnostics") or {},
            folder_label=folder,
            dedup_status=dedup,
            claim_names_issuer=names_issuer,
        )

    run_id = records[0].get("run_id") if records else directory.name
    return Run(
        run_id=run_id or directory.name,
        directory=directory,
        documents=documents,
        enrichment_runs=tuple(sorted(enriched_from)),
        folder_labels_available=bool(labels),
        records=len(records),
    )


def normalise_label(label: str) -> str:
    """Same normalisation `discovery.report.folder_agreement` uses."""
    return "".join(character for character in (label or "").lower() if character.isalnum())


def registered_bank_tokens() -> frozenset[str]:
    """Normalised tokens for every bank the registry has a parser for.

    Read from the live registry rather than listed here, so "do we already have
    a parser for this bank" cannot drift and no bank name becomes a constant in
    this file (the R-1 rule).
    """
    from analysis import parser_registry_entries  # noqa: F401  (populates)
    from analysis.parser_registry import registrations

    tokens: set[str] = set()
    for registration in registrations():
        for raw in (registration.id, registration.bank):
            token = normalise_label(raw or "")
            if token:
                tokens.add(token)
    return frozenset(tokens)


def registration_labels() -> dict[str, frozenset[str]]:
    """parser id -> the normalised labels that parser legitimately answers to.

    Its registry id AND its registered bank name. Both are OUR constants, so
    using them is admissible where `Statement.bank` (read out of the document,
    and forbidden by H3_SCHEMA I1) is not.

    This is what stops the label check from manufacturing findings. `td_us` is
    registered as "TD Bank", so a document a human filed under `TD Bank/` and
    `td_us` claimed is in the RIGHT folder - matching the id alone would call
    28 correctly-parsed statements misfiled, which is precisely the failure
    `discovery.report.folder_agreement`'s docstring warns about.

    WHAT IT CANNOT ANSWER, and where that is handled. For a §U registration
    both strings are template names, so this returns two labels that no bank
    folder can legitimately match. That is not a wrong answer here - the
    registration really does answer to those names - it is a question that
    should not have been asked, and `label_verdict` is what declines to ask it.
    """
    from analysis import parser_registry_entries  # noqa: F401  (populates)
    from analysis.parser_registry import registrations

    return {
        registration.id: frozenset(
            token for token in (
                normalise_label(registration.id),
                normalise_label(registration.bank or ""),
            ) if token
        )
        for registration in registrations()
    }


def label_agrees(folder_label: str, labels: frozenset[str]) -> bool:
    """Containment in either direction against any admissible label."""
    folder = normalise_label(folder_label)
    if not folder or not labels:
        return False
    return any(token in folder or folder in token for token in labels)


def label_verdict(document: Document, labels: frozenset[str]) -> str:
    """Does this claim agree with the folder, disagree, or answer a different
    question entirely? One of `AGREE` / `TEMPLATE_CLAIM` / `LABEL_UNMATCHED`.

    The vocabulary and the ORDER are `discovery.report.folder_agreement`'s, and
    `TEMPLATE_CLAIM` is imported from it rather than restated, so the run
    report and the adjudication workspace cannot describe the same document
    two ways. Order is load-bearing there and here: a template name that
    happened to be contained in a folder name would otherwise be reported as
    agreement, manufacturing a detection-accuracy datum out of a coincidence.

    The caller decides what an unmatched label MEANS - `label_unmatched` is not
    "disagree", and on the pinned corpus every one of them is an abbreviation
    the matcher cannot see through (`Amex` vs `american_express`). This
    function only refuses to file a category error among them.
    """
    if document.is_template_claim:
        return TEMPLATE_CLAIM
    return AGREE if label_agrees(document.folder_label or "", labels) else LABEL_UNMATCHED


def bank_is_registered(folder_label: str, tokens: frozenset[str]) -> bool:
    """Containment in either direction, matching `folder_agreement`'s matcher.

    Deliberately the same (deliberately imperfect) matcher: it is the reference
    the discovery report already uses, and an adjudication tool that disagreed
    with the report about which banks we support would be worse than one that
    is wrong in the same direction as the thing it is adjudicating.
    """
    folder = normalise_label(folder_label)
    if not folder:
        return False
    return any(token in folder or folder in token for token in tokens)
