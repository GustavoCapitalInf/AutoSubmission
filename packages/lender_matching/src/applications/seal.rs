//! Application data is sealed with XChaCha20-Poly1305 before it reaches SQLite. An envelope is the
//! key's id (8 bytes), a random nonce (24 bytes), then the ciphertext and its tag. The associated
//! data binds it to its column, application, row and format, so an envelope copied to another row
//! does not open there.

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use chacha20poly1305::aead::{Aead, Payload};
use chacha20poly1305::{Key, KeyInit, XChaCha20Poly1305, XNonce};
use sha2::{Digest, Sha256};
use uuid::Uuid;

pub const KEY_VARIABLE: &str = "APPLICATION_DATA_KEY";

const ID_LEN: usize = 8;
const NONCE_LEN: usize = 24;

/// The key that seals application data. It has no `Debug` or `Display`, so it cannot reach a log.
pub struct DataKey {
    id: [u8; ID_LEN],
    cipher: XChaCha20Poly1305,
}

/// Where a sealed value is stored.
pub struct Binding {
    pub column: &'static str,
    pub application: Uuid,
    pub row: String,
    pub format: u32,
}

impl Binding {
    fn associated_data(&self) -> Vec<u8> {
        format!("lender-matching application\0{}\0{}\0{}\0{}", self.column, self.application, self.row, self.format)
            .into_bytes()
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SealError {
    /// Sealed with another key.
    OtherKey,
    /// Changed, moved to another row, or not an envelope.
    Broken,
}

impl DataKey {
    /// None when `APPLICATION_DATA_KEY` is unset or empty. A value that is not 32 bytes in base64
    /// is refused with a message that does not hold it.
    pub fn from_env() -> Result<Option<DataKey>, String> {
        let Some(value) = std::env::var_os(KEY_VARIABLE) else { return Ok(None) };
        let value = value.to_str().unwrap_or("\u{FFFD}").trim();
        if value.is_empty() {
            return Ok(None);
        }
        DataKey::parse(value).map(Some)
    }

    fn parse(base64: &str) -> Result<DataKey, String> {
        let bytes = STANDARD.decode(base64).ok().and_then(|bytes| <[u8; 32]>::try_from(bytes).ok());
        bytes.map(DataKey::new).ok_or_else(|| format!("{KEY_VARIABLE} must be 32 bytes in base64"))
    }

    pub fn new(bytes: [u8; 32]) -> DataKey {
        let digest =
            Sha256::new().chain_update(b"lender-matching application data key id\0").chain_update(bytes).finalize();
        let mut id = [0; ID_LEN];
        id.copy_from_slice(&digest[..ID_LEN]);
        DataKey { id, cipher: XChaCha20Poly1305::new(&Key::from(bytes)) }
    }

    pub fn seal(&self, binding: &Binding, plaintext: &[u8]) -> Vec<u8> {
        let mut nonce = [0; NONCE_LEN];
        getrandom::fill(&mut nonce).expect("the OS random source is available");
        let aad = binding.associated_data();
        let ciphertext = self
            .cipher
            .encrypt(&XNonce::from(nonce), Payload { msg: plaintext, aad: &aad })
            .expect("XChaCha20-Poly1305 seals any length stored here");
        [self.id.as_slice(), &nonce, &ciphertext].concat()
    }

    pub fn open(&self, binding: &Binding, envelope: &[u8]) -> Result<Vec<u8>, SealError> {
        let (id, rest) = envelope.split_first_chunk::<ID_LEN>().ok_or(SealError::Broken)?;
        if *id != self.id {
            return Err(SealError::OtherKey);
        }
        let (nonce, ciphertext) = rest.split_first_chunk::<NONCE_LEN>().ok_or(SealError::Broken)?;
        let aad = binding.associated_data();
        self.cipher
            .decrypt(&XNonce::from(*nonce), Payload { msg: ciphertext, aad: &aad })
            .map_err(|_| SealError::Broken)
    }

    /// Whether `envelope` names this key, without opening it.
    pub fn sealed(&self, envelope: &[u8]) -> bool {
        envelope.get(..ID_LEN) == Some(self.id.as_slice())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn binding(row: &str) -> Binding {
        Binding { column: "application_revisions.state", application: Uuid::nil(), row: row.to_string(), format: 1 }
    }

    #[test]
    fn a_value_opens_only_with_its_key_and_its_binding() {
        let key = DataKey::new([7; 32]);
        let sealed = key.seal(&binding("1"), b"SAMPLE OWNER 900-12-3456");
        assert!(!sealed.windows(6).any(|window| window == b"SAMPLE"), "the envelope holds no plaintext");
        assert_eq!(key.open(&binding("1"), &sealed).unwrap(), b"SAMPLE OWNER 900-12-3456");
        assert_ne!(key.seal(&binding("1"), b"SAMPLE"), key.seal(&binding("1"), b"SAMPLE"), "each nonce is fresh");

        assert_eq!(key.open(&binding("2"), &sealed), Err(SealError::Broken), "another row");
        let moved = Binding { column: "application_parses.payload", ..binding("1") };
        assert_eq!(key.open(&moved, &sealed), Err(SealError::Broken), "another column");
        let reformatted = Binding { format: 2, ..binding("1") };
        assert_eq!(key.open(&reformatted, &sealed), Err(SealError::Broken), "another format");
        let mut changed = sealed.clone();
        *changed.last_mut().unwrap() ^= 1;
        assert_eq!(key.open(&binding("1"), &changed), Err(SealError::Broken), "a changed byte");
        assert_eq!(key.open(&binding("1"), &sealed[..20]), Err(SealError::Broken), "truncated");

        let other = DataKey::new([8; 32]);
        assert!(key.sealed(&sealed) && !other.sealed(&sealed));
        assert_eq!(other.open(&binding("1"), &sealed), Err(SealError::OtherKey));
    }

    #[test]
    fn the_key_is_32_bytes_in_base64_and_a_refusal_never_shows_it() {
        let key = DataKey::parse(&STANDARD.encode([7; 32])).unwrap();
        assert!(key.sealed(&DataKey::new([7; 32]).seal(&binding("1"), b"")), "the same bytes are the same key");
        for wrong in [STANDARD.encode([7; 31]), "c2FtcGxlIGtleSBub3QgYmFzZTY0!".to_string()] {
            let message = DataKey::parse(&wrong).err().unwrap();
            assert_eq!(message, "APPLICATION_DATA_KEY must be 32 bytes in base64");
        }
    }
}
