use std::sync::Arc;

use lender_matching_application::fields::{BusinessField, FieldId};
use lender_matching_application::{EditInput, Edits};

use crate::applications::testing::support::form::Form;
use crate::applications::testing::{
    Document, ENVELOPE, LEGAL_NAME, application, earlier_parser, key, reading_with, service,
};
use crate::applications::{Applications, Cause, Intake};
use crate::matching::Matcher;
use crate::store::auth::Role;
use crate::store::{Store, now};
use crate::web::{AppState, router};

const PASSWORD: &str = "correct horse battery";

struct Session {
    http: reqwest::Client,
    base: String,
    cookie: String,
    csrf: String,
}

impl Session {
    async fn post(&self, path: &str, fields: &[(&str, &str)]) -> reqwest::Response {
        let mut pairs = vec![("csrf", self.csrf.as_str())];
        pairs.extend_from_slice(fields);
        let body = form_urlencoded::Serializer::new(String::new()).extend_pairs(pairs).finish();
        self.http
            .post(format!("{}{path}", self.base))
            .header("Cookie", format!("lm_session={}", self.cookie))
            .header("Content-Type", "application/x-www-form-urlencoded")
            .body(body)
            .send()
            .await
            .unwrap()
    }

    async fn get(&self, path: &str) -> String {
        let request = self.http.get(format!("{}{path}", self.base));
        request.header("Cookie", format!("lm_session={}", self.cookie)).send().await.unwrap().text().await.unwrap()
    }
}

/// Serves `applications` on a loopback port, with `username` signed in.
async fn serve(store: Arc<Store>, applications: Applications, username: &str) -> Session {
    crate::analysis_api::install_tls_provider();
    let cookie = store.write(|tx| tx.sign_in(username, PASSWORD)).unwrap().unwrap();
    let csrf = store.read(|tx| tx.session(&cookie)).unwrap().unwrap().csrf;
    let matcher = Matcher::new(store.clone(), None, Some(Arc::new(key())));
    let state = Arc::new(AppState { store, matcher, applications: Some(applications), secure_cookies: false });
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    tokio::spawn(async move { axum::serve(listener, router(state)).await.unwrap() });
    let http = reqwest::Client::builder().redirect(reqwest::redirect::Policy::none()).build().unwrap();
    Session { http, base, cookie, csrf }
}

#[tokio::test(flavor = "multi_thread")]
async fn a_new_reading_shows_what_it_changes_and_adopting_it_keeps_a_persons_value() {
    let store = Arc::new(Store::open_in_memory());
    let reviewer = store.write(|tx| tx.add_user("sample.reviewer", PASSWORD, Role::Reviewer)).unwrap();
    let (applications, reader) = service(&store);
    let older = earlier_parser(applications);
    let pdf = reader.knows(application(Form::word(), ENVELOPE, 21));
    let Intake::Stored { reference, .. } = older.upload(&pdf, reviewer).unwrap() else { panic!("stored") };
    let current = older.current(reference.id).unwrap();
    let edits = Edits::read(current.record(), &[(LEGAL_NAME, EditInput::Text("FABRIKAM LLC"))], now().date());
    older.correct(reference, &edits.ok().unwrap(), Cause::Merchant, None, reviewer).ok().unwrap();
    let city = FieldId::Business(BusinessField::City);
    let renamed = Form::word().set(LEGAL_NAME, "NORTHWIND LLC").set(city, "DALLAS");
    reader.knows(Document::reading_as(pdf, application(renamed, ENVELOPE, 21)));
    let session = serve(store.clone(), reading_with(&store, reader), "sample.reviewer").await;
    let path = format!("/admin/applications/{}", reference.id);

    let shown = session.post(&format!("{path}/reparse"), &[]).await;
    assert_eq!(shown.status(), reqwest::StatusCode::OK);
    let shown = shown.text().await.unwrap();
    assert!(shown.contains("<li>Business City: AUSTIN → DALLAS</li>"), "{shown}");
    assert!(!shown.contains("NORTHWIND LLC"), "a person's value stays");
    let parse = shown.split("name=\"parse\" value=\"").nth(1).unwrap().split('"').next().unwrap().to_string();

    let adopted = session.post(&format!("{path}/adopt"), &[("base_revision", "2"), ("parse", &parse)]).await;
    assert_eq!(adopted.headers()["location"], format!("{path}?done=adopted").as_str());
    let page = session.get(&path).await;
    assert!(
        page.contains("Revision 3 ·") && page.contains("value=\"DALLAS\"") && page.contains("value=\"FABRIKAM LLC\"")
    );
    let again = session.post(&format!("{path}/adopt"), &[("base_revision", "2"), ("parse", &parse)]).await;
    assert_eq!(again.headers()["location"], format!("{path}?done=unchanged").as_str(), "a repeat writes nothing");
    let history = session.get(&format!("{path}/history")).await;
    assert!(history.contains("A new reading of the PDF adopted by sample.reviewer"));
    assert!(history.contains("<li>Business City: AUSTIN → DALLAS</li>"));
    assert!(history.contains("<li>Business Legal Name: CONTOSO LLC → FABRIKAM LLC</li>"));
}
