//! Admin accounts, sessions and machine-client tokens. Secrets are stored only as SHA-256 digests
//! (tokens) or argon2id PHC strings (passwords).

use std::collections::BTreeSet;
use std::sync::OnceLock;

use argon2::Argon2;
use argon2::password_hash::phc::PasswordHash;
use argon2::password_hash::{PasswordHasher, PasswordVerifier};
use base64::Engine;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use sha2::{Digest, Sha256};

/// Ordered: each role can do everything the roles before it can.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub enum Role {
    /// Reads lenders, history, imports and matches.
    Viewer,
    /// Also confirms facts and waives checks on a match.
    Reviewer,
    /// Also edits, activates and pauses lenders and manages industries.
    Editor,
}

impl Role {
    pub const ALL: [Role; 3] = [Role::Viewer, Role::Reviewer, Role::Editor];

    pub fn key(self) -> &'static str {
        match self {
            Role::Viewer => "viewer",
            Role::Reviewer => "reviewer",
            Role::Editor => "editor",
        }
    }

    pub fn from_key(key: &str) -> Option<Role> {
        Role::ALL.into_iter().find(|role| role.key() == key)
    }
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub enum Scope {
    /// `POST /matches`.
    Match,
    /// `GET /industries` and `GET /matches/{id}`.
    Read,
}

impl Scope {
    pub const ALL: [Scope; 2] = [Scope::Match, Scope::Read];

    pub fn key(self) -> &'static str {
        match self {
            Scope::Match => "match",
            Scope::Read => "read",
        }
    }

    pub fn from_key(key: &str) -> Option<Scope> {
        Scope::ALL.into_iter().find(|scope| scope.key() == key)
    }
}

pub fn scopes_text(scopes: &BTreeSet<Scope>) -> String {
    scopes.iter().map(|scope| scope.key()).collect::<Vec<_>>().join(" ")
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct AdminUser {
    pub id: i64,
    pub username: String,
    pub role: Role,
    pub csrf: String,
}

impl AdminUser {
    pub fn can(&self, role: Role) -> bool {
        self.role >= role
    }

    pub fn csrf_matches(&self, sent: &str) -> bool {
        constant_time_eq(self.csrf.as_bytes(), sent.as_bytes())
    }
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct MachineClient {
    pub id: i64,
    pub name: String,
    pub scopes: BTreeSet<Scope>,
}

impl MachineClient {
    pub fn has(&self, scope: Scope) -> bool {
        self.scopes.contains(&scope)
    }
}

/// 32 random bytes, base64url without padding.
pub fn random_secret() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("the OS random source is available");
    URL_SAFE_NO_PAD.encode(bytes)
}

pub fn digest(secret: &str) -> Vec<u8> {
    Sha256::digest(secret.as_bytes()).to_vec()
}

pub fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

pub fn hash_password(password: &str) -> String {
    Argon2::default()
        .hash_password(password.as_bytes())
        .expect("argon2 accepts any password length used here")
        .to_string()
}

/// Verifies against `phc`, or against a fixed hash when the account is unknown so both take the
/// same time.
pub fn verify_password(password: &str, phc: Option<&str>) -> bool {
    static UNKNOWN_ACCOUNT: OnceLock<String> = OnceLock::new();
    let phc = phc.unwrap_or_else(|| UNKNOWN_ACCOUNT.get_or_init(|| hash_password(&random_secret())));
    let Ok(parsed) = PasswordHash::new(phc) else { return false };
    Argon2::default().verify_password(password.as_bytes(), &parsed).is_ok()
}

/// At least 12 characters.
pub fn acceptable_password(password: &str) -> bool {
    password.chars().count() >= 12
}
