"""Versioned return contracts. WIT describes ABI, never SQL text width/collation.

Only the existing scalar profiles and legacy Canonical HANDLE UDAF are supported.
Unknown versions/kinds/ABIs fail closed; no string SQL type is inferred.
"""
import re
from pathlib import Path

FIELDS = {'abi', 'sql_type', 'charset', 'collation', 'nullable'}
NUMERIC = {'s64': 'BIGINT', 'u64': 'BIGINT UNSIGNED', 's32': 'INT',
           'u32': 'INT UNSIGNED', 'f64': 'DOUBLE'}
WIT_TYPES = {'f64': 'float64', 'bytes': 'list<u8>', 'option-s64': 'option<s64>'}


def contract(abi, sql_type, nullable=False, charset=None, collation=None):
    return dict(abi=abi, sql_type=sql_type, charset=charset, collation=collation, nullable=nullable)


# Migration only for previously supported manifests. Never migrate bare "string".
LEGACY = {a: contract(a, t) for a, t in NUMERIC.items()}
LEGACY.update({'bytes': contract('bytes', 'LONGBLOB'),
               'option-s64': contract('option-s64', 'BIGINT', True)})
# Keyed by exact server, function kind and ABI profile, not by WIT type alone.
PROFILES = {
    ('9.1.1', 'handle-udaf', 'canonical-handle'): {
        **LEGACY, 'string': contract('string', 'TEXT', False, 'utf8mb4', 'utf8mb4_bin')},
    ('9.1.1', 'udf', 'canonical'): {'s64': contract('s64', 'BIGINT', True)},
    ('9.1.1', 'udf', 'basic'): {'f64': contract('f64', 'DOUBLE', True)},
}


def context(m):
    kind = m.get('kind', 'udf')
    profile = m.get('abi_profile', 'canonical-handle' if kind == 'handle-udaf' else
                    ('basic' if m.get('shape') == 'f64-scalar' else 'canonical'))
    version = m.get('target_version', m.get('compatibility', {}).get('target_version', '9.1.1'))
    return version, kind, profile


def fail(m, variant, reason, wit='unverified', generated='not generated', location='function.json#/returns'):
    name = m.get('name', '?')
    cb = variant.get('callbacks', {}).get('terminate', 'evaluate')
    raise ValueError('Return contract mismatch / 반환 타입 계약 불일치:\n'
        f'- Function: {context(m)[1]} {name}; profile: {context(m)}\n'
        f'- WIT return: {wit}; callback: {cb} (SQL {cb.replace("-", "_")})\n'
        f'- Manifest return: {variant.get("returns", "missing")}\n'
        f'- Generated SQL return: {generated}\n'
        f'- Location: {location}\n- Reason: {reason}\n'
        '- Action: explicitly correct function.json returns, interface.wit or SQL generator, then rebuild. '
        'Do not substitute TEXT/LONGTEXT.\n'
        '- DB unverified: registration, SHOW CREATE, calls, MERGE, SERIALIZE/DESERIALIZE, NULL/empty input require live evidence.')


def resolve(m, variant=None):
    handle = m.get('kind') == 'handle-udaf'
    variant = variant if variant is not None else m
    raw = variant.get('returns')
    if raw is None and not handle:
        abi = 'f64' if m.get('shape') == 'f64-scalar' else 's64'
        raw = contract(abi, NUMERIC[abi], True)
    if isinstance(raw, str):
        if raw not in LEGACY:
            fail(m, variant, 'No implicit migration for this ABI; specify all five return fields')
        raw = dict(LEGACY[raw])
    if not isinstance(raw, dict) or set(raw) != FIELDS:
        fail(m, variant, 'returns requires exactly abi, sql_type, charset, collation, nullable')
    if type(raw['nullable']) is not bool or not isinstance(raw['abi'], str):
        fail(m, variant, 'nullable must be a boolean and abi must be a string')
    expected = PROFILES.get(context(m), {}).get(raw['abi'])
    if expected is None:
        fail(m, variant, 'Unverified function kind/version/ABI profile; define a separately evidenced policy')
    if raw != expected:
        fail(m, variant, f'Policy violation or unverified mapping; profile permits {expected}; explicit declaration was preserved',
             wit=WIT_TYPES.get(raw['abi'], raw['abi']), generated=sql_type(raw))
    return dict(raw)


def sql_type(c):
    # Formatting is separate from policy. Every field must be explicit, never inferred here.
    if not isinstance(c.get('sql_type'), str) or not re.fullmatch(r'[A-Z]+(?: UNSIGNED)?', c['sql_type']):
        raise ValueError('invalid SQL return type')
    result = c['sql_type']
    for key, keyword in [('charset', 'CHARACTER SET'), ('collation', 'COLLATE')]:
        if c[key] is not None:
            if not isinstance(c[key], str) or not re.fullmatch(r'[a-z0-9_]+', c[key]):
                raise ValueError('invalid return ' + key)
            result += ' ' + keyword + ' ' + c[key]
    return result + (' NULL' if c['nullable'] else ' NOT NULL')


def wit_functions(path):
    """Strict parser for this toolkit's legacy flat WIT, not modern component WIT."""
    aliases = {}; functions = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        line = line.split('//', 1)[0].strip().rstrip(';')
        if not line: continue
        alias = re.fullmatch(r'type ([\w-]+)\s*=\s*(.+)', line)
        fun = re.fullmatch(r'([\w-]+):\s*func\((.*)\)\s*(?:->\s*(.+))?', line)
        if alias:
            if alias[1] in aliases: raise ValueError(f'{path}:{line_no}: duplicate alias')
            aliases[alias[1]] = alias[2]
        elif fun:
            if fun[1] in functions: raise ValueError(f'{path}:{line_no}: duplicate callback')
            args = []
            if fun[2].strip():
                for arg in fun[2].split(','):
                    if ':' not in arg: raise ValueError(f'{path}:{line_no}: invalid argument')
                    args.append(arg.split(':', 1)[1].strip())
            functions[fun[1]] = (args, fun[3] or '', line_no)
        else: raise ValueError(f'{path}:{line_no}: unsupported WIT syntax; no contract inferred')
    def expand(t, seen=()):
        t = re.sub(r'\s+', '', t)
        if t in aliases:
            if t in seen: raise ValueError(f'{path}: cyclic WIT alias')
            return expand(aliases[t], seen+(t,))
        nested = re.fullmatch(r'(option|list)<(.+)>', t)
        if nested: return nested[1]+'<'+expand(nested[2], seen)+'>'
        return {'f64': 'float64', 'f32': 'float32'}.get(t, t)
    return {name: ([expand(a) for a in args], expand(ret), line)
            for name, (args, ret, line) in functions.items()}


def specs(m):
    if m.get('kind') == 'handle-udaf':
        for suffix, variant in m['aggregates'].items():
            yield suffix, variant, resolve(m, variant)
    else:
        yield '', m, resolve(m)


def expected_wit(m, variant, c):
    ret = WIT_TYPES.get(c['abi'], c['abi'])
    if m.get('kind') != 'handle-udaf':
        params = (['string', 'string'] if m['shape'] == 'string-pair-i64' else
                  ['float64'] * len(m['arguments']) if m['shape'] == 'f64-scalar' else ['s64'])
        return {'evaluate': (params, ret)}
    state = 's32'; blob = 'list<u8>'
    roles = {'initialize': ([], state), 'iterate': ([state]+[WIT_TYPES.get(t,t) for t in m['argument_types']], state),
             'merge': ([state,state],state), 'terminate': ([state],ret),
             'serialize': ([state],blob), 'deserialize': ([blob],state),
             'copymerge': ([state,state],state), 'clone': ([state],state), 'destroy': ([state],state)}
    return {name: roles[role] for role,name in variant['callbacks'].items()}


def lower(params, ret):
    def arg(t):
        if t in ('string', 'list<u8>'): return ['i32', 'i32']
        if t in ('s64','u64'): return ['i64']
        if t == 'float64': return ['f64']
        if t in ('s32','u32'): return ['i32']
        raise ValueError('unsupported WIT lowering: ' + t)
    result = [] if not ret else ['i32'] if ret in ('string','list<u8>','option<s64>') else arg(ret)
    return sum((arg(p) for p in params), []), result


def check_project(project, m, inventory=None, registrations=None):
    path = Path(project)/'interface.wit'
    functions = wit_functions(path)
    exports = {e['name']: e for e in inventory['exports']} if inventory is not None else None
    reports = []
    for suffix, variant, c in specs(m):
        expected = expected_wit(m, variant, c)
        for name, (params, ret) in expected.items():
            actual = functions.get(name)
            location = f'{path}:{actual[2] if actual else 1}; function.json#/aggregates/{suffix}/returns'
            if actual is None or actual[:2] != (params,ret):
                fail(m, variant, f'WIT callback {name}: expected {(params,ret)}, got {actual}',
                     wit=actual[1] if actual else 'missing', generated=sql_type(c), location=location)
            if exports is not None:
                p,r = lower(params,ret); export = exports.get(name,{})
                if export.get('parameters') != p or export.get('results') != r:
                    fail(m,variant,f'Wasm export {name}: expected {(p,r)}, got {export}',
                         wit=ret,generated=sql_type(c),location=location+'; module.wasm export '+name)
        if registrations is not None:
            if m.get('kind') == 'handle-udaf':
                matches = [x for x in registrations if x.get('suffix') == suffix]
                if len(matches)!=1: fail(m,variant,'missing/duplicate aggregate SQL variant',generated='missing')
                check_sql(m, variant, c, matches[0]['sql'], 'artifacts/register.sql', expected)
            else:
                if len(registrations)!=2: fail(m,variant,'expected scalar core and public wrapper')
                check_sql(m,variant,c,registrations[1]['sql'],'artifacts/register.sql wrapper')
                if m['shape']=='f64-scalar':
                    check_sql(m,variant,dict(c,nullable=False),registrations[0]['sql'],'artifacts/register.sql core')
                elif "USING EXPORT 'evaluate'" not in registrations[0]['sql']:
                    fail(m,variant,'Canonical core must use evaluate export')
        reports.append({'variant':suffix,'contract':c,'wit_return':WIT_TYPES.get(c['abi'],c['abi']),
                        'wit_manifest':'passed','wasm_exports':'passed' if exports is not None else 'not_run',
                        'sql_contract':'passed' if registrations is not None else 'not_run',
                        'db_registration':'not_run', 'profile':context(m),
                        'migration':'legacy explicit policy' if not isinstance(variant.get('returns'),dict) else 'none'})
    return reports


def check_sql(m, variant, c, sql, location, callbacks=None):
    if m.get('kind') == 'handle-udaf':
        from aggregate import input_declarations
        expected_inputs = '('+', '.join(input_declarations(m))+')'
        if not sql.splitlines()[0].endswith(expected_inputs):
            fail(m, variant, 'SQL input declaration differs from manifest', location=location)
    match = re.search(r'\bRETURNS\s+(.+?)(?:\n|\s+AS\b)',sql,re.I)
    actual = match[1].strip() if match else 'missing'
    # Whitespace normalization only. TEXT/LONGTEXT, NULL, charset and collation are exact.
    if ' '.join(actual.split()) != sql_type(c):
        fail(m,variant,'manifest and generated RETURNS differ',WIT_TYPES.get(c['abi'],c['abi']),actual,
             location+':'+str(sql[:match.start()].count('\n')+1 if match else 1))
    if callbacks:
        found = dict(re.findall(r'(?m)^(INITIALIZE|ITERATE|MERGE|TERMINATE|SERIALIZE|DESERIALIZE|COPYMERGE|CLONE|DESTROY) WITH (\w+)\s*$',sql))
        wanted = {role.upper(): name.replace('-','_') for role,name in variant['callbacks'].items()}
        if found != wanted: fail(m,variant,'SQL callback names differ from WIT/manifest',generated=actual,location=location)
