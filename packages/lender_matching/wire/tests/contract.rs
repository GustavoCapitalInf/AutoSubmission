use std::path::Path;

use lender_matching_wire::contract;

fn read(name: &str) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("docs").join("api").join(name);
    std::fs::read_to_string(&path).unwrap_or_else(|error| panic!("{}: {error}", path.display())).replace("\r\n", "\n")
}

#[test]
fn contract_files_are_current() {
    let fix = "run `cargo run -p lender_matching_wire --example write_contract`";
    assert!(read("v1.schema.json") == contract::schema_text(), "docs/api/v1.schema.json is stale; {fix}");
    let doc = read("v1.md");
    assert!(contract::with_reference(&doc).as_deref() == Some(doc.as_str()), "docs/api/v1.md is stale; {fix}");
}
