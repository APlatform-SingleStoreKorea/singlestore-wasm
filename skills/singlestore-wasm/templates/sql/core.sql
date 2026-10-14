CREATE FUNCTION `{{database}}`.`{{core}}`
AS WASM ABI CANONICAL GROW TO {{memory_bytes}} FROM BASE64 '{{wasm_base64}}'
WITH WIT FROM BASE64 '{{wit_base64}}'
USING EXPORT 'evaluate';
