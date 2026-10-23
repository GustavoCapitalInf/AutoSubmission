use std::fmt;

use serde::{Serialize, Serializer};

/// One field of the application form. Its `Display` (`business.legal_name`, `principal.ssn`) is the
/// key every report uses.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum FieldId {
    Business(BusinessField),
    Owner(OwnerSlot, OwnerField),
    Property(PropertyField),
    Signature(SignatureField),
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum BusinessField {
    LegalName,
    Dba,
    Address,
    Suite,
    City,
    State,
    Zip,
    Phone,
    Fax,
    Entity,
    Email,
    StartDate,
    OwnershipStart,
    TaxId,
    Website,
    LandlordName,
    LandlordPhone,
    LeaseTimeLeft,
    MonthlyRent,
    RentCurrent,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum OwnerSlot {
    Principal,
    Secondary,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum OwnerField {
    Name,
    OwnershipPercent,
    Email,
    Phone,
    Address,
    City,
    State,
    Zip,
    Ssn,
    BirthDate,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum PropertyField {
    Description,
    AnnualRevenue,
    FundsPurpose,
    EstimatedFico,
    CardVolume,
    ReceivablesOutstanding,
    PriorLender,
    LoanBalance,
    RequestedAmount,
    OpenJudgements,
    Bankruptcy,
    TaxLiens,
    Seasonal,
}

/// The dates printed beside the two signature lines.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum SignatureField {
    ApplicantOneDate,
    ApplicantTwoDate,
}

const BUSINESS: [BusinessField; 20] = {
    use BusinessField::*;
    [
        LegalName,
        Dba,
        Address,
        Suite,
        City,
        State,
        Zip,
        Phone,
        Fax,
        Entity,
        Email,
        StartDate,
        OwnershipStart,
        TaxId,
        Website,
        LandlordName,
        LandlordPhone,
        LeaseTimeLeft,
        MonthlyRent,
        RentCurrent,
    ]
};

const OWNER: [OwnerField; 10] = {
    use OwnerField::*;
    [Name, OwnershipPercent, Email, Phone, Address, City, State, Zip, Ssn, BirthDate]
};

const PROPERTY: [PropertyField; 13] = {
    use PropertyField::*;
    [
        Description,
        AnnualRevenue,
        FundsPurpose,
        EstimatedFico,
        CardVolume,
        ReceivablesOutstanding,
        PriorLender,
        LoanBalance,
        RequestedAmount,
        OpenJudgements,
        Bankruptcy,
        TaxLiens,
        Seasonal,
    ]
};

const SIGNATURE: [SignatureField; 2] = [SignatureField::ApplicantOneDate, SignatureField::ApplicantTwoDate];

impl FieldId {
    /// 20 business, 2 x 10 owner, 13 property and 2 signature fields.
    pub const COUNT: usize = 55;

    /// Every field once, in the form's reading order.
    pub const ALL: [FieldId; FieldId::COUNT] = {
        let mut all = [FieldId::Business(BusinessField::LegalName); FieldId::COUNT];
        let mut i = 0;
        while i < BUSINESS.len() {
            all[i] = FieldId::Business(BUSINESS[i]);
            i += 1;
        }
        let mut j = 0;
        while j < OWNER.len() {
            all[20 + j] = FieldId::Owner(OwnerSlot::Principal, OWNER[j]);
            all[30 + j] = FieldId::Owner(OwnerSlot::Secondary, OWNER[j]);
            j += 1;
        }
        let mut k = 0;
        while k < PROPERTY.len() {
            all[40 + k] = FieldId::Property(PROPERTY[k]);
            k += 1;
        }
        all[53] = FieldId::Signature(SIGNATURE[0]);
        all[54] = FieldId::Signature(SIGNATURE[1]);
        all
    };

    /// The position of this field in `ALL`.
    pub fn index(self) -> usize {
        match self {
            FieldId::Business(field) => field as usize,
            FieldId::Owner(OwnerSlot::Principal, field) => 20 + field as usize,
            FieldId::Owner(OwnerSlot::Secondary, field) => 30 + field as usize,
            FieldId::Property(field) => 40 + field as usize,
            FieldId::Signature(field) => 53 + field as usize,
        }
    }

    pub fn from_key(key: &str) -> Option<FieldId> {
        FieldId::ALL.into_iter().find(|field| field.to_string() == key)
    }

    fn section(self) -> &'static str {
        match self {
            FieldId::Business(_) => "business",
            FieldId::Owner(OwnerSlot::Principal, _) => "principal",
            FieldId::Owner(OwnerSlot::Secondary, _) => "secondary",
            FieldId::Property(_) => "property",
            FieldId::Signature(_) => "signatures",
        }
    }

    fn name(self) -> &'static str {
        match self {
            FieldId::Business(field) => match field {
                BusinessField::LegalName => "legal_name",
                BusinessField::Dba => "dba",
                BusinessField::Address => "address",
                BusinessField::Suite => "suite",
                BusinessField::City => "city",
                BusinessField::State => "state",
                BusinessField::Zip => "zip",
                BusinessField::Phone => "phone",
                BusinessField::Fax => "fax",
                BusinessField::Entity => "entity",
                BusinessField::Email => "email",
                BusinessField::StartDate => "start_date",
                BusinessField::OwnershipStart => "ownership_start",
                BusinessField::TaxId => "tax_id",
                BusinessField::Website => "website",
                BusinessField::LandlordName => "landlord_name",
                BusinessField::LandlordPhone => "landlord_phone",
                BusinessField::LeaseTimeLeft => "lease_time_left",
                BusinessField::MonthlyRent => "monthly_rent",
                BusinessField::RentCurrent => "rent_current",
            },
            FieldId::Owner(_, field) => match field {
                OwnerField::Name => "name",
                OwnerField::OwnershipPercent => "ownership_percent",
                OwnerField::Email => "email",
                OwnerField::Phone => "phone",
                OwnerField::Address => "address",
                OwnerField::City => "city",
                OwnerField::State => "state",
                OwnerField::Zip => "zip",
                OwnerField::Ssn => "ssn",
                OwnerField::BirthDate => "birth_date",
            },
            FieldId::Property(field) => match field {
                PropertyField::Description => "description",
                PropertyField::AnnualRevenue => "annual_revenue",
                PropertyField::FundsPurpose => "funds_purpose",
                PropertyField::EstimatedFico => "estimated_fico",
                PropertyField::CardVolume => "card_volume",
                PropertyField::ReceivablesOutstanding => "receivables_outstanding",
                PropertyField::PriorLender => "prior_lender",
                PropertyField::LoanBalance => "loan_balance",
                PropertyField::RequestedAmount => "requested_amount",
                PropertyField::OpenJudgements => "open_judgements",
                PropertyField::Bankruptcy => "bankruptcy",
                PropertyField::TaxLiens => "tax_liens",
                PropertyField::Seasonal => "seasonal",
            },
            FieldId::Signature(field) => match field {
                SignatureField::ApplicantOneDate => "applicant_one_date",
                SignatureField::ApplicantTwoDate => "applicant_two_date",
            },
        }
    }

    /// An exhaustive `match`, so a new field does not compile without its spec.
    pub fn spec(self) -> FieldSpec {
        use FieldKind as K;
        let (kind, required, masked) = match self {
            FieldId::Business(field) => {
                let kind = match field {
                    BusinessField::LegalName
                    | BusinessField::Dba
                    | BusinessField::Address
                    | BusinessField::Suite
                    | BusinessField::City
                    | BusinessField::Website
                    | BusinessField::LandlordName
                    | BusinessField::LeaseTimeLeft => K::Text,
                    BusinessField::State => K::Jurisdiction,
                    BusinessField::Zip => K::PostalCode,
                    BusinessField::Phone | BusinessField::Fax | BusinessField::LandlordPhone => K::Phone,
                    BusinessField::Entity => K::Entity,
                    BusinessField::Email => K::Email,
                    BusinessField::StartDate | BusinessField::OwnershipStart => K::StatedDate,
                    BusinessField::TaxId => K::TaxId,
                    BusinessField::MonthlyRent => K::Money,
                    BusinessField::RentCurrent => K::YesNo,
                };
                let required = matches!(
                    field,
                    BusinessField::Address
                        | BusinessField::City
                        | BusinessField::Zip
                        | BusinessField::Email
                        | BusinessField::StartDate
                        | BusinessField::TaxId
                );
                (kind, required, false)
            }
            FieldId::Owner(slot, field) => {
                let kind = match field {
                    OwnerField::Name | OwnerField::Address | OwnerField::City => K::Text,
                    OwnerField::OwnershipPercent => K::Percent,
                    OwnerField::Email => K::Email,
                    OwnerField::Phone => K::Phone,
                    OwnerField::State => K::Jurisdiction,
                    OwnerField::Zip => K::PostalCode,
                    OwnerField::Ssn => K::Ssn,
                    OwnerField::BirthDate => K::BirthDate,
                };
                let required = slot == OwnerSlot::Principal
                    && matches!(field, OwnerField::Phone | OwnerField::Address | OwnerField::City);
                (kind, required, matches!(field, OwnerField::Ssn | OwnerField::BirthDate))
            }
            FieldId::Property(field) => {
                let kind = match field {
                    PropertyField::Description | PropertyField::FundsPurpose | PropertyField::PriorLender => K::Text,
                    PropertyField::AnnualRevenue
                    | PropertyField::CardVolume
                    | PropertyField::ReceivablesOutstanding
                    | PropertyField::LoanBalance
                    | PropertyField::RequestedAmount => K::Money,
                    PropertyField::EstimatedFico => K::Score,
                    PropertyField::OpenJudgements
                    | PropertyField::Bankruptcy
                    | PropertyField::TaxLiens
                    | PropertyField::Seasonal => K::YesNo,
                };
                (kind, false, false)
            }
            FieldId::Signature(_) => (K::SignatureDate, false, false),
        };
        FieldSpec { kind, required, masked }
    }
}

impl fmt::Display for FieldId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}", self.section(), self.name())
    }
}

impl Serialize for FieldId {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_str(self)
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct FieldSpec {
    pub kind: FieldKind,
    /// Required for a complete application: the fields the owner's screenshot stars.
    pub required: bool,
    /// Identity data: the SSN and the date of birth.
    pub masked: bool,
}

/// How a field's text reads; `FieldKind::read` holds the grammar of each kind.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FieldKind {
    Text,
    Email,
    Phone,
    Jurisdiction,
    PostalCode,
    Entity,
    /// A business date: a day or a month.
    StatedDate,
    BirthDate,
    SignatureDate,
    TaxId,
    Ssn,
    Money,
    Percent,
    Score,
    YesNo,
}

impl FieldKind {
    /// Kinds whose refused values `applications evaluate --shapes` may describe. Names, emails and
    /// other free text never get a shape.
    pub fn is_structured(self) -> bool {
        !matches!(self, FieldKind::Text | FieldKind::Email)
    }
}

/// One `T` for every field, so "every field appears once" holds by construction.
pub struct FieldMap<T>(Box<[T]>);

impl<T> FieldMap<T> {
    pub fn from_fn(f: impl FnMut(FieldId) -> T) -> FieldMap<T> {
        FieldMap(FieldId::ALL.into_iter().map(f).collect())
    }

    pub fn get(&self, field: FieldId) -> &T {
        &self.0[field.index()]
    }

    pub fn get_mut(&mut self, field: FieldId) -> &mut T {
        &mut self.0[field.index()]
    }

    pub fn iter(&self) -> impl Iterator<Item = (FieldId, &T)> {
        FieldId::ALL.into_iter().zip(self.0.iter())
    }
}

impl<T: Default> Default for FieldMap<T> {
    fn default() -> Self {
        FieldMap::from_fn(|_| T::default())
    }
}

impl<T: Clone> Clone for FieldMap<T> {
    fn clone(&self) -> Self {
        FieldMap(self.0.clone())
    }
}

impl<T: Serialize> Serialize for FieldMap<T> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_map(self.iter())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    #[test]
    fn every_field_has_one_index_and_one_key() {
        for (i, field) in FieldId::ALL.into_iter().enumerate() {
            assert_eq!(field.index(), i, "{field}");
            assert_eq!(FieldId::from_key(&field.to_string()), Some(field));
        }
        let keys: BTreeSet<String> = FieldId::ALL.iter().map(FieldId::to_string).collect();
        assert_eq!(keys.len(), FieldId::COUNT);
        assert_eq!(FieldId::from_key("business.ssn"), None);
    }

    #[test]
    fn keys_name_the_section_and_the_field() {
        assert_eq!(FieldId::Business(BusinessField::LegalName).to_string(), "business.legal_name");
        assert_eq!(FieldId::Owner(OwnerSlot::Secondary, OwnerField::Ssn).to_string(), "secondary.ssn");
        assert_eq!(FieldId::Property(PropertyField::RequestedAmount).to_string(), "property.requested_amount");
        assert_eq!(FieldId::Signature(SignatureField::ApplicantTwoDate).to_string(), "signatures.applicant_two_date");
    }

    #[test]
    fn required_fields_match_the_owner_screenshot() {
        let required: Vec<String> =
            FieldId::ALL.into_iter().filter(|field| field.spec().required).map(|field| field.to_string()).collect();
        assert_eq!(
            required,
            [
                "business.address",
                "business.city",
                "business.zip",
                "business.email",
                "business.start_date",
                "business.tax_id",
                "principal.phone",
                "principal.address",
                "principal.city",
            ]
        );
    }

    #[test]
    fn only_ssn_and_birth_date_are_masked() {
        let masked: Vec<String> =
            FieldId::ALL.into_iter().filter(|field| field.spec().masked).map(|field| field.to_string()).collect();
        assert_eq!(masked, ["principal.ssn", "principal.birth_date", "secondary.ssn", "secondary.birth_date"]);
    }

    #[test]
    fn a_field_map_holds_one_value_per_field() {
        let mut map = FieldMap::from_fn(|field| field.index());
        *map.get_mut(FieldId::Property(PropertyField::Seasonal)) = 0;
        assert_eq!(*map.get(FieldId::Property(PropertyField::Seasonal)), 0);
        assert_eq!(map.iter().count(), FieldId::COUNT);
        let json = serde_json::to_string(&FieldMap::from_fn(|_| 1)).unwrap();
        assert!(
            json.starts_with(r#"{"business.legal_name":1,"#) && json.ends_with(r#""signatures.applicant_two_date":1}"#)
        );
    }
}
