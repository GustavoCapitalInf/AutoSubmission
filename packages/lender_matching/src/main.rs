mod analysis_api;
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
use data_dir::DataDir;
use info_hub::{ImportError, ImportMode};
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

fn run(cli: Cli) -> Result<ExitCode, String> {
    match cli.command {
        Command::PdfWorker => {
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
    let runtime =
        tokio::runtime::Builder::new_multi_thread().enable_all().build().map_err(|error| error.to_string())?;
    runtime.block_on(async move {
        let store = Arc::new(store);
        let state = Arc::new(AppState { matcher: Matcher::new(store.clone(), analysis), store, secure_cookies });
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
