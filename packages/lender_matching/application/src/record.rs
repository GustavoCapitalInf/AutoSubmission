//! An application revision is a selected parse plus one override per field and an admission
//! state. Every current value derives from those, so a reparse cannot replace what a person set.

use std::fmt;

use serde::{Deserialize, Serialize};
use time::Date;

use crate::extract::{Document, Doubt, FieldReading, Reading, RegionValue, Unlocated};
use crate::fields::{BusinessField, FieldId, FieldMap, OwnerField, OwnerSlot, Required};
use crate::values::{Answer, FieldValue, Percent, RawText, ReadContext, Refusal};

/// What a revision says about one field. It holds a value, so `Debug` names the variant only.
#[derive(Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Override {
    /// The selected parse's reading.
    Inherit,
    Set(FieldValue),
    Empty(EmptyReason),
}

impl fmt::Debug for Override {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Override::Inherit => f.write_str("Override::Inherit"),
            Override::Set(_) => f.write_str("Override::Set(..)"),
            Override::Empty(why) => write!(f, "Override::Empty({why:?})"),
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EmptyReason {
    Cleared,
    /// A person typed N/A: the merchant answered that nothing applies.
    NotApplicable,
    RemovedOwner,
}

/// Whether the document is an application.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Admission {
    /// The selected parse read the form.
    Recognized,
    /// A manual-entry draft: a scan or an unknown layout, which a person has not confirmed.
    AwaitingConfirmation,
    /// A person confirmed that the document is an application.
    Confirmed,
    /// Sampled for a blind audit, whatever the parse reads it as: nothing but the audit changes it.
    AwaitingAudit,
    /// The audit found that the document is not an application.
    NotAnApplication,
}

impl Admission {
    /// None for a refused document, which an upload does not store.
    pub fn of(document: &Document) -> Option<Admission> {
        match document {
            Document::Application(_) => Some(Admission::Recognized),
            Document::ManualEntry(_) => Some(Admission::AwaitingConfirmation),
            Document::Refused(_) => None,
        }
    }

    pub fn admits_matching(self) -> bool {
        matches!(self, Admission::Recognized | Admission::Confirmed)
    }
}

/// What a revision stores besides the parse it selects.
#[derive(Clone, PartialEq, Serialize, Deserialize)]
pub struct RevisionState {
    pub overrides: FieldMap<Override>,
    pub admission: Admission,
}

impl RevisionState {
    /// Every field inherits. None for a refused document.
    pub fn initial(document: &Document) -> Option<RevisionState> {
        Some(RevisionState { overrides: FieldMap::from_fn(|_| Override::Inherit), admission: Admission::of(document)? })
    }

    pub fn edited(&self, edits: &Edits) -> RevisionState {
        let mut next = self.clone();
        for (field, edit) in edits.0.iter() {
            if let Some(edit) = edit {
                *next.overrides.get_mut(field) = edit.clone();
            }
        }
        next
    }

    /// Revision 1 of a document sampled for a blind audit, refused ones included.
    pub fn awaiting_audit() -> RevisionState {
        RevisionState { overrides: FieldMap::from_fn(|_| Override::Inherit), admission: Admission::AwaitingAudit }
    }

    /// The state with `document` selected instead: every override kept, and the admission it
    /// reads as unless a person or an audit settled it. None for a refused document.
    pub fn adopting(&self, document: &Document) -> Option<RevisionState> {
        let admission = match (self.admission, Admission::of(document)?) {
            (settled @ (Admission::Confirmed | Admission::AwaitingAudit | Admission::NotAnApplication), _) => settled,
            (_, read) => read,
        };
        Some(RevisionState { overrides: self.overrides.clone(), admission })
    }

    /// A blind audit's result: what the auditor typed, and whether the document is an application.
    pub fn audited(&self, edits: &Edits, application: bool) -> RevisionState {
        let mut next = self.edited(edits);
        next.admission = if application { Admission::Confirmed } else { Admission::NotAnApplication };
        next
    }

    /// A manual-entry draft confirmed as an application; any other state is unchanged.
    pub fn confirmed(&self) -> RevisionState {
        let admission = match self.admission {
            Admission::AwaitingConfirmation => Admission::Confirmed,
            other => other,
        };
        RevisionState { overrides: self.overrides.clone(), admission }
    }
}

/// A field's current value. It holds a value, so it has no `Debug`.
pub enum Current {
    Value {
        value: FieldValue,
        origin: Origin,
    },
    /// Nothing: blank or N/A on the page, nothing read, emptied by a person, or a derived field
    /// with no owner.
    Empty {
        origin: Origin,
    },
    /// The parse gave no value for text that may be there; `FieldState::attention` says why.
    NeedsReview,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Origin {
    /// The selected parse's reading.
    Parse,
    /// The revision's override.
    Person,
    /// The number of owners.
    Derived,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Attention {
    RequiredEmpty,
    /// The parse refused the field's text.
    Refused(Refusal),
    /// The parse did not locate the field's label.
    Unlocated(Unlocated),
    /// The parse could not tell whose text lies in the field.
    Doubtful(Doubt),
}

pub struct FieldState {
    pub current: Current,
    /// In this order: the parse's issue, then `RequiredEmpty`.
    pub attention: Vec<Attention>,
}

impl FieldState {
    pub fn value(&self) -> Option<&FieldValue> {
        match &self.current {
            Current::Value { value, .. } => Some(value),
            Current::Empty { .. } | Current::NeedsReview => None,
        }
    }
}

/// Every field's current value and what needs a person's attention.
pub struct Resolved(FieldMap<FieldState>);

const SECONDARY_NAME: FieldId = FieldId::Owner(OwnerSlot::Secondary, OwnerField::Name);
const STATE: FieldId = FieldId::Business(BusinessField::State);

impl Resolved {
    pub fn get(&self, field: FieldId) -> &FieldState {
        self.0.get(field)
    }

    pub fn value(&self, field: FieldId) -> Option<&FieldValue> {
        self.0.get(field).value()
    }

    pub fn iter(&self) -> impl Iterator<Item = (FieldId, &FieldState)> {
        self.0.iter()
    }

    pub fn has_second_owner(&self) -> bool {
        self.value(SECONDARY_NAME).is_some()
    }
}

/// One revision: the parse it selects and its state.
#[derive(Clone, Copy)]
pub struct Record<'a> {
    pub reading: &'a Reading,
    pub state: &'a RevisionState,
}

impl Record<'_> {
    /// `Set` gives the person's value, `Empty` nothing, and `Inherit` the parse's reading. A
    /// derived field ignores both: one owner holds 100%, two owners 50% each.
    pub fn resolve(&self) -> Resolved {
        let mut fields = FieldMap::from_fn(|field| match self.state.overrides.get(field) {
            _ if field.spec().derived => {
                FieldState { current: Current::Empty { origin: Origin::Derived }, attention: vec![] }
            }
            Override::Set(value) => FieldState {
                current: Current::Value { value: value.clone(), origin: Origin::Person },
                attention: vec![],
            },
            Override::Empty(_) => FieldState { current: Current::Empty { origin: Origin::Person }, attention: vec![] },
            Override::Inherit => inherited(self.parsed(field)),
        });
        let shares = match fields.get(SECONDARY_NAME).value() {
            Some(_) => [Some(Percent::HALF), Some(Percent::HALF)],
            None => [Some(Percent::WHOLE), None],
        };
        for (slot, share) in [OwnerSlot::Principal, OwnerSlot::Secondary].into_iter().zip(shares) {
            fields.get_mut(FieldId::Owner(slot, OwnerField::OwnershipPercent)).current = match share {
                Some(share) => Current::Value { value: FieldValue::Percent(share), origin: Origin::Derived },
                None => Current::Empty { origin: Origin::Derived },
            };
        }
        let missing: Vec<FieldId> = FieldId::ALL
            .into_iter()
            .filter(|field| {
                let required = match field.spec().required {
                    Required::Always => true,
                    Required::Never => false,
                    Required::IfFilled(other) => fields.get(other).value().is_some(),
                };
                required && fields.get(*field).value().is_none()
            })
            .collect();
        for field in missing {
            fields.get_mut(field).attention.push(Attention::RequiredEmpty);
        }
        Resolved(fields)
    }

    /// How a person's text for a field reads: against the parse's signing day, else `today`, and
    /// the business's country now.
    pub fn read_context(&self, today: Date) -> ReadContext {
        let country = self.resolve().value(STATE).and_then(country_of);
        ReadContext {
            signed_on: Some(self.reading.signed_on.map_or(today, |signed| signed.date())),
            business_country: country,
        }
    }

    fn parsed(&self, field: FieldId) -> Option<&FieldReading> {
        match &self.reading.document {
            Document::Application(form) => Some(form.fields.get(field)),
            Document::ManualEntry(_) | Document::Refused(_) => None,
        }
    }
}

fn country_of(value: &FieldValue) -> Option<crate::values::Country> {
    match value {
        FieldValue::Jurisdiction(code) => Some(code.country()),
        _ => None,
    }
}

fn inherited(reading: Option<&FieldReading>) -> FieldState {
    let review = |issue| FieldState { current: Current::NeedsReview, attention: vec![issue] };
    let empty = FieldState { current: Current::Empty { origin: Origin::Parse }, attention: vec![] };
    match reading {
        None => empty,
        Some(FieldReading::Unlocated(why)) => review(Attention::Unlocated(*why)),
        Some(FieldReading::Located { value, .. }) => match value {
            RegionValue::Blank | RegionValue::NotApplicable(_) => empty,
            RegionValue::Read(value, _) => FieldState {
                current: Current::Value { value: value.clone(), origin: Origin::Parse },
                attention: vec![],
            },
            RegionValue::Refused(why, _) => review(Attention::Refused(*why)),
            RegionValue::Doubtful(doubt, _) => review(Attention::Doubtful(*doubt)),
        },
    }
}

/// What a person submits for one field.
pub enum EditInput<'a> {
    /// Read by the field's grammar: a value sets it, N/A empties it as not applicable.
    Text(&'a str),
    Clear,
    /// Back to the parse's reading.
    UseParse,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum EditRefusal {
    /// A derived field or a signature date.
    NotEditable,
    /// The field appears twice in one submission.
    Repeated,
    Value(Refusal),
}

/// Overrides to apply, at most one per field. Each holds a value, so there is no `Debug`.
pub struct Edits(FieldMap<Option<Override>>);

impl Edits {
    /// Reads every input, or refuses with each refused field. `business.state` is read first, so
    /// a date in the same submission reads with the business's new country.
    pub fn read(
        record: Record,
        inputs: &[(FieldId, EditInput)],
        today: Date,
    ) -> Result<Edits, Vec<(FieldId, EditRefusal)>> {
        let mut context = record.read_context(today);
        let mut edits = Edits(FieldMap::from_fn(|_| None));
        let mut refusals = Vec::new();
        let mut ordered: Vec<&(FieldId, EditInput)> = inputs.iter().collect();
        ordered.sort_by_key(|(field, _)| *field != STATE);
        for (field, input) in ordered {
            let field = *field;
            if !field.spec().editable() {
                refusals.push((field, EditRefusal::NotEditable));
                continue;
            }
            if edits.0.get(field).is_some() {
                refusals.push((field, EditRefusal::Repeated));
                continue;
            }
            let edit = match input {
                EditInput::Clear => Override::Empty(EmptyReason::Cleared),
                EditInput::UseParse => Override::Inherit,
                EditInput::Text(text) => match field.read(&RawText::typed(text), &context) {
                    Ok(Answer::Value(value)) => Override::Set(value),
                    Ok(Answer::NotApplicable) => Override::Empty(EmptyReason::NotApplicable),
                    Err(why) => {
                        refusals.push((field, EditRefusal::Value(why)));
                        continue;
                    }
                },
            };
            if field == STATE {
                context.business_country = match &edit {
                    Override::Set(value) => country_of(value),
                    Override::Inherit => record.parsed(STATE).and_then(FieldReading::value).and_then(country_of),
                    Override::Empty(_) => None,
                };
            }
            *edits.0.get_mut(field) = Some(edit);
        }
        if refusals.is_empty() { Ok(edits) } else { Err(refusals) }
    }

    /// Empties every editable secondary-owner field. Typing a name again brings the owner back.
    pub fn remove_second_owner() -> Edits {
        Edits(FieldMap::from_fn(|field| {
            (matches!(field, FieldId::Owner(OwnerSlot::Secondary, _)) && field.spec().editable())
                .then_some(Override::Empty(EmptyReason::RemovedOwner))
        }))
    }

    pub fn is_empty(&self) -> bool {
        self.0.iter().all(|(_, edit)| edit.is_none())
    }
}

#[cfg(test)]
#[path = "record_tests.rs"]
mod tests;
