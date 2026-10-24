//! The pdfium build is named in three places that must agree: `PDFIUM_BUILD`, `pdfium.lock` and the
//! `pdfium-render` API feature.

use lender_matching_application::PDFIUM_BUILD;

#[test]
fn the_pdfium_build_matches_the_lock_file_and_the_api_feature() {
    let package = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let lock = std::fs::read_to_string(package.join("../pdfium.lock")).unwrap();
    let pins: Vec<&str> = lock.lines().filter(|line| !line.starts_with('#') && !line.trim().is_empty()).collect();
    assert!(!pins.is_empty(), "pdfium.lock pins no build");
    for pin in pins {
        assert_eq!(pin.split_whitespace().next(), Some(PDFIUM_BUILD), "pdfium.lock line: {pin}");
    }
    let number = PDFIUM_BUILD.strip_prefix("chromium/").unwrap();
    let manifest = std::fs::read_to_string(package.join("Cargo.toml")).unwrap();
    assert!(manifest.contains(&format!("\"pdfium_{number}\"")), "Cargo.toml lacks the pdfium_{number} feature");
}
