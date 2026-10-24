//! The application form: cards of labelled inputs holding the current values, and the reading of
//! a submitted form back into corrections. An input is `f.<field key>`; `clear.<field key>` and
//! `parse.<field key>` are its Clear and Use-the-PDF's-reading boxes.

use std::collections::BTreeMap;

use lender_matching_application::fields::{BusinessField as B, OwnerField as O, OwnerSlot, PropertyField as P};
use lender_matching_application::fields::{Required, SignatureField};
use lender_matching_application::record::{Attention, Origin};
use lender_matching_application::values::Email;
use lender_matching_application::{
    Current, DetailCheck, Document, EditInput, FieldId, FieldValue, Override, Resolved, SignerCheck, compare_signer,
};
use maud::{Markup, html};

use super::text::{self, label};
use crate::applications::{Cause, Snapshot};
use crate::web::admin::Fields;

/// The cards in the order the page shows them, each field once.
pub fn cards() -> [(&'static str, Vec<FieldId>); 4] {
    let business = [
        B::LegalName,
        B::Dba,
        B::Address,
        B::Suite,
        B::City,
        B::State,
        B::Zip,
        B::Phone,
        B::Fax,
        B::Email,
        B::Entity,
        B::StartDate,
        B::OwnershipStart,
        B::TaxId,
        B::Website,
        B::LandlordName,
        B::LandlordPhone,
        B::LeaseTimeLeft,
        B::MonthlyRent,
        B::RentCurrent,
    ];
    let mut business: Vec<FieldId> = business.into_iter().map(FieldId::Business).collect();
    business.insert(2, FieldId::Property(P::Description));
    let property = [
        P::AnnualRevenue,
        P::FundsPurpose,
        P::EstimatedFico,
        P::CardVolume,
        P::ReceivablesOutstanding,
        P::PriorLender,
        P::LoanBalance,
        P::RequestedAmount,
        P::OpenJudgements,
        P::Bankruptcy,
        P::TaxLiens,
        P::Seasonal,
    ];
    let mut property: Vec<FieldId> = property.into_iter().map(FieldId::Property).collect();
    property.extend([SignatureField::ApplicantOneDate, SignatureField::ApplicantTwoDate].map(FieldId::Signature));
    [
        ("Business", business),
        ("Principal Owner", OwnerSlot::Principal.fields().collect()),
        ("Secondary Owner", OwnerSlot::Secondary.fields().collect()),
        ("Property & Funding", property),
    ]
}

/// What one input changes. It holds what a person typed, so it has no `Debug`.
pub enum Change {
    Text(String),
    Clear,
    UseParse,
}

/// The fields a person changed on a submitted form, and why.
pub struct Submission {
    pub changes: Vec<(FieldId, Change)>,
    pub cause: Option<Cause>,
    pub reason: String,
}

impl Submission {
    pub fn change(&self, field: FieldId) -> Option<&Change> {
        self.changes.iter().find(|(changed, _)| *changed == field).map(|(_, change)| change)
    }

    pub fn inputs(&self) -> Vec<(FieldId, EditInput<'_>)> {
        fn input(change: &Change) -> EditInput<'_> {
            match change {
                Change::Text(text) => EditInput::Text(text),
                Change::Clear => EditInput::Clear,
                Change::UseParse => EditInput::UseParse,
            }
        }
        self.changes.iter().map(|(field, change)| (*field, input(change))).collect()
    }
}

fn normalized(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// The page's text for a field the parse needs a person for, when the parse located some.
fn evidence(head: &Snapshot, field: FieldId) -> Option<&str> {
    match &head.parse.reading.document {
        Document::Application(form) => form.fields.get(field).evidence().map(|evidence| evidence.text.as_str()),
        Document::ManualEntry(_) | Document::Refused(_) => None,
    }
}

/// What a reviewer's input for `field` holds: the current value, or for a field that needs review
/// the PDF's text. An SSN's or a date of birth's input is blank.
pub fn shown(head: &Snapshot, resolved: &Resolved, field: FieldId) -> String {
    if field.spec().masked {
        return String::new();
    }
    match &resolved.get(field).current {
        Current::Value { value, .. } => value.canonical(),
        Current::Empty { .. } => String::new(),
        Current::NeedsReview => evidence(head, field).unwrap_or_default().to_string(),
    }
}

/// The fields a person changed on a form rendered from `base`: an input whose text differs from
/// what `base` rendered (an emptied one clears the field), or a ticked box. An input left as
/// rendered changes nothing. A field given two changes is left out, with a problem naming it.
pub fn read_submission(fields: &Fields, base: &Snapshot) -> (Submission, Vec<String>) {
    let resolved = base.record().resolve();
    let mut changes = Vec::new();
    let mut problems = Vec::new();
    for field in FieldId::ALL.into_iter().filter(|field| field.spec().editable()) {
        let key = field.to_string();
        let input = format!("f.{key}");
        let typed = fields.has(&input).then(|| normalized(fields.get(&input)));
        let text = typed
            .filter(|typed| *typed != normalized(&shown(base, &resolved, field)))
            .map(|typed| if typed.is_empty() { Change::Clear } else { Change::Text(typed) });
        let change = match (text, fields.has(&format!("clear.{key}")), fields.has(&format!("parse.{key}"))) {
            (None, false, false) => continue,
            (Some(change), false, false) => change,
            (None | Some(Change::Clear), true, false) => Change::Clear,
            (None, false, true) => Change::UseParse,
            _ => {
                problems.push(format!(
                    "{}: change the text, tick Clear or tick Use the PDF's reading, not two of them",
                    label(field)
                ));
                continue;
            }
        };
        changes.push((field, change));
    }
    let cause = match fields.get("cause") {
        "reading" => Some(Cause::Reading),
        "merchant" => Some(Cause::Merchant),
        _ => None,
    };
    let submission = Submission { changes, cause, reason: fields.get("reason").trim().to_string() };
    (submission, problems)
}

/// One change as a conflict page lists it; a typed SSN or date of birth is not shown.
pub fn change_text(field: FieldId, change: &Change) -> String {
    let what = match change {
        Change::Text(_) if field.spec().masked => "a replacement".to_string(),
        Change::Text(text) => text.clone(),
        Change::Clear => "cleared".to_string(),
        Change::UseParse => "back to the PDF's reading".to_string(),
    };
    format!("{}: {what}", label(field))
}

/// A field's value as a list of changes prints it; an SSN or a date of birth only says that it is
/// recorded.
fn current_text(field: FieldId, current: &Current) -> String {
    match current {
        Current::Value { .. } if field.spec().masked => "recorded".to_string(),
        Current::Value { value, .. } => value.canonical(),
        Current::Empty { .. } => "empty".to_string(),
        Current::NeedsReview => "needs review".to_string(),
    }
}

fn origin(current: &Current) -> Option<Origin> {
    match current {
        Current::Value { origin, .. } | Current::Empty { origin } => Some(*origin),
        Current::NeedsReview => None,
    }
}

/// Each field whose value or origin differs between two records, as "Label: before → after".
pub fn differences(before: &Resolved, after: &Resolved) -> Vec<String> {
    FieldId::ALL
        .into_iter()
        .filter_map(|field| {
            let (old, new) = (&before.get(field).current, &after.get(field).current);
            let same_value = match (old, new) {
                (Current::Value { value: a, .. }, Current::Value { value: b, .. }) => a == b,
                (Current::Empty { .. }, Current::Empty { .. }) | (Current::NeedsReview, Current::NeedsReview) => true,
                _ => false,
            };
            if same_value && origin(old) == origin(new) {
                return None;
            }
            let (from, to) = (current_text(field, old), current_text(field, new));
            let label = label(field);
            Some(match origin(new) {
                _ if !same_value && from == to => format!("{label}: changed"),
                _ if !same_value => format!("{label}: {from} → {to}"),
                Some(Origin::Person) => format!("{label}: {to}, now a person's value"),
                _ => format!("{label}: {to}, now the PDF's reading"),
            })
        })
        .collect()
}

/// How SSNs and dates of birth show.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Sensitive {
    Masked,
    /// In full, on the page a logged reveal answers.
    Revealed,
}

/// The form's state for one rendering.
pub struct FormView<'a> {
    pub head: &'a Snapshot,
    pub resolved: &'a Resolved,
    /// A reviewer or an editor: the inputs can be edited and the boxes ticked, and an SSN shows its
    /// last four digits. A viewer sees no digit of it.
    pub reviewer: bool,
    pub sensitive: Sensitive,
    /// A refused or conflicting submission, shown again; what it typed for an SSN or a date of
    /// birth is not.
    pub submitted: Option<&'a Submission>,
    pub problems: &'a BTreeMap<FieldId, String>,
}

/// An SSN by its last four digits for a reviewer and a date of birth as "Recorded", or either in
/// full once revealed.
fn identity_text(view: &FormView, field: FieldId) -> String {
    match (&view.resolved.get(field).current, view.sensitive) {
        (Current::Value { value, .. }, Sensitive::Revealed) => value.canonical(),
        (Current::Value { value: FieldValue::Ssn(id), .. }, Sensitive::Masked) if view.reviewer => {
            format!("•••-••-{}", id.last_four())
        }
        (Current::Value { .. }, Sensitive::Masked) => "Recorded".to_string(),
        (Current::Empty { .. }, _) => "Missing".to_string(),
        (Current::NeedsReview, Sensitive::Revealed) => match evidence(view.head, field) {
            Some(text) => format!("Needs review; the PDF shows {text}"),
            None => "Needs review".to_string(),
        },
        (Current::NeedsReview, Sensitive::Masked) => "Needs review".to_string(),
    }
}

/// Whether the field holds a value in a complete application, given the other fields now.
fn required_now(view: &FormView, field: FieldId) -> bool {
    match field.spec().required {
        Required::Always => true,
        Required::Never => false,
        Required::IfFilled(other) => view.resolved.value(other).is_some(),
    }
}

fn field_cell(view: &FormView, field: FieldId) -> Markup {
    let spec = field.spec();
    let state = view.resolved.get(field);
    let key = field.to_string();
    let id = format!("f-{}", key.replace('.', "-"));
    let needs_review = matches!(state.current, Current::NeedsReview);
    let class = if needs_review {
        "field needs-review"
    } else if state.attention.contains(&Attention::RequiredEmpty) {
        "field required-empty"
    } else {
        "field"
    };
    let submitted = view.submitted.and_then(|submitted| submitted.change(field));
    let value = match submitted {
        Some(Change::Text(text)) if !spec.masked => text.clone(),
        _ if view.reviewer => shown(view.head, view.resolved, field),
        _ if needs_review || spec.masked => String::new(),
        _ => state.value().map(FieldValue::canonical).unwrap_or_default(),
    };
    let hints: Vec<String> = state
        .attention
        .iter()
        .filter(|attention| **attention != Attention::RequiredEmpty)
        .map(|attention| text::attention(spec.kind, *attention))
        .collect();
    let overridden = *view.head.revision.state.overrides.get(field) != Override::Inherit;
    html! {
        div class=(class) {
            label for=(id) { (label(field)) @if required_now(view, field) { span.star { "*" } } }
            @if !spec.editable() {
                input id=(id) type="text" value=(value) readonly;
                p.hint { @if spec.derived { "Set by the number of owners" } @else { "DocuSign's date stamp" } }
            } @else if spec.masked {
                span.masked { (identity_text(view, field)) }
                @if view.reviewer {
                    input id=(id) type="text" name={ "f." (key) } value="" autocomplete="off" placeholder="Type a replacement";
                }
            } @else {
                input id=(id) type="text" name={ "f." (key) } value=(value) disabled[!view.reviewer];
            }
            @for hint in &hints { p.hint { (hint) } }
            @if let Some(problem) = view.problems.get(&field) { p.problem { (problem) } }
            @if view.reviewer && spec.editable() {
                @let cleared = matches!(submitted, Some(Change::Clear));
                @let reparsed = matches!(submitted, Some(Change::UseParse));
                p.controls {
                    @if !matches!(state.current, Current::Empty { .. }) || cleared {
                        label { input type="checkbox" name={ "clear." (key) } checked[cleared]; " Clear" } " "
                    }
                    @if overridden || reparsed {
                        label { input type="checkbox" name={ "parse." (key) } checked[reparsed]; " Use the PDF's reading" }
                    }
                }
            }
        }
    }
}

fn detail(check: DetailCheck) -> &'static str {
    match check {
        DetailCheck::Agreement => "matches",
        DetailCheck::Difference => "differs",
        DetailCheck::Unavailable => "missing",
    }
}

/// The principal owner against the DocuSign certificate's signers.
fn signer_check(view: &FormView) -> Markup {
    let principal = |field| view.resolved.value(FieldId::Owner(OwnerSlot::Principal, field));
    let name = match principal(O::Name) {
        Some(FieldValue::Text(name)) => Some(name.as_str()),
        _ => None,
    };
    let email: Option<&Email> = match principal(O::Email) {
        Some(FieldValue::Email(email)) => Some(email),
        _ => None,
    };
    let signers = view.head.parse.reading.certificate.as_ref().map_or(&[][..], |certificate| &certificate.signers);
    let comparison = compare_signer(name, email, signers);
    html! {
        @match comparison.check {
            SignerCheck::Agreement => p.check-ok { "DocuSign check: matches the envelope's signer." },
            SignerCheck::Disagreement => p.check-warn {
                "DocuSign check: differs from the envelope's signers (name " (detail(comparison.name)) ", email " (detail(comparison.email)) "). Signers: "
                (signers.iter().map(|signer| format!("{} ({})", signer.name(), signer.email())).collect::<Vec<_>>().join("; "))
            },
            SignerCheck::Ambiguous => p.check-warn { "DocuSign check: several of the envelope's signers match this owner." },
            SignerCheck::Unavailable => p.note { "DocuSign check: not possible; the owner's name or email, or the envelope's signers, are missing." },
        }
    }
}

/// The four cards. `secondary_action` goes in the Secondary Owner card's heading.
pub fn render_cards(view: &FormView, secondary_action: Option<Markup>) -> Markup {
    html! {
        @for (title, fields) in cards() {
            section.card {
                h2 {
                    (title)
                    @if title == "Secondary Owner" { @if let Some(action) = &secondary_action { " " (action) } }
                }
                div.grid { @for field in &fields { (field_cell(view, *field)) } }
                @if title == "Principal Owner" { (signer_check(view)) }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_cards_hold_every_field_once() {
        let mut shown: Vec<FieldId> = cards().into_iter().flat_map(|(_, fields)| fields).collect();
        assert_eq!(shown.len(), FieldId::COUNT);
        shown.sort();
        shown.dedup();
        assert_eq!(shown.len(), FieldId::COUNT);
    }
}
