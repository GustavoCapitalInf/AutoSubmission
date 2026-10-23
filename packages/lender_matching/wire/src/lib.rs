//! The request and response types of the lender matching API, shared by the server and its
//! clients. `docs/api/v1.md` is the contract; `contract` generates its schema and reference.

pub mod v1;

pub mod contract {
    //! `docs/api/v1.schema.json` and the GENERATED block of `docs/api/v1.md` come from the types in
    //! `v1`. `cargo run -p lender_matching_wire --example write_contract` writes both, and the
    //! `contract_files_are_current` test fails when either is stale.

    use std::collections::BTreeSet;

    use schemars::generate::SchemaSettings;
    use serde_json::{Map, Value, json};

    use crate::v1;

    pub const BEGIN: &str = "<!-- BEGIN GENERATED: cargo run -p lender_matching_wire --example write_contract -->";
    pub const END: &str = "<!-- END GENERATED -->";

    /// One JSON Schema (draft 2020-12) document: every request, response and error body, under
    /// `$defs`. Every field of a definition only responses use is required, since the server
    /// writes each one, null included.
    pub fn schema() -> Value {
        let mut generator = SchemaSettings::draft2020_12().into_generator();
        let request = generator.subschema_for::<v1::MatchRequest>().to_value();
        let responses = [
            generator.subschema_for::<v1::MatchResponse>().to_value(),
            generator.subschema_for::<v1::IndustriesResponse>().to_value(),
            generator.subschema_for::<v1::ErrorResponse>().to_value(),
        ];
        let mut definitions = generator.take_definitions(true);
        let in_requests = reachable(std::slice::from_ref(&request), &definitions);
        for name in reachable(&responses, &definitions).difference(&in_requests) {
            let Some(Value::Object(definition)) = definitions.get_mut(name) else { continue };
            if let Some(Value::Object(properties)) = definition.get("properties") {
                let all: Vec<Value> = properties.keys().cloned().map(Value::from).collect();
                definition.insert("required".to_string(), Value::Array(all));
            }
        }
        let mut roots = vec![request];
        roots.extend(responses);
        json!({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "lender-matching API v1",
            "x-api-version": v1::API_VERSION,
            "anyOf": roots,
            "$defs": definitions,
        })
    }

    /// The definitions `roots` name through `$ref`, directly or through other definitions.
    fn reachable(roots: &[Value], definitions: &Map<String, Value>) -> BTreeSet<String> {
        fn refs(value: &Value, found: &mut Vec<String>) {
            match value {
                Value::Object(object) => {
                    if let Some(Value::String(reference)) = object.get("$ref") {
                        found.push(reference.rsplit('/').next().unwrap_or_default().to_string());
                    }
                    object.values().for_each(|child| refs(child, found));
                }
                Value::Array(items) => items.iter().for_each(|child| refs(child, found)),
                _ => {}
            }
        }
        let mut pending = Vec::new();
        roots.iter().for_each(|root| refs(root, &mut pending));
        let mut seen = BTreeSet::new();
        while let Some(name) = pending.pop() {
            if seen.insert(name.clone())
                && let Some(definition) = definitions.get(&name)
            {
                refs(definition, &mut pending);
            }
        }
        seen
    }

    pub fn schema_text() -> String {
        serde_json::to_string_pretty(&schema()).expect("a schema serializes") + "\n"
    }

    fn cell(text: &str) -> String {
        text.replace('|', "\\|").replace('\n', " ")
    }

    fn type_of(schema: &Value) -> String {
        let Some(object) = schema.as_object() else { return "any".to_string() };
        if let Some(reference) = object.get("$ref").and_then(Value::as_str) {
            return format!("`{}`", reference.rsplit('/').next().unwrap_or(reference));
        }
        if let Some(constant) = object.get("const") {
            return format!("`{constant}`");
        }
        if let Some(values) = object.get("enum").and_then(Value::as_array) {
            let values: Vec<String> =
                values.iter().map(|value| format!("`{}`", value.as_str().unwrap_or("null"))).collect();
            return format!("one of {}", values.join(", "));
        }
        for key in ["anyOf", "oneOf"] {
            if let Some(options) = object.get(key).and_then(Value::as_array) {
                return options.iter().map(type_of).collect::<Vec<_>>().join(" or ");
            }
        }
        let item = |kind: &str| match kind {
            "array" => format!("array of {}", object.get("items").map_or("any".to_string(), type_of)),
            "integer" => match object.get("format").and_then(Value::as_str) {
                Some(format) => format!("integer ({format})"),
                None => "integer".to_string(),
            },
            "string" => match object.get("format").and_then(Value::as_str) {
                Some(format) => format!("string ({format})"),
                None => "string".to_string(),
            },
            other => other.to_string(),
        };
        match object.get("type") {
            Some(Value::String(kind)) => item(kind),
            Some(Value::Array(kinds)) => {
                kinds.iter().filter_map(Value::as_str).map(item).collect::<Vec<_>>().join(" or ")
            }
            _ => "any".to_string(),
        }
    }

    fn definition(name: &str, schema: &Map<String, Value>) -> String {
        let mut out = format!("### `{name}`\n\n");
        if let Some(description) = schema.get("description").and_then(Value::as_str) {
            out.push_str(&format!("{}\n\n", description.replace('\n', " ")));
        }
        let Some(properties) = schema.get("properties").and_then(Value::as_object) else {
            let options = schema.get("oneOf").or_else(|| schema.get("anyOf")).and_then(Value::as_array);
            let options = options.map(Vec::as_slice).unwrap_or_default();
            if !options.is_empty() && options.iter().all(|option| option.get("properties").is_some()) {
                out.push_str(
                    "One of these objects, told apart by the field whose value is fixed:

",
                );
                for option in options {
                    let fields = option["properties"].as_object().expect("checked above");
                    let shape: Vec<String> = fields
                        .iter()
                        .map(|(field, property)| match property.get("const") {
                            Some(constant) => format!("`{field}`: `{}`", constant.as_str().unwrap_or("")),
                            None => format!("`{field}` ({})", type_of(property)),
                        })
                        .collect();
                    let meaning = option.get("description").and_then(Value::as_str).unwrap_or("");
                    out.push_str(&format!(
                        "- {}. {meaning}
",
                        shape.join(", ")
                    ));
                }
            } else if !options.is_empty() {
                out.push_str("| Value | Meaning |\n|---|---|\n");
                for option in options {
                    let meaning = cell(option.get("description").and_then(Value::as_str).unwrap_or(""));
                    let values = match (option.get("const"), option.get("enum").and_then(Value::as_array)) {
                        (Some(constant), _) => vec![constant.clone()],
                        (None, Some(values)) => values.clone(),
                        (None, None) => Vec::new(),
                    };
                    for value in values {
                        out.push_str(&format!("| `{}` | {meaning} |\n", value.as_str().unwrap_or("null")));
                    }
                }
            } else if let Some(values) = schema.get("enum").and_then(Value::as_array) {
                out.push_str("| Value |\n|---|\n");
                for value in values {
                    out.push_str(&format!("| `{}` |\n", value.as_str().unwrap_or("null")));
                }
            } else {
                out.push_str(&format!("{}\n", type_of(&Value::Object(schema.clone()))));
            }
            out.push('\n');
            return out;
        };
        let required: Vec<&str> =
            schema.get("required").and_then(Value::as_array).into_iter().flatten().filter_map(Value::as_str).collect();
        out.push_str("| Field | Type | Required | Meaning |\n|---|---|---|---|\n");
        for (field, property) in properties {
            let meaning = property.get("description").and_then(Value::as_str).unwrap_or("");
            let required = if required.contains(&field.as_str()) { "yes" } else { "no" };
            out.push_str(&format!("| `{field}` | {} | {required} | {} |\n", cell(&type_of(property)), cell(meaning)));
        }
        out.push('\n');
        out
    }

    /// The reference block: one section per schema definition, then the error codes.
    pub fn reference() -> String {
        let schema = schema();
        let mut out = format!("{BEGIN}\n\nGenerated from the `lender_matching_wire` crate; never edit it by hand.\n\n");
        let definitions = schema["$defs"].as_object().expect("the schema has definitions");
        for (name, definition_schema) in definitions {
            let empty = Map::new();
            out.push_str(&definition(name, definition_schema.as_object().unwrap_or(&empty)));
        }
        out.push_str("### Error codes\n\n| Code | HTTP status | Message |\n|---|---|---|\n");
        for code in v1::ErrorCode::ALL {
            out.push_str(&format!("| `{}` | {} | {} |\n", code.key(), code.status(), code.message()));
        }
        out.push('\n');
        out.push_str(END);
        out
    }

    /// `doc` with its GENERATED block replaced by `reference()`; None when the markers are missing.
    pub fn with_reference(doc: &str) -> Option<String> {
        let start = doc.find(BEGIN)?;
        let end = doc[start..].find(END)? + start + END.len();
        Some(format!("{}{}{}", &doc[..start], reference(), &doc[end..]))
    }
}
