use std::path::Path;

use lender_matching_wire::contract;

fn main() {
    let docs = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("docs").join("api");
    std::fs::write(docs.join("v1.schema.json"), contract::schema_text()).expect("write v1.schema.json");
    let doc_path = docs.join("v1.md");
    let doc = std::fs::read_to_string(&doc_path).expect("read v1.md");
    let updated = contract::with_reference(&doc).expect("v1.md lacks the GENERATED markers");
    std::fs::write(&doc_path, updated).expect("write v1.md");
    println!("wrote {} and {}", docs.join("v1.schema.json").display(), doc_path.display());
}
