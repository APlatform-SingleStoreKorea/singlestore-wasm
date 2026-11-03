//! General JSON transport. serde_json handles escaping, nested values and JSON syntax.
use serde_json::Value;
#[derive(Debug)]
pub struct Input { pub values: Vec<Value>, pub defaults: Value, pub form: String }
fn fits(v: &Value, s: &Value) -> bool {
    if v.is_null() { return s["nullable"] == true; }
    match s["type"].as_str().unwrap_or("") {
        "string" => v.is_string(),
        "boolean" => v.is_boolean(),
        "integer" => v.as_i64().map_or(false, |n| n >= s["min"].as_i64().unwrap() && n <= s["max"].as_i64().unwrap()),
        "number" => v.as_f64().map_or(false, |n| n.is_finite() && n >= s["min"].as_f64().unwrap() && n <= s["max"].as_f64().unwrap()),
        "array" => v.as_array().map_or(false, |a| a.len() >= s["min_items"].as_u64().unwrap() as usize && a.len() <= s["max_items"].as_u64().unwrap() as usize && a.iter().all(|x| fits(x, &s["items"]))),
        "object" => v.as_object().map_or(false, |a| { let p = s["properties"].as_object().unwrap(); a.len() == p.len() && p.iter().all(|(k,s)| a.get(k).map_or(false, |x| fits(x,s))) }),
        _ => false,
    }
}
pub fn parse(text: &str, spec: &str, argument: &str) -> Result<Input, &'static str> {
    let s: Value = serde_json::from_str(spec).map_err(|_| "invalid_contract")?;
    let s = s["json_arguments"].as_array().ok_or("invalid_contract")?.iter().find(|s| s["argument"] == argument).ok_or("invalid_contract")?;
    if text.len() > s["max_bytes"].as_u64().ok_or("invalid_contract")? as usize { return Err("json_bytes"); }
    let v: Value = serde_json::from_str(text).map_err(|_| "invalid_json")?;
    let values = v.as_array().ok_or("expected_array")?;
    if s["mode"] == "repeat" {
        if values.len() < s["min_items"].as_u64().unwrap() as usize || values.len() > s["max_items"].as_u64().unwrap() as usize { return Err("array_length"); }
        if !values.iter().all(|v| fits(v, &s["items"])) { return Err("array_type"); }
        return Ok(Input { values: values.clone(), defaults: serde_json::json!({}), form: "repeat".into() });
    }
    let candidates: Vec<&Value> = s["variants"].as_array().ok_or("invalid_contract")?.iter().filter(|f| {
        let items = f["items"].as_array().unwrap(); items.len() == values.len() && values.iter().zip(items).all(|(v,s)| fits(v,s))
    }).collect();
    if candidates.len() != 1 { return Err("no_unique_call_form"); }
    let f = candidates[0];
    Ok(Input { values: values.clone(), defaults: f["defaults"].clone(), form: f["form"].as_str().unwrap().into() })
}
