//! Flat JSON condition-array transport; calculation and NULL policy belong to the caller.
//! This profile accepts unsigned integers, booleans and null, not arbitrary JSON values.
#[derive(Debug, PartialEq, Eq)]
pub enum Value { Integer(u64), Boolean(bool), Null }
pub fn parse(text: &str, min_items: usize, max_items: usize, max_bytes: usize) -> Result<Vec<Value>, &'static str> {
    if min_items > max_items || text.len() > max_bytes { return Err("array_limit"); }
    let text = text.trim_matches(|c| matches!(c, ' '| '\n' | '\r' | '\t'));
    let body = text.strip_prefix('[').and_then(|s| s.strip_suffix(']')).ok_or("invalid_json_array")?;
    let mut values = Vec::new();
    if !body.trim_matches(|c| matches!(c, ' '| '\n' | '\r' | '\t')).is_empty() {
        for token in body.split(',') {
            if values.len() == max_items { return Err("array_limit"); }
            let token = token.trim_matches(|c| matches!(c, ' '| '\n' | '\r' | '\t'));
            values.push(match token {
                "null" => Value::Null, "true" => Value::Boolean(true), "false" => Value::Boolean(false),
                _ => {
                    if token.is_empty() || !token.bytes().all(|b| b.is_ascii_digit()) || (token.len()>1 && token.starts_with('0')) { return Err("invalid_condition"); }
                    Value::Integer(token.parse().map_err(|_| "integer_range")?)
                }
            });
        }
    }
    if values.len() < min_items { return Err("array_limit"); }
    Ok(values)
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn preserves_values_and_null_without_row_policy() {
        assert_eq!(parse("[true,256,null]",0,100,100).unwrap(), vec![Value::Boolean(true),Value::Integer(256),Value::Null]);
        assert_eq!(parse("[]",0,100,100).unwrap(),vec![]);
        assert!(parse("[]",1,100,100).is_err());
        assert_eq!(parse(&format!("[{}]",vec!["1";40].join(",")),0,40,1000).unwrap().len(),40);
    }
    #[test] fn rejects_invalid_json_and_limits() {
        for bad in ["[1,]","[,1]","[01]","[1.5]","[[1]]","[\"x\"]","[1]x","[\u{a0}1]","[18446744073709551616]"] {assert!(parse(bad,0,100,100).is_err(),"{bad}");}
        assert!(parse("[1,2]",0,1,100).is_err());
        assert!(parse("[1,2]",0,10,3).is_err());
    }
}
