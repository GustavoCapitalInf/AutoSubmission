mod analysis_api;
mod applications;
mod criteria;
mod data_dir;
mod facts;
mod info_hub;
mod matching;
mod store;
mod web;

use std::collections::BTreeSet;
use std::io::{BufRead, Write};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Arc;

use clap::{Parser, Subcommand, ValueEnum};

use analysis_api::AnalysisClient;
use applications::{Applications, DataKey, Intake, KEY_VARIABLE, WorkerReader};
use data_dir::DataDir;
use info_hub::{ImportError, ImportMode};
use lender_matching_application::tally::TallyOptions;
use matching::Matcher;
use store::Store;
use store::auth::{Role, Scope, acceptable_password};
use web::AppState;

#[derive(Parser)]
#[command(name = "lender-matching", version, about = "Lender criteria CRM and lender matching")]
struct Cli {
    /// The data directory; defaults to the OS data directory.
    #[arg(long, global = true, env = "LENDER_MATCHING_DATA_DIR")]
    data_dir: Option<PathBuf>,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Serve the admin pages and /api/v1.
    Serve {
        #[arg(long, default_value = "127.0.0.1:8080")]
        bind: SocketAddr,
    },
    /// Read the Info Hub workbook's "Lenders Module" sheet; a dry run unless --apply.
    ImportInfoHub {
        path: PathBuf,
        #[arg(long)]
        apply: bool,
    },
    /// Manage admin accounts.
    User {
        #[command(subcommand)]
        command: UserCommand,
    },
    /// Manage machine-client bearer tokens.
    Token {
        #[command(subcommand)]
        command: TokenCommand,
    },
    /// Work with merchant application PDFs.
    Applications {
        #[command(subcommand)]
        command: ApplicationsCommand,
    },
    /// Read PDFs with pdfium for a supervising process: frames on stdin, page data on stdout.
    #[command(hide = true)]
    PdfWorker,
}

#[derive(Subcommand)]
enum UserCommand {
    /// Add an account; prompts for its password.
    Add {
        username: String,
        #[arg(long, value_enum)]
        role: RoleArg,
        /// Read the password from the first line of standard input instead of prompting.
        #[arg(long)]
        password_stdin: bool,
    },
}

#[derive(Subcommand)]
enum ApplicationsCommand {
    /// Read every PDF under a folder and print counts and closed reasons only: no value, file
    /// name or path. Needs PDFIUM_LIBRARY.
    Evaluate {
        folder: PathBuf,
        /// Add each sentinel label's offset from the BUSINESS INFORMATION heading, in whole points.
        #[arg(long)]
        offsets: bool,
        /// Add the shapes of refused structured values (digits as 9, letters as A or a).
        #[arg(long)]
        shapes: bool,
        /// Also write the counts as JSON to this file.
        #[arg(long, value_name = "FILE")]
        json: Option<PathBuf>,
    },
    /// Store application PDFs, sealed with APPLICATION_DATA_KEY, as uploads by a reviewer or an
    /// editor. Prints each file's outcome by its position, not its name. Needs PDFIUM_LIBRARY.
    Import {
        #[arg(required = true)]
        files: Vec<PathBuf>,
        /// The account the uploads are recorded under.
        #[arg(long, value_name = "USERNAME")]
        by: String,
    },
    /// Draw a uniform random sample of the PDF files under a folder, refused ones included, into a
    /// scratch data directory for a blind audit in the admin pages. Prints counts only. Needs
    /// --data-dir, APPLICATION_DATA_KEY and PDFIUM_LIBRARY.
    Sample {
        folder: PathBuf,
        #[arg(long)]
        count: usize,
        /// The same seed draws the same files from the same folder.
        #[arg(long)]
        seed: u64,
        /// The account the sampled uploads are recorded under.
        #[arg(long, value_name = "USERNAME")]
        by: String,
    },
    /// Score the audited documents of a scratch data directory against their frozen parses.
    /// Prints counts only. Needs --data-dir and APPLICATION_DATA_KEY.
    Accuracy,
}

#[derive(Subcommand)]
enum TokenCommand {
    /// Create a token and print it once.
    Create {
        name: String,
        #[arg(long = "scope", value_enum, required = true)]
        scopes: Vec<ScopeArg>,
    },
    /// Revoke the live token with this name.
    Revoke { name: String },
}

#[derive(Clone, Copy, ValueEnum)]
enum RoleArg {
    Viewer,
    Reviewer,
    Editor,
}

#[derive(Clone, Copy, ValueEnum)]
enum ScopeArg {
    Match,
    Read,
}

fn main() -> ExitCode {
    analysis_api::install_tls_provider();
    let cli = Cli::parse();
    match run(cli) {
        Ok(code) => code,
        Err(message) => {
            eprintln!("lender-matching: {message}");
            ExitCode::FAILURE
        }
    }
}

fn open_store(data_dir: Option<PathBuf>) -> Result<(DataDir, Store), String> {
    let dir = DataDir::resolve(data_dir)?;
    let store = Store::open(&dir.database()).map_err(|error| error.to_string())?;
    Ok((dir, store))
}

/// The data key, refusing to go on without one.
fn required_data_key() -> Result<DataKey, String> {
    DataKey::from_env()?
        .ok_or_else(|| format!("set {KEY_VARIABLE} to the 32-byte key, in base64, that seals stored applications"))
}

/// A closed reason as its stored key, such as `unknown_layout`.
fn reason_key(reason: impl serde::Serialize) -> String {
    serde_json::to_value(reason).ok().and_then(|value| value.as_str().map(str::to_string)).unwrap_or_default()
}

/// The stored applications of `data_dir`, read with pdfium when `library` names it.
fn applications_in(data_dir: Option<PathBuf>, library: Option<PathBuf>) -> Result<(Arc<Store>, Applications), String> {
    let data_key = required_data_key()?;
    let (_, store) = open_store(data_dir)?;
    applications::check_key(&store, &data_key)?;
    let store = Arc::new(store);
    let reader = WorkerReader::new(library)?;
    Ok((store.clone(), Applications::new(store, Arc::new(data_key), Arc::new(reader))))
}

/// The live reviewer or editor named `by`.
fn reviewer(store: &Store, by: &str) -> Result<i64, String> {
    match store.read(|tx| tx.user_by_name(by.trim())).map_err(|error| error.to_string())? {
        Some((id, role)) if role >= Role::Reviewer => Ok(id),
        _ => Err(format!("no live reviewer or editor account is named {by}")),
    }
}

/// A blind audit runs in a data directory named for it, not in the OS default.
fn scratch(data_dir: Option<PathBuf>) -> Result<Option<PathBuf>, String> {
    data_dir.map(Some).ok_or_else(|| "name the audit's scratch data directory with --data-dir".to_string())
}

fn sample(
    data_dir: Option<PathBuf>,
    folder: &std::path::Path,
    count: usize,
    seed: u64,
    by: &str,
) -> Result<ExitCode, String> {
    let library = applications::evaluate::pdfium_library()?;
    let (store, applications) = applications_in(scratch(data_dir)?, Some(library))?;
    let user = reviewer(&store, by)?;
    let stored = store.read(|tx| tx.application_uploads()).map_err(|error| error.to_string())?.len();
    let accuracy = applications.accuracy().map_err(|error| error.to_string())?;
    // A sample goes only where every application was drawn for an audit
    // (`a_blind_audit_hides_the_parse_until_it_is_saved_and_accuracy_scores_it`).
    if stored != (accuracy.audited + accuracy.awaiting) as usize {
        return Err(
            "this data directory holds applications that were not drawn for an audit; name a scratch one".to_string()
        );
    }
    let report = applications::sample::sample(&applications, folder, count, seed, user)?;
    for line in report.lines(seed) {
        println!("{line}");
    }
    Ok(ExitCode::SUCCESS)
}

fn import(data_dir: Option<PathBuf>, files: &[PathBuf], by: &str) -> Result<ExitCode, String> {
    required_data_key()?;
    let library = applications::evaluate::pdfium_library()?;
    let (store, applications) = applications_in(data_dir, Some(library))?;
    let user = reviewer(&store, by)?;
    let mut failed = false;
    for (number, path) in (1..).zip(files) {
        let line = match std::fs::read(path).map(|bytes| applications.upload(&bytes, user)) {
            Err(_) => Err("cannot read the file".to_string()),
            Ok(Err(error)) => Err(format!("not stored: {error}")),
            Ok(Ok(Intake::Stored { reference, manual_entry, same_envelope })) => {
                let draft = manual_entry.map(|reason| format!(" as a manual-entry draft ({})", reason_key(reason)));
                let envelope = same_envelope.map(|earlier| format!("; {earlier} is from the same envelope"));
                Ok(format!("stored {}{}{}", reference.id, draft.unwrap_or_default(), envelope.unwrap_or_default()))
            }
            Ok(Ok(Intake::AlreadyStored(reference))) => Ok(format!("already stored as {}", reference.id)),
            Ok(Ok(Intake::Refused(reason))) => Ok(format!("refused: {}", reason_key(reason))),
        };
        failed |= line.is_err();
        println!("{number}: {}", line.unwrap_or_else(|message| message));
    }
    Ok(if failed { ExitCode::FAILURE } else { ExitCode::SUCCESS })
}

fn run(cli: Cli) -> Result<ExitCode, String> {
    match cli.command {
        Command::Applications { command: ApplicationsCommand::Import { files, by } } => {
            import(cli.data_dir, &files, &by)
        }
        Command::Applications { command: ApplicationsCommand::Sample { folder, count, seed, by } } => {
            sample(cli.data_dir, &folder, count, seed, &by)
        }
        Command::Applications { command: ApplicationsCommand::Accuracy } => {
            let (_, applications) = applications_in(scratch(cli.data_dir)?, None)?;
            for line in applications.accuracy().map_err(|error| error.to_string())?.lines() {
                println!("{line}");
            }
            Ok(ExitCode::SUCCESS)
        }
        Command::Applications { command: ApplicationsCommand::Evaluate { folder, offsets, shapes, json } } => {
            let tally = applications::evaluate::evaluate(&folder, TallyOptions { offsets, shapes })?;
            for line in tally.lines() {
                println!("{line}");
            }
            if let Some(json) = json {
                let text = serde_json::to_string_pretty(&tally).map_err(|error| error.to_string())?;
                std::fs::write(&json, text + "\n").map_err(|_| "cannot write the JSON file".to_string())?;
            }
            Ok(ExitCode::SUCCESS)
        }
        Command::PdfWorker => {
            if cli.data_dir.is_some() || std::env::var_os(KEY_VARIABLE).is_some() {
                return Err(format!("the PDF worker takes neither {KEY_VARIABLE} nor a data directory"));
            }
            let library = std::env::var_os("PDFIUM_LIBRARY").map(PathBuf::from);
            lender_matching_application::worker::serve(
                library.as_deref(),
                std::io::stdin().lock(),
                std::io::stdout().lock(),
            )
            .map_err(|error| error.to_string())?;
            Ok(ExitCode::SUCCESS)
        }
        Command::Serve { bind } => {
            let (dir, store) = open_store(cli.data_dir)?;
            serve(dir, store, bind)
        }
        Command::ImportInfoHub { path, apply } => {
            let (_, store) = open_store(cli.data_dir)?;
            let sheet = info_hub::read_sheet(&path).map_err(|error| format!("{}: {error}", path.display()))?;
            let mode = if apply { ImportMode::Apply } else { ImportMode::DryRun };
            let report = match info_hub::run(&store, &sheet, mode) {
                Ok(report) => report,
                Err(ImportError::Blocked(report)) => *report,
                Err(ImportError::Store(error)) => return Err(error.to_string()),
            };
            for line in report.lines() {
                println!("{line}");
            }
            Ok(if report.blockers.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE })
        }
        Command::User { command: UserCommand::Add { username, role, password_stdin } } => {
            let username = username.trim().to_string();
            if username.is_empty() || username.chars().any(char::is_whitespace) {
                return Err("a username is one word".to_string());
            }
            let password = if password_stdin {
                let mut line = String::new();
                std::io::stdin().lock().read_line(&mut line).map_err(|error| error.to_string())?;
                line.trim_end_matches(['\r', '\n']).to_string()
            } else {
                let first = rpassword::prompt_password("Password: ").map_err(|error| error.to_string())?;
                let again = rpassword::prompt_password("Password again: ").map_err(|error| error.to_string())?;
                if first != again {
                    return Err("the passwords differ".to_string());
                }
                first
            };
            if !acceptable_password(&password) {
                return Err("a password needs at least 12 characters".to_string());
            }
            let role = match role {
                RoleArg::Viewer => Role::Viewer,
                RoleArg::Reviewer => Role::Reviewer,
                RoleArg::Editor => Role::Editor,
            };
            let (_, store) = open_store(cli.data_dir)?;
            store.write(|tx| tx.add_user(&username, &password, role)).map_err(|error| error.to_string())?;
            println!("added {username} ({})", role.key());
            Ok(ExitCode::SUCCESS)
        }
        Command::Token { command: TokenCommand::Create { name, scopes } } => {
            let scopes: BTreeSet<Scope> = scopes
                .into_iter()
                .map(|scope| match scope {
                    ScopeArg::Match => Scope::Match,
                    ScopeArg::Read => Scope::Read,
                })
                .collect();
            let (_, store) = open_store(cli.data_dir)?;
            let token = store
                .write(|tx| tx.create_token(name.trim(), &scopes))
                .map_err(|error| format!("cannot create the token {name}: {error}"))?;
            println!("{token}");
            Ok(ExitCode::SUCCESS)
        }
        Command::Token { command: TokenCommand::Revoke { name } } => {
            let (_, store) = open_store(cli.data_dir)?;
            if store.write(|tx| tx.revoke_token(name.trim())).map_err(|error| error.to_string())? {
                println!("revoked {name}");
                Ok(ExitCode::SUCCESS)
            } else {
                Err(format!("no live token is named {name}"))
            }
        }
    }
}

fn env(name: &str) -> Option<String> {
    std::env::var(name).ok().map(|value| value.trim().to_string()).filter(|value| !value.is_empty())
}

fn secure_cookies(bind: SocketAddr) -> Result<bool, String> {
    match env("PUBLIC_URL") {
        Some(url) if url.starts_with("https://") => Ok(true),
        Some(url) if url.starts_with("http://") && bind.ip().is_loopback() => Ok(false),
        Some(_) => Err("PUBLIC_URL must start with https:// unless the server binds a loopback address".to_string()),
        None if bind.ip().is_loopback() => Ok(false),
        None => Err("set PUBLIC_URL to the https:// address people open, or bind a loopback address".to_string()),
    }
}

fn analysis_client() -> Result<Option<AnalysisClient>, String> {
    match (env("ANALYSIS_API_URL"), env("ANALYSIS_API_TOKEN")) {
        (Some(url), Some(token)) => AnalysisClient::new(&url, &token).map(Some),
        (None, None) => Ok(None),
        _ => Err("set both ANALYSIS_API_URL and ANALYSIS_API_TOKEN, or neither".to_string()),
    }
}

fn serve(dir: DataDir, store: Store, bind: SocketAddr) -> Result<ExitCode, String> {
    let secure_cookies = secure_cookies(bind)?;
    let analysis = analysis_client()?;
    if analysis.is_none() {
        eprintln!("lender-matching: no analysis service is configured; a match that names a package answers 503");
    }
    let key = DataKey::from_env()?;
    match &key {
        Some(key) => applications::check_key(&store, key)?,
        None => eprintln!("lender-matching: no {KEY_VARIABLE} is set; stored applications answer 503"),
    }
    let runtime =
        tokio::runtime::Builder::new_multi_thread().enable_all().build().map_err(|error| error.to_string())?;
    let library = applications::evaluate::pdfium_library().ok();
    if library.is_none() {
        eprintln!("lender-matching: no PDFIUM_LIBRARY is set; uploads answer 503 and pages show no page image");
    }
    let reader: Arc<dyn applications::ReadPdf> = Arc::new(WorkerReader::new(library)?);
    runtime.block_on(async move {
        let store = Arc::new(store);
        let key = key.map(Arc::new);
        let applications = key.clone().map(|key| Applications::new(store.clone(), key, reader));
        let matcher = Matcher::new(store.clone(), analysis, key);
        let state = Arc::new(AppState { matcher, store, applications, secure_cookies });
        let listener =
            tokio::net::TcpListener::bind(bind).await.map_err(|error| format!("cannot bind {bind}: {error}"))?;
        let address = listener.local_addr().map_err(|error| error.to_string())?;
        println!("listening on http://{address}");
        std::io::stdout().flush().map_err(|error| error.to_string())?;
        eprintln!("lender-matching: data directory {}", dir.path().display());
        axum::serve(listener, web::router(state))
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
            })
            .await
            .map_err(|error| error.to_string())?;
        Ok(ExitCode::SUCCESS)
    })
}
