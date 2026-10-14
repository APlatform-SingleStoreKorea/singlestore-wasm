#[cfg(target_arch = "wasm32")]
#[export_name = "evaluate"]
pub extern "C" fn evaluate_export(value: i64) -> i64 {
    crate::logic::evaluate(value)
}
