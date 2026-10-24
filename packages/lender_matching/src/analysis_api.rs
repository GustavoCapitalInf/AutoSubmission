use std::time::Duration;

use reqwest::StatusCode;
use reqwest::header::RETRY_AFTER;
use uuid::Uuid;

use crate::facts::analysis::{Parsed, ReadyPackage, parse};

/// The wait the analysis API sends while a package processes, used when its header is unreadable.
const DEFAULT_RETRY: Duration = Duration::from_secs(10);

pub struct AnalysisClient {
    /// `https://<host>/api/v1`, without a trailing slash.
    base: String,
    token: String,
    http: reqwest::Client,
}

pub enum Fetched {
    Processing { retry_after: Duration },
    Ready(ReadyPackage),
}

/// Each reason names a status or a position, not body content, so it is safe to log.
#[derive(Debug, thiserror::Error)]
pub enum AnalysisError {
    #[error("the analysis service has no package with this id")]
    NotFound,
    #[error("the analysis service is unavailable: {0}")]
    Unavailable(String),
    #[error("the analysis service broke its v1 contract: {0}")]
    ContractMismatch(String),
}

/// Installs `ring` as the process's TLS crypto provider; reqwest is built without one so that no
/// system library or assembler is needed on Windows.
pub fn install_tls_provider() {
    let _ = rustls::crypto::ring::default_provider().install_default();
}

/// True for `localhost` and loopback IP addresses, with or without a port.
pub fn is_loopback_host(host: &str) -> bool {
    let host = host.strip_prefix('[').and_then(|rest| rest.split(']').next()).unwrap_or_else(|| {
        host.rsplit_once(':').filter(|(_, port)| port.bytes().all(|b| b.is_ascii_digit())).map_or(host, |(h, _)| h)
    });
    host.eq_ignore_ascii_case("localhost") || host.parse::<std::net::IpAddr>().is_ok_and(|ip| ip.is_loopback())
}

impl AnalysisClient {
    /// Refuses a URL that is not `https://`, unless it names a loopback host.
    pub fn new(base_url: &str, token: &str) -> Result<AnalysisClient, String> {
        let base = base_url.trim().trim_end_matches('/').to_string();
        let host = match base.split_once("://") {
            Some(("https", rest)) | Some(("http", rest)) => rest.split('/').next().unwrap_or_default(),
            _ => return Err("ANALYSIS_API_URL must start with https://".to_string()),
        };
        if base.starts_with("http://") && !is_loopback_host(host) {
            return Err("ANALYSIS_API_URL must use https:// for a host other than this machine".to_string());
        }
        let token = token.trim().to_string();
        if token.is_empty() {
            return Err("ANALYSIS_API_TOKEN is empty".to_string());
        }
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|error| format!("the HTTP client could not start: {error}"))?;
        Ok(AnalysisClient { base, token, http })
    }

    pub async fn fetch(&self, id: Uuid) -> Result<Fetched, AnalysisError> {
        let url = format!("{}/packages/{}", self.base, id.as_hyphenated());
        let response = self.http.get(&url).bearer_auth(&self.token).send().await.map_err(|error| {
            AnalysisError::Unavailable(if error.is_timeout() { "timed out" } else { "no answer" }.into())
        })?;
        let status = response.status();
        let retry_after = response
            .headers()
            .get(RETRY_AFTER)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.trim().parse::<u64>().ok())
            .map_or(DEFAULT_RETRY, |seconds| Duration::from_secs(seconds.clamp(1, 300)));
        let body = response.bytes().await.map_err(|_| AnalysisError::Unavailable("the body was cut off".into()))?;
        match status {
            StatusCode::OK => match parse(&body, id).map_err(|mismatch| AnalysisError::ContractMismatch(mismatch.0))? {
                Parsed::Processing => Ok(Fetched::Processing { retry_after }),
                Parsed::Ready(package) => Ok(Fetched::Ready(package)),
            },
            StatusCode::NOT_FOUND if error_code(&body).as_deref() == Some("package_not_found") => {
                Err(AnalysisError::NotFound)
            }
            other => Err(AnalysisError::Unavailable(format!("status {}", other.as_u16()))),
        }
    }
}

fn error_code(body: &[u8]) -> Option<String> {
    let value: serde_json::Value = serde_json::from_slice(body).ok()?;
    value.get("error")?.get("code")?.as_str().map(str::to_string)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plain_http_is_only_for_this_machine() {
        install_tls_provider();
        assert!(AnalysisClient::new("http://127.0.0.1:9000/api/v1", "t").is_ok_and(|c| c.base.ends_with("/api/v1")));
        assert!(AnalysisClient::new("http://localhost/api/v1/", "t").is_ok_and(|c| !c.base.ends_with('/')));
        assert!(AnalysisClient::new("http://[::1]:9000/api/v1", "t").is_ok());
        assert!(AnalysisClient::new("http://analysis.contoso.example/api/v1", "t").is_err());
        assert!(AnalysisClient::new("ftp://analysis.contoso.example", "t").is_err());
        assert!(AnalysisClient::new("https://analysis.contoso.example/api/v1", " ").is_err());
    }

    #[test]
    fn loopback_hosts() {
        for host in ["localhost", "127.0.0.1", "127.0.0.1:8080", "[::1]:8080", "LOCALHOST:1"] {
            assert!(is_loopback_host(host), "{host}");
        }
        for host in ["10.0.0.1", "contoso.example", "0.0.0.0:80"] {
            assert!(!is_loopback_host(host), "{host}");
        }
    }
}
