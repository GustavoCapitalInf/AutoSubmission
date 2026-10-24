use std::fs;
use std::path::Path;

#[test]
fn every_analysis_fixture_validates_against_the_analysis_v1_schema() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let schema_path = root.join("..").join("bank_statement_analysis").join("docs").join("api").join("v1.schema.json");
    let schema: serde_json::Value = serde_json::from_str(&fs::read_to_string(&schema_path).unwrap()).unwrap();
    let validator = jsonschema::validator_for(&schema).unwrap();
    let mut checked = 0;
    for entry in fs::read_dir(root.join("tests").join("fixtures").join("analysis")).unwrap() {
        let path = entry.unwrap().path();
        let body: serde_json::Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        let errors: Vec<String> = validator.iter_errors(&body).map(|error| error.to_string()).collect();
        assert!(errors.is_empty(), "{} is not a v1 body: {errors:#?}", path.display());
        checked += 1;
    }
    assert!(checked >= 4, "found {checked} fixtures");
}
