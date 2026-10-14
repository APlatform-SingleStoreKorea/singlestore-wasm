CREATE FUNCTION `{{database}}`.`{{public}}`({{arguments}})
RETURNS {{return_type}} NULL AS
DECLARE result {{return_type}};
BEGIN
    IF {{null_check}} THEN RETURN NULL; END IF;
{{limit_check}}
    result = `{{database}}`.`{{core}}`({{argument_names}});
{{error_check}}
    RETURN result;
END;
