//! The HTTP server. `/api/v1` authenticates only a bearer token; `/healthz` takes none.

pub mod api;

use std::sync::Arc;

use axum::Router;
use axum::routing::get;

use crate::matching::Matcher;
use crate::store::{ReadTx, Store, StoreError, WriteTx};

pub struct AppState {
    pub store: Arc<Store>,
    pub matcher: Matcher,
    /// Session cookies carry `Secure` when the public URL is https.
    pub secure_cookies: bool,
}

pub type Shared = Arc<AppState>;

impl AppState {
    /// Store calls block; this runs them off the async worker.
    pub fn read<R>(&self, f: impl FnOnce(&ReadTx) -> Result<R, StoreError>) -> Result<R, StoreError> {
        tokio::task::block_in_place(|| self.store.read(f))
    }

    pub fn write<R, E: From<StoreError>>(&self, f: impl FnOnce(&WriteTx) -> Result<R, E>) -> Result<R, E> {
        tokio::task::block_in_place(|| self.store.write(f))
    }
}

pub fn router(state: Shared) -> Router {
    Router::new().route("/healthz", get(|| async { "ok" })).nest("/api/v1", api::router()).with_state(state)
}

/// Prints only the error's own text, which holds no request or response body.
pub fn log_error(context: &str, error: &dyn std::fmt::Display) {
    eprintln!("lender-matching: {context}: {error}");
}
