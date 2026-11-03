CREATE FUNCTION `{{public}}`({{arguments}})
RETURNS {{return_type}} NULL AS
DECLARE result {{return_type}};
BEGIN
    IF {{null_check}} THEN RETURN NULL; END IF;
{{limit_check}}
    result = `{{core}}`({{argument_names}});
{{error_check}}
    RETURN result;
END;
