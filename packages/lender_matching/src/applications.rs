use std::path::{Path, PathBuf};
use std::time::Duration;

use lender_matching_application::extract;
use lender_matching_application::tally::{Failure, Tally, TallyOptions};
use lender_matching_application::worker::{PdfWorker, WorkerError};

/// A document taking longer than this stops the worker and counts as a timeout.
const DOCUMENT_TIMEOUT: Duration = Duration::from_secs(60);

/// Reads every PDF under `folder`, in sorted path order, through a pdfium worker, and keeps only
/// counts. Messages name no file or path inside the folder.
pub fn evaluate(folder: &Path, options: TallyOptions) -> Result<Tally, String> {
    let library = std::env::var_os("PDFIUM_LIBRARY")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .ok_or("set PDFIUM_LIBRARY to the absolute path of the pdfium library that pdfium.lock names")?;
    let (pdfs, others) = pdf_files(folder)?;
    let program = std::env::current_exe().map_err(|error| error.to_string())?;
    let mut worker = PdfWorker::start(&program, &["pdf-worker"], &library).map_err(|error| match error {
        WorkerError::NoEngine => "the PDF worker cannot load pdfium from PDFIUM_LIBRARY".to_string(),
        _ => "the PDF worker did not start".to_string(),
    })?;
    let mut tally = Tally::new(options);
    tally.other_files = others;
    for path in pdfs {
        match std::fs::read(&path) {
            Ok(bytes) => match worker.facts(&bytes, DOCUMENT_TIMEOUT) {
                Ok(facts) => tally.add(&extract::read(&facts)),
                Err(error) => tally.add_failure(Failure::Worker(error)),
            },
            Err(_) => tally.add_failure(Failure::Unopened),
        }
    }
    Ok(tally)
}

/// Every `.pdf` file under `folder` (any case), sorted, and the count of other entries. Symbolic
/// links are counted as other entries and not followed.
fn pdf_files(folder: &Path) -> Result<(Vec<PathBuf>, u32), String> {
    let mut pdfs = Vec::new();
    let mut others = 0;
    let mut pending = vec![folder.to_path_buf()];
    while let Some(directory) = pending.pop() {
        let entries = std::fs::read_dir(&directory).map_err(|_| {
            if directory == folder { "cannot list the folder" } else { "cannot list a folder inside the folder" }
        })?;
        for entry in entries {
            let entry = entry.map_err(|_| "cannot list a folder inside the folder")?;
            let kind = entry.file_type().map_err(|_| "cannot read an entry inside the folder")?;
            let path = entry.path();
            if kind.is_dir() {
                pending.push(path);
            } else if kind.is_file() && path.extension().is_some_and(|ext| ext.eq_ignore_ascii_case("pdf")) {
                pdfs.push(path);
            } else {
                others += 1;
            }
        }
    }
    pdfs.sort();
    Ok((pdfs, others))
}
