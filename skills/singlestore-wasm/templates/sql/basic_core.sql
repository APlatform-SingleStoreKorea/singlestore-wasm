CREATE FUNCTION `{{database}}`.`{{core}}`({{arguments}})
RETURNS {{return_type}} NOT NULL
AS WASM ABI BASIC GROW TO {{memory_bytes}} FROM BASE64 '{{wasm_base64}}'
USING EXPORT 'evaluate';
