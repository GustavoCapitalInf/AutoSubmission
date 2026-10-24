//! Matching a stored application.

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::Response;
use uuid::Uuid;

use super::review::{confirmations, refused};
use super::{PageError, RawForm, fields, redirect, require};
use crate::applications::{ApplicationId, ApplicationRef};
use crate::criteria::Product;
use crate::matching::{ApplicationInput, MatchCommand, Requester};
use crate::store::auth::{AdminUser, Role};
use crate::web::Shared;

fn unprocessable(message: &str) -> PageError {
    PageError::status(StatusCode::UNPROCESSABLE_ENTITY, message)
}

/// `POST /admin/applications/{id}/matches`: a person's first match of revision `base_revision`,
/// with `product`, an optional `analysis_package_id` and the review form's `confirm.*` choices.
pub async fn create_match(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let id = Uuid::parse_str(&id).map(ApplicationId).map_err(|_| PageError::not_found())?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let revision =
        fields.get("base_revision").parse().map_err(|_| unprocessable("Name the application revision to match."))?;
    let analysis_package = match fields.get("analysis_package_id").trim() {
        "" => None,
        text => Some(Uuid::parse_str(text).map_err(|_| unprocessable("The analysis package id is not a UUID."))?),
    };
    let product = Product::from_key(fields.get("product")).ok_or_else(|| unprocessable("Choose a product."))?;
    let industries = app.read(|tx| tx.industries())?;
    let (confirmations, problems) = confirmations(&fields, &industries, &user);
    if let Some(problem) = problems.first() {
        return Err(unprocessable(problem));
    }
    let command = MatchCommand {
        analysis_package,
        product,
        application: ApplicationInput::Stored(ApplicationRef { id, revision }),
        confirmations,
        waivers: Vec::new(),
    };
    match app.matcher.run(Requester::Person { user: user.id, supersedes: None }, command).await {
        Ok(record) => Ok(redirect(&format!("/admin/matches/{}", record.id))),
        Err(error) => Err(refused(error)),
    }
}
