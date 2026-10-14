"""Small shared helpers. No credential values in generated artifacts."""
import base64
import hashlib
import json
import math
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value):
        raise ValueError('invalid SQL identifier')
    return value

def manifest(project):
    m = json.loads((project / 'function.json').read_text())
    if not isinstance(m, dict):
        raise ValueError('function.json must contain an object')
    from compatibility import validate_manifest
    validate_manifest(m)
    identifier(m['name'])
    if m.get('kind') == 'handle-udaf':
        from aggregate import validate
        return validate(m)
    from return_contracts import resolve
    resolve(m)
    if m['shape'] not in ('string-pair-i64', 'i64-unary', 'f64-scalar'):
        raise ValueError('unsupported ABI shape; add and validate a new template first')
    floating = m['shape'] == 'f64-scalar'
    if floating:
        names = m.get('arguments')
        if (not isinstance(names, list) or not 1 <= len(names) <= 16
                or any(not isinstance(n, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,35}', n) for n in names)
                or len(set(names)) != len(names)):
            raise ValueError('f64-scalar requires 1..16 unique argument names')
        tolerance = m.get('comparison')
        if (not isinstance(tolerance, dict) or set(tolerance) != {'absolute', 'relative'}
                or any(not finite_number(v) or v < 0 for v in tolerance.values())):
            raise ValueError('f64-scalar requires finite nonnegative absolute/relative tolerances')
    if m.get('null_policy') != 'propagate':
        raise ValueError('this starter supports NULL propagation only')
    limit = m.get('max_codepoints')
    if 'max_codepoints' in m and (m['shape'] != 'string-pair-i64' or type(limit) is not int or limit <= 0):
        raise ValueError('max_codepoints must be a positive integer for string-pair-i64')
    sentinel_present = 'error_sentinel' in m
    if sentinel_present:
        sentinel = m['error_sentinel']
        if floating:
            if not finite_number(sentinel):
                raise ValueError('error_sentinel must be finite f64')
        elif type(sentinel) is not int or not -(2**63) <= sentinel < 2**63:
            raise ValueError('error_sentinel must be a signed 64-bit integer')
    if sentinel_present or limit is not None or 'error_message' in m:
        message = m.get('error_message')
        if not isinstance(message, str) or not message.strip() or not re.fullmatch(r'[A-Za-z0-9 _.,:=-]+', message):
            raise ValueError('error_message must be nonempty and contain only safe ASCII text')
        if not sentinel_present and limit is None:
            raise ValueError('error_message requires error_sentinel or max_codepoints')
    cases = m.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('Set nonempty independent expected cases in function.json first')
    ids = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError('each test case must be an object')
        case_id = case.get('id')
        if not isinstance(case_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', case_id) or case_id in ids:
            raise ValueError('test ids must be unique and match [A-Za-z0-9_-]+')
        ids.add(case_id)
        args = case.get('args')
        arity = len(m['arguments']) if floating else (2 if m['shape'] == 'string-pair-i64' else 1)
        if not isinstance(args, list) or len(args) != arity:
            raise ValueError('test arguments do not match ABI arity')
        for arg in args:
            value = expand(arg)
            if value is None:
                continue
            if m['shape'] == 'string-pair-i64':
                if not isinstance(value, str):
                    raise ValueError('string-pair-i64 test inputs must be strings or NULL')
                value.encode('utf-8')
            elif floating:
                if not finite_number(value):
                    raise ValueError('f64-scalar inputs must be finite numbers or NULL')
            elif type(value) is not int or not -(2**63) <= value < 2**63:
                raise ValueError('i64-unary test inputs must be signed 64-bit integers or NULL')
        if ('expected' in case) == ('expected_error' in case):
            raise ValueError('each case requires exactly one of expected and expected_error')
        if 'expected_error' in case:
            if not isinstance(case['expected_error'], str) or not case['expected_error'].strip():
                raise ValueError('expected_error must be a nonempty string')
            if not sentinel_present and limit is None:
                raise ValueError('expected_error requires a configured SQL error mapping')
            if case['expected_error'] not in m['error_message']:
                raise ValueError('expected_error must identify the configured error_message')
        elif case['expected'] is not None:
            expected = case['expected']
            if floating:
                if not finite_number(expected):
                    raise ValueError('expected must be finite f64 or NULL')
            elif type(expected) is not int or not -(2**63) <= expected < 2**63:
                raise ValueError('expected must be a signed 64-bit integer or NULL')
            if sentinel_present and expected == m['error_sentinel']:
                raise ValueError('expected collides with error_sentinel')
    return m

def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False

def scalar_matches(actual, case, spec):
    if 'expected_error' in case:
        return False
    expected = case['expected']
    if expected is None:
        return actual is None
    if spec['shape'] == 'f64-scalar':
        t = spec['comparison']
        return (finite_number(actual) and
                abs(actual - expected) <= t['absolute'] + t['relative'] * abs(expected))
    return actual == expected

def source_fingerprint(project):
    """Hash editable inputs; generated outputs are deliberately excluded."""
    project = project.resolve()
    required = ['Cargo.toml', 'Cargo.lock', 'interface.wit', 'function.json']
    paths = [project / name for name in required]
    toolchains = [project / name for name in ('rust-toolchain.toml', 'rust-toolchain') if (project / name).is_file()]
    if not toolchains:
        raise ValueError('a project Rust toolchain pin is required')
    paths.extend(toolchains)
    sources = sorted(p for p in (project / 'src').rglob('*') if p.is_file())
    if not sources:
        raise ValueError('project src directory contains no source files')
    paths.extend(sources)
    for folder in ('scripts', 'tests', 'vendor'):
        paths.extend(p for p in (project / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend(project / name for name in ('build.rs', '.cargo/config.toml', '.cargo/config', 'contract.json', 'provenance.json') if (project / name).is_file())
    spec = json.loads((project / 'function.json').read_text())
    for name in spec.get('reference', {}).get('files', []):
        path = (project / name).resolve()
        if not path.is_relative_to(project.resolve()) or not path.is_file():
            raise ValueError('reference evidence file must be inside project')
        paths.append(path)
    files = {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'sha256': digest, 'files': files}

def verify_build(project):
    """Reject partial or stale builds before SQL generation or DB access."""
    meta = json.loads((project / 'artifacts/build.json').read_text())
    if meta.get('build_status') != 'passed':
        raise ValueError('build is not passed; rerun build.py successfully')
    if meta.get('source_fingerprint') != source_fingerprint(project):
        raise ValueError('project inputs differ from validated build; rerun build.py')
    if 'tool_fingerprint' in meta and meta['tool_fingerprint'] != tool_fingerprint():
        raise ValueError('pipeline tools differ from validated build; rerun build.py')
    for name, digest in meta.get('artifact_hashes', {}).items():
        if Path(name).name != name or hashlib.sha256((project / 'artifacts' / name).read_bytes()).hexdigest() != digest:
            raise ValueError('artifact changed: ' + name)
    binary = (project / 'artifacts/module.wasm').read_bytes()
    if hashlib.sha256(binary).hexdigest() != meta.get('wasm_sha256'):
        raise ValueError('Wasm differs from validated build')
    encoded = (project / 'artifacts/module.wasm.b64').read_text().strip()
    if base64.b64decode(encoded, validate=True) != binary:
        raise ValueError('Base64 does not round-trip to module.wasm')
    wit = (project / 'interface.wit').read_bytes()
    if hashlib.sha256(wit).hexdigest() != meta.get('wit_sha256'):
        raise ValueError('WIT differs from validated build')
    return meta

def tool_fingerprint():
    paths = [p for folder in ('scripts','templates') for p in (SKILL/folder).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(SKILL).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

def render(path, fields):
    text = (SKILL / path).read_text()
    for key, value in fields.items():
        text = text.replace('{{' + key + '}}', str(value))
    if '{{' in text:
        raise ValueError('unresolved template field')
    return text.strip().removesuffix(';')

def sql_statements(project, database, public):
    database, public = identifier(database), identifier(public)
    core = identifier(public + '_core')
    m = manifest(project)
    verify_build(project)
    b64 = (project / 'artifacts/module.wasm.b64').read_text().strip()
    wit = (project / 'interface.wit').read_bytes()
    from return_contracts import resolve, check_project
    check_project(project,m)
    return_contract=resolve(m)
    floating = m['shape'] == 'f64-scalar'
    pairs = [('left_arg', 'TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin'),
             ('right_arg', 'TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')] if m['shape'] == 'string-pair-i64' else [('value_arg', 'BIGINT')]
    if floating:
        pairs = [('arg_' + n, 'DOUBLE') for n in m['arguments']]
    shared = dict(database=database, public=public, core=core,
                  memory_bytes=m.get('build', {}).get('memory_bytes', 16777216),
                  return_type=return_contract['sql_type'])
    raw = render('templates/sql/basic_core.sql' if floating else 'templates/sql/core.sql', dict(shared,
        arguments=', '.join(f'{n} {t} NOT NULL' for n, t in pairs),
        wasm_base64=b64, wit_base64=base64.b64encode(wit).decode()))
    error_check = ''
    if m.get('error_sentinel') is not None:
        sentinel = literal(m['error_sentinel'])
        message = m['error_message']
        error_check = f"    IF result = {sentinel} THEN RAISE user_exception('{message}'); END IF;"
    limit_check = ''
    if 'max_codepoints' in m:
        condition = ' OR '.join(f'CHAR_LENGTH({n}) > {m["max_codepoints"]}' for n, _ in pairs)
        limit_check = f"    IF {condition} THEN RAISE user_exception('{m['error_message']}'); END IF;"
    wrapper = render('templates/sql/wrapper.sql', dict(shared,
        arguments=', '.join(f'{n} {t} NULL' for n, t in pairs),
        null_check=' OR '.join(f'{n} IS NULL' for n, _ in pairs),
        argument_names=', '.join(n for n, _ in pairs), error_check=error_check, limit_check=limit_check))
    check_project(project,m,registrations=[{'sql':raw},{'sql':wrapper}])
    return raw, wrapper

def expand(value):
    if isinstance(value, dict):
        if set(value) != {'repeat', 'count'} or not isinstance(value['repeat'], str) or type(value['count']) is not int or value['count'] < 0:
            raise ValueError('repeat expressions require a string repeat and nonnegative integer count')
        return value['repeat'] * value['count']
    return value

def string_literal(value):
    """SingleStore 9.1.1: UTF-8 bytes, without unsupported _utf8mb4 X introducer.

    Hex preserves quotes, backslashes, newlines and NUL in every SQL mode.
    Text parameters coerce these bytes using their declared utf8mb4 charset.
    """
    return "X'" + value.encode("utf-8").hex() + "'"


def literal(value):
    if value is None: return 'NULL'
    if isinstance(value, dict):
        if type(value['count']) is not int or value['count'] < 0:
            raise ValueError('invalid repeat count')
        return literal(expand(value))
    if isinstance(value, str):
        return string_literal(value)
    if type(value) is int: return str(value)
    if type(value) is float and math.isfinite(value): return repr(value)
    raise ValueError('test input must be NULL, string, finite number, or repeat expression')

def validation_sql(m, database, public):
    statements = []
    for case in m['cases']:
        args = ', '.join(literal(x) for x in case['args'])
        call = f'`{identifier(database)}`.`{identifier(public)}`({args})'
        if 'expected_error' in case:
            sql = f'SELECT {call} AS expected_error'
        else:
            expected = literal(case['expected'])
            comparison = '(actual <=> expected)'
            if m['shape'] == 'f64-scalar' and case['expected'] is not None:
                t = m['comparison']
                comparison = f"COALESCE(ABS(actual - expected) <= {literal(t['absolute'])} + {literal(t['relative'])} * ABS(expected), 0)"
            sql = f'SELECT actual, expected, {comparison} AS passed FROM (SELECT {call} AS actual, {expected} AS expected) AS comparison_case'
        statements.append((case, sql))
    return statements

def validation_file(checks, m, errors=False):
    """Human-executable SQL with the same expectations used by the DB runner."""
    blocks=[]
    for item in checks:
        case=item['case']
        if ('expected_error' in case)!=errors: continue
        comment='-- '+case['id']
        if errors:
            expectation=case['expected_error']
            if not isinstance(expectation,dict):
                expectation={'code':2242,'contains':[expectation,m['error_message']]}
            comment+='\n-- Expected error: '+json.dumps(expectation,ensure_ascii=True)
        blocks.append(comment+'\n'+item['sql']+';')
    guidance=('-- Each statement must fail with its specified code AND message fragments.\n'
              '-- Run statements individually, or use a client that continues after errors.\n'
              if errors else '-- Every row must have passed = 1.\n')
    if not blocks:guidance+='-- No '+('error' if errors else 'normal')+' cases defined for this contract.\n'
    return guidance+'SET NAMES utf8mb4;\n'+'\n\n'.join(blocks)+'\n'


def write_sql(project, database, public):
    m = manifest(project)
    if m.get('kind') == 'handle-udaf':
        from aggregate import registrations, cases, fixture_plan
        verify_build(project)
        items = registrations(project, m, database, public)
        checks = cases(m, database, public)
        fixtures = fixture_plan(m, database, public)
        out = project / 'artifacts'
        (out/'register.sql').write_text(';\n'.join(x['sql'] for x in items)+';\n')
        for filename, error in [('validate.sql',False),('validate-errors.sql',True)]:
            (out/filename).write_text(validation_file(checks,m,error))
        (out/'sql-plan.json').write_text(json.dumps({'registrations':items,'cases':checks,'fixtures':fixtures},indent=2)+'\n')
        return items
    raw, wrapper = sql_statements(project, database, public)
    out = project / 'artifacts'
    (out / 'register.sql').write_text(f'USE `{identifier(database)}`;\n{raw};\nDELIMITER //\n{wrapper}//\nDELIMITER ;\n')
    checks=[{'case':case,'sql':sql} for case,sql in validation_sql(m,database,public)]
    (out / 'validate.sql').write_text(validation_file(checks,m))
    (out / 'validate-errors.sql').write_text(validation_file(checks,m,True))
    return raw, wrapper
