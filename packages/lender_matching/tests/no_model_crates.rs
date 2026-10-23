//! The product calls no model: no LLM or ML inference crate may enter the dependency graph.

use std::path::Path;

/// Crates that run or call a model.
const MODEL_CRATES: [&str; 24] = [
    "async-openai",
    "openai",
    "openai-api-rs",
    "anthropic",
    "anthropic-sdk",
    "misanthropy",
    "genai",
    "llm",
    "llm-chain",
    "ollama-rs",
    "rig-core",
    "kalosm",
    "mistralrs",
    "llama-cpp-2",
    "llama_cpp",
    "ort",
    "tract-onnx",
    "candle-core",
    "candle-nn",
    "candle-transformers",
    "tch",
    "burn",
    "tokenizers",
    "rust-bert",
];

#[test]
fn no_model_crate_is_locked() {
    let lock = std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("Cargo.lock")).unwrap();
    let locked: Vec<&str> = lock
        .lines()
        .filter_map(|line| line.strip_prefix("name = \""))
        .filter_map(|rest| rest.strip_suffix('"'))
        .collect();
    assert!(locked.len() > 50, "Cargo.lock lists {} packages; is it the workspace lock?", locked.len());
    let found: Vec<&&str> = locked.iter().filter(|name| MODEL_CRATES.contains(name)).collect();
    assert!(found.is_empty(), "model crates in Cargo.lock: {found:?}");
}
