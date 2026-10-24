//! pdfium runs in a child process, so a crash or a hang in it cannot take the caller down. The
//! child reads frames of PDF bytes on stdin and writes one frame per document on stdout: the page
//! data, or a closed error kind. A frame is a little-endian `u32` length, then that many bytes.

use std::ffi::OsString;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::time::Duration;

use time::Date;

use crate::page::{Glyph, PdfFacts, Rect, TextPage};
use crate::pdf::{MAX_BYTES, PdfEngine, ReadError};

/// A response frame is page data, which outgrows its PDF; this bounds what the parent accepts.
const MAX_RESPONSE: usize = 256 << 20;
/// How long the child may take to load pdfium.
const START_TIMEOUT: Duration = Duration::from_secs(30);

const READY: u8 = 0;
const NO_ENGINE: u8 = 1;
const FACTS: u8 = 0;
const FAILED: u8 = 1;

fn read_frame(input: &mut impl Read, max: usize) -> io::Result<Option<Vec<u8>>> {
    let mut length = [0; 4];
    match input.read_exact(&mut length) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => return Ok(None),
        Err(error) => return Err(error),
    }
    let length = usize::try_from(u32::from_le_bytes(length)).map_err(|_| io::ErrorKind::InvalidData)?;
    if length > max {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let mut payload = vec![0; length];
    input.read_exact(&mut payload)?;
    Ok(Some(payload))
}

fn write_frame(output: &mut impl Write, payload: &[u8]) -> io::Result<()> {
    let length = u32::try_from(payload.len()).map_err(|_| io::ErrorKind::InvalidInput)?;
    output.write_all(&length.to_le_bytes())?;
    output.write_all(payload)?;
    output.flush()
}

/// The child's side: binds pdfium, answers `READY` or `NO_ENGINE`, then reads documents until
/// stdin closes.
pub fn serve(library: Option<&Path>, mut input: impl Read, mut output: impl Write) -> io::Result<()> {
    let Some(mut engine) = library.and_then(|library| PdfEngine::bind(library).ok()) else {
        return write_frame(&mut output, &[NO_ENGINE]);
    };
    write_frame(&mut output, &[READY])?;
    while let Some(pdf) = read_frame(&mut input, MAX_BYTES)? {
        write_frame(&mut output, &encode(&engine.facts(&pdf)))?;
    }
    Ok(())
}

fn error_code(error: ReadError) -> u8 {
    match error {
        ReadError::NotPdf => 0,
        ReadError::Encrypted => 1,
        ReadError::TooLarge => 2,
        ReadError::Engine => 3,
    }
}

fn error_of(code: u8) -> Option<ReadError> {
    [ReadError::NotPdf, ReadError::Encrypted, ReadError::TooLarge, ReadError::Engine]
        .into_iter()
        .find(|error| error_code(*error) == code)
}

fn encode(result: &Result<PdfFacts, ReadError>) -> Vec<u8> {
    let facts = match result {
        Ok(facts) => facts,
        Err(error) => return vec![FAILED, error_code(*error)],
    };
    let mut out = vec![FACTS];
    let put_u32 = |out: &mut Vec<u8>, n: usize| out.extend(u32::try_from(n).unwrap_or(u32::MAX).to_le_bytes());
    let put_f32 = |out: &mut Vec<u8>, x: f32| out.extend(x.to_le_bytes());
    match facts.created_on {
        Some(date) => {
            out.push(1);
            out.extend(date.to_julian_day().to_le_bytes());
        }
        None => out.push(0),
    }
    put_u32(&mut out, facts.pages.len());
    for page in &facts.pages {
        for x in [page.width, page.height, page.image_cover] {
            put_f32(&mut out, x);
        }
        put_u32(&mut out, page.fonts.len());
        for font in &page.fonts {
            put_u32(&mut out, font.len());
            out.extend(font.as_bytes());
        }
        put_u32(&mut out, page.glyphs.len());
        for glyph in &page.glyphs {
            out.extend(u32::from(glyph.ch).to_le_bytes());
            out.extend(glyph.font.to_le_bytes());
            for x in [glyph.size, glyph.rect.x0, glyph.rect.top, glyph.rect.x1, glyph.rect.bottom] {
                put_f32(&mut out, x);
            }
        }
    }
    out
}

struct Cursor<'a>(&'a [u8]);

impl Cursor<'_> {
    fn take<const N: usize>(&mut self) -> Option<[u8; N]> {
        let (head, rest) = self.0.split_first_chunk::<N>()?;
        self.0 = rest;
        Some(*head)
    }

    fn u8(&mut self) -> Option<u8> {
        self.take::<1>().map(|[b]| b)
    }

    fn count(&mut self) -> Option<usize> {
        usize::try_from(u32::from_le_bytes(self.take()?)).ok()
    }

    fn f32(&mut self) -> Option<f32> {
        Some(f32::from_le_bytes(self.take()?))
    }
}

/// None when the payload is not a well-formed response: the child broke the protocol.
fn decode(payload: &[u8]) -> Option<Result<PdfFacts, ReadError>> {
    let mut cursor = Cursor(payload);
    match cursor.u8()? {
        FAILED => {
            let error = error_of(cursor.u8()?)?;
            cursor.0.is_empty().then_some(Err(error))
        }
        FACTS => {
            let created_on = match cursor.u8()? {
                0 => None,
                1 => Some(Date::from_julian_day(i32::from_le_bytes(cursor.take()?)).ok()?),
                _ => return None,
            };
            let mut pages = Vec::new();
            for _ in 0..cursor.count()? {
                let (width, height, image_cover) = (cursor.f32()?, cursor.f32()?, cursor.f32()?);
                let mut fonts = Vec::new();
                for _ in 0..cursor.count()? {
                    let length = cursor.count()?;
                    let (name, rest) = cursor.0.split_at_checked(length)?;
                    fonts.push(String::from_utf8(name.to_vec()).ok()?);
                    cursor.0 = rest;
                }
                let mut glyphs = Vec::new();
                for _ in 0..cursor.count()? {
                    let ch = char::from_u32(u32::from_le_bytes(cursor.take()?))?;
                    let font = u16::from_le_bytes(cursor.take()?);
                    if usize::from(font) >= fonts.len() {
                        return None;
                    }
                    let size = cursor.f32()?;
                    let rect = Rect { x0: cursor.f32()?, top: cursor.f32()?, x1: cursor.f32()?, bottom: cursor.f32()? };
                    glyphs.push(Glyph { ch, font, size, rect });
                }
                pages.push(TextPage { width, height, fonts, glyphs, image_cover });
            }
            cursor.0.is_empty().then_some(Ok(PdfFacts { created_on, pages }))
        }
        _ => None,
    }
}

/// Why a document gives no page data through the worker. A closed set.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum WorkerError {
    Read(ReadError),
    /// The document took longer than its timeout; the worker was stopped.
    Timeout,
    /// The worker exited or broke the protocol.
    Crashed,
    /// The worker could not load pdfium.
    NoEngine,
}

struct Running {
    child: Child,
    requests: Sender<Vec<u8>>,
    /// Each frame the child writes; `None` once its stdout closes or breaks the protocol.
    responses: Receiver<Option<Vec<u8>>>,
}

impl Running {
    fn stop(mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Supervises one worker process: starts it on demand, gives each document a timeout, and
/// replaces it after a crash or a timeout. The worker's environment is cleared except for
/// `PDFIUM_LIBRARY` (and, on Windows, `SystemRoot`, which system libraries need), and its stderr
/// goes nowhere, so nothing it holds reaches a log.
pub struct PdfWorker {
    program: PathBuf,
    args: Vec<OsString>,
    library: PathBuf,
    running: Option<Running>,
}

impl PdfWorker {
    /// Starts `program args...` as the worker and waits for it to load pdfium from `library`.
    pub fn start(program: &Path, args: &[&str], library: &Path) -> Result<PdfWorker, WorkerError> {
        let mut worker = PdfWorker {
            program: program.to_path_buf(),
            args: args.iter().map(OsString::from).collect(),
            library: library.to_path_buf(),
            running: None,
        };
        worker.running = Some(worker.spawn()?);
        Ok(worker)
    }

    fn spawn(&self) -> Result<Running, WorkerError> {
        let mut command = Command::new(&self.program);
        command.args(&self.args).env_clear().env("PDFIUM_LIBRARY", &self.library);
        if cfg!(windows)
            && let Some(root) = std::env::var_os("SystemRoot")
        {
            command.env("SystemRoot", root);
        }
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| WorkerError::Crashed)?;
        let (Some(mut stdin), Some(mut stdout)) = (child.stdin.take(), child.stdout.take()) else {
            let _ = child.kill();
            let _ = child.wait();
            return Err(WorkerError::Crashed);
        };
        let (requests, pending) = mpsc::channel::<Vec<u8>>();
        let (answer, responses) = mpsc::channel();
        std::thread::spawn(move || {
            for pdf in pending {
                if write_frame(&mut stdin, &pdf).is_err() {
                    break;
                }
            }
        });
        std::thread::spawn(move || {
            loop {
                let frame = read_frame(&mut stdout, MAX_RESPONSE).ok().flatten();
                let done = frame.is_none();
                if answer.send(frame).is_err() || done {
                    break;
                }
            }
        });
        let running = Running { child, requests, responses };
        match running.responses.recv_timeout(START_TIMEOUT) {
            Ok(Some(frame)) if frame == [READY] => Ok(running),
            Ok(Some(frame)) if frame == [NO_ENGINE] => {
                running.stop();
                Err(WorkerError::NoEngine)
            }
            Err(RecvTimeoutError::Timeout) => {
                running.stop();
                Err(WorkerError::Timeout)
            }
            _ => {
                running.stop();
                Err(WorkerError::Crashed)
            }
        }
    }

    /// Reads one document within `timeout`. After a crash or a timeout the next call starts a
    /// new worker.
    pub fn facts(&mut self, pdf: &[u8], timeout: Duration) -> Result<PdfFacts, WorkerError> {
        if pdf.len() > MAX_BYTES {
            return Err(WorkerError::Read(ReadError::TooLarge));
        }
        let running = match self.running.take() {
            Some(running) => running,
            None => self.spawn()?,
        };
        if running.requests.send(pdf.to_vec()).is_err() {
            running.stop();
            return Err(WorkerError::Crashed);
        }
        match running.responses.recv_timeout(timeout) {
            Ok(Some(payload)) => match decode(&payload) {
                Some(result) => {
                    self.running = Some(running);
                    result.map_err(WorkerError::Read)
                }
                None => {
                    running.stop();
                    Err(WorkerError::Crashed)
                }
            },
            Err(RecvTimeoutError::Timeout) => {
                running.stop();
                Err(WorkerError::Timeout)
            }
            Ok(None) | Err(RecvTimeoutError::Disconnected) => {
                running.stop();
                Err(WorkerError::Crashed)
            }
        }
    }
}

impl Drop for PdfWorker {
    fn drop(&mut self) {
        if let Some(running) = self.running.take() {
            running.stop();
        }
    }
}

#[cfg(test)]
mod tests {
    use time::macros::date;

    use super::*;
    use crate::page::build::PageBuilder;

    fn sample() -> PdfFacts {
        let first = PageBuilder::new().text("Calibri", 11.0, 40.0, 60.0, "City").text(
            "ArialMT",
            9.0,
            70.0,
            61.6,
            "SAMPLE\u{FFFD}",
        );
        let second = PageBuilder::new().image_cover(0.25).build();
        PdfFacts { created_on: Some(date!(2026 - 10 - 20)), pages: vec![first.build(), second] }
    }

    #[test]
    fn page_data_crosses_the_pipe_unchanged() {
        let facts = sample();
        let Some(Ok(back)) = decode(&encode(&Ok(sample()))) else { panic!("did not decode") };
        assert_eq!(back.created_on, facts.created_on);
        assert_eq!(back.pages.len(), 2);
        for (a, b) in facts.pages.iter().zip(&back.pages) {
            assert_eq!((a.width, a.height, a.image_cover, &a.fonts), (b.width, b.height, b.image_cover, &b.fonts));
            let glyphs =
                |page: &TextPage| page.glyphs.iter().map(|g| (g.ch, g.font, g.size, g.rect)).collect::<Vec<_>>();
            assert_eq!(glyphs(a), glyphs(b));
        }
        for error in [ReadError::NotPdf, ReadError::Encrypted, ReadError::TooLarge, ReadError::Engine] {
            assert!(matches!(decode(&encode(&Err(error))), Some(Err(back)) if back == error));
        }
    }

    #[test]
    fn a_malformed_response_is_a_protocol_break() {
        let good = encode(&Ok(sample()));
        assert!(decode(&good[..good.len() - 1]).is_none(), "truncated");
        assert!(decode(&[good.as_slice(), &[0]].concat()).is_none(), "trailing bytes");
        assert!(decode(&[FAILED, 9]).is_none(), "unknown error kind");
        assert!(decode(&[7]).is_none(), "unknown tag");
        assert!(decode(&[]).is_none());
    }

    #[test]
    fn frames_round_trip_and_refuse_an_oversized_length() {
        let mut pipe = Vec::new();
        write_frame(&mut pipe, b"SAMPLE").unwrap();
        write_frame(&mut pipe, b"").unwrap();
        let mut input = pipe.as_slice();
        assert_eq!(read_frame(&mut input, 16).unwrap().as_deref(), Some(&b"SAMPLE"[..]));
        assert_eq!(read_frame(&mut input, 16).unwrap().as_deref(), Some(&b""[..]));
        assert_eq!(read_frame(&mut input, 16).unwrap(), None, "a closed pipe ends the loop");
        let mut oversized = Vec::new();
        write_frame(&mut oversized, &[0; 17]).unwrap();
        assert!(read_frame(&mut oversized.as_slice(), 16).is_err());
    }

    #[test]
    fn a_worker_without_pdfium_answers_no_engine() {
        let mut output = Vec::new();
        serve(None, io::empty(), &mut output).unwrap();
        assert_eq!(read_frame(&mut output.as_slice(), 4).unwrap().as_deref(), Some(&[NO_ENGINE][..]));
    }
}
