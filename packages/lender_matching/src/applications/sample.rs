//! Drawing a blind-audit sample from a folder of PDFs into a scratch data directory.

use std::path::Path;

use super::evaluate::pdf_files;
use super::{ApplicationError, Applications, Sampled};

/// SplitMix64, so that a seed names one draw on every platform.
struct SplitMix(u64);

impl SplitMix {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Uniform in `0..bound`, by multiplying and rejecting the biased low products.
    fn below(&mut self, bound: u64) -> u64 {
        let threshold = bound.wrapping_neg() % bound;
        loop {
            let product = u128::from(self.next()) * u128::from(bound);
            if product as u64 >= threshold {
                return (product >> 64) as u64;
            }
        }
    }
}

/// `count` distinct positions in `0..total`, every subset equally likely, in the order drawn.
pub fn draw(total: usize, count: usize, seed: u64) -> Vec<usize> {
    let count = count.min(total);
    let mut positions: Vec<usize> = (0..total).collect();
    let mut random = SplitMix(seed);
    for i in 0..count {
        let j = i + random.below((total - i) as u64) as usize;
        positions.swap(i, j);
    }
    positions.truncate(count);
    positions
}

/// What a draw stored, in counts.
#[derive(Default)]
pub struct SampleReport {
    pub files: usize,
    pub drawn: usize,
    pub forms: u32,
    pub drafts: u32,
    pub refused: u32,
    pub already: u32,
    pub unreadable: u32,
}

impl SampleReport {
    pub fn lines(&self, seed: u64) -> Vec<String> {
        vec![
            format!(
                "applications sample: drew {} of {} PDF files with seed {seed}. Counts only.",
                self.drawn, self.files
            ),
            format!(
                "stored for the audit: application forms {}, hand-entry drafts {}, refused documents {}",
                self.forms, self.drafts, self.refused
            ),
            format!("already stored {}; not stored, as the PDF could not be read, {}", self.already, self.unreadable),
        ]
    }
}

/// Stores `count` PDF files drawn from under `folder` with `seed`, each awaiting its audit. A
/// file pdfium cannot read is counted and left out.
pub fn sample(
    applications: &Applications,
    folder: &Path,
    count: usize,
    seed: u64,
    by: i64,
) -> Result<SampleReport, String> {
    let (pdfs, _) = pdf_files(folder)?;
    if count == 0 || count > pdfs.len() {
        return Err(format!("the folder holds {} PDF files; draw at least 1 and at most that many", pdfs.len()));
    }
    let mut report = SampleReport { files: pdfs.len(), drawn: count, ..SampleReport::default() };
    for position in draw(pdfs.len(), count, seed) {
        let outcome = match std::fs::read(&pdfs[position]) {
            Ok(bytes) => applications.sample(&bytes, by),
            Err(_) => {
                report.unreadable += 1;
                continue;
            }
        };
        match outcome {
            Ok(Sampled::Form) => report.forms += 1,
            Ok(Sampled::ManualEntry) => report.drafts += 1,
            Ok(Sampled::Refused) => report.refused += 1,
            Ok(Sampled::AlreadyStored) => report.already += 1,
            Err(ApplicationError::Pdf(_)) => report.unreadable += 1,
            Err(error) => return Err(error.to_string()),
        }
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_seed_names_one_draw_of_distinct_positions() {
        let first = draw(3500, 60, 2026);
        assert_eq!(first, draw(3500, 60, 2026));
        assert_ne!(first, draw(3500, 60, 2027));
        let mut sorted = first.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), 60);
        assert!(sorted.iter().all(|position| *position < 3500));
        assert_eq!(draw(4, 9, 1).len(), 4);
    }

    #[test]
    fn every_position_is_drawn_about_equally_often() {
        let mut counts = [0u32; 10];
        for seed in 0..20_000 {
            for position in draw(10, 3, seed) {
                counts[position] += 1;
            }
        }
        for count in counts {
            assert!((5_700..=6_300).contains(&count), "{counts:?}");
        }
    }
}
