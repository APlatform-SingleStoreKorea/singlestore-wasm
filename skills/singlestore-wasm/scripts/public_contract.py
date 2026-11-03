"""Versioned SQL-facing contract, independent of C and Wasm calling conventions."""
import json
import math
import re

TYPES = {'string': ('TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin', 'String', 'string'),
         's32': ('INT', 'i32', 's32'), 's64': ('BIGINT', 'i64', 's64'),
         'f64': ('DOUBLE', 'f64', 'float64')}


def require(ok, message):
    if not ok:
        raise ValueError('public_contract: ' + message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def schema(s):
    require(isinstance(s, dict), 'type schema required')
    require(s.get('type') in ('string', 'integer', 'number', 'boolean', 'array', 'object'), 'unsupported JSON type')
    require(type(s.get('nullable')) is bool, 'explicit JSON nullable required')
    t = s['type']
    if t in ('integer', 'number'):
        require(all(type(s.get(k)) in (int, float) and math.isfinite(s[k]) for k in ('min', 'max')), 'finite numeric bounds required')
        require(s['min'] <= s['max'], 'reversed numeric bounds')
        if t == 'integer':
            require(type(s['min']) is int and type(s['max']) is int and -(2**63) <= s['min'] <= s['max'] < 2**63, 'integer bounds must fit i64')
    if t == 'array':
        require(type(s.get('min_items')) is int and type(s.get('max_items')) is int and 0 <= s['min_items'] <= s['max_items'], 'array bounds required')
        schema(s.get('items'))
    if t == 'object':
        require(isinstance(s.get('properties'), dict), 'object properties required')
        for child in s['properties'].values(): schema(child)


def matches(v, s):
    if v is None: return s['nullable']
    t = s['type']
    if t == 'string': return isinstance(v, str)
    if t == 'boolean': return type(v) is bool
    if t == 'integer': return type(v) is int and s['min'] <= v <= s['max']
    if t == 'number': return type(v) in (int, float) and math.isfinite(v) and s['min'] <= v <= s['max']
    if t == 'array': return isinstance(v, list) and s['min_items'] <= len(v) <= s['max_items'] and all(matches(x, s['items']) for x in v)
    return isinstance(v, dict) and v.keys() == s['properties'].keys() and all(matches(v[k], child) for k, child in s['properties'].items())


def validate(c):
    require(isinstance(c, dict) and c.get('version') == 1, 'version 1 required')
    origin = c.get('origin', {})
    require(all(text(origin.get(k)) for k in ('database', 'version', 'documentation')), 'source DB, version and documentation required')
    forms = origin.get('forms')
    require(isinstance(forms, list) and bool(forms), 'public SQL forms required')
    ids = set()
    for f in forms:
        require(text(f.get('id')) and f['id'] not in ids, 'unique form id required'); ids.add(f['id'])
        require(text(f.get('returns')) and isinstance(f.get('arguments'), list), 'form arguments and return required')
        names = []
        for a in f['arguments']:
            require(all(text(a.get(k)) for k in ('name', 'type', 'meaning')), 'public argument name/type/meaning required')
            require('default' in a, 'default must be explicit (null means no omission default)')
            names.append(a['name'])
        require(len(names) == len(set(names)), 'duplicate source argument')
    require(all(text(origin.get(k)) for k in ('nulls', 'empty', 'errors', 'boundaries')), 'observable behavior required')
    target = c.get('target', {})
    require(text(target.get('version')) and text(target.get('capability_evidence')), 'target version and capability evidence required')
    args = target.get('arguments')
    require(isinstance(args, list) and 1 <= len(args) <= 16, '1..16 target SQL arguments required')
    names = []
    for a in args:
        require(isinstance(a, dict) and isinstance(a.get('name'), str) and re.fullmatch(r'[a-z][a-z0-9_]{0,35}', a['name']), 'invalid target argument name')
        require(a.get('abi') in TYPES and text(a.get('meaning')), 'supported target ABI and meaning required')
        names.append(a['name'])
    require(len(names) == len(set(names)), 'duplicate target argument')
    require(target.get('sql_null') in ('propagate', 'reject'), 'SQL NULL policy required')
    mappings = c.get('mappings')
    require(isinstance(mappings, list) and {m.get('form') for m in mappings} == ids and len(mappings) == len(ids), 'one mapping per source form required')
    for m in mappings:
        require(isinstance(m.get('bindings'), dict), 'bindings required')
        f = next(f for f in forms if f['id'] == m['form'])
        require(set(m['bindings']) == {a['name'] for a in f['arguments']}, 'bind every source public argument')
        for binding in m['bindings'].values():
            require(isinstance(binding, dict) and binding.get('argument') in names, 'binding must use a target SQL argument')
            if 'index' in binding: require(type(binding['index']) is int and binding['index'] >= 0, 'invalid array position')
        require(text(m.get('source_call')) and text(m.get('target_call')), 'paired calls required')
    internal = c.get('internal')
    require(isinstance(internal, list), 'explicit internal mapping list required')
    for a in internal:
        require(all(text(a.get(k)) for k in ('name', 'expression', 'evidence')), 'internal mapping and source evidence required')
        require(a['name'] not in names and all(a['name'] not in m['bindings'] for m in mappings), 'internal argument exposed')
    from compatibility import evaluate
    decision = evaluate({'target_version': target['version'], 'review_basis': [origin['documentation']],
                         'available_arities': [len(args)], 'selected_arities': [len(args)],
                         'scope_basis': {'source':'sql','evidence':target['capability_evidence']},
                         'differences': c.get('differences')})
    require(decision['state'] == 'ready', 'unresolved public contract differences')
    require(isinstance(c.get('representations'), list), 'explicit complex representations list required')
    arrays = c.get('json_arguments', [])
    require(isinstance(arrays, list), 'json_arguments must be a list')
    seen = set()
    for j in arrays:
        require(j.get('argument') in names and j['argument'] not in seen, 'unique JSON target argument required'); seen.add(j['argument'])
        require(next(a for a in args if a['name'] == j['argument'])['abi'] == 'string', 'JSON transport requires string ABI')
        require(j.get('mode') in ('forms', 'repeat'), 'JSON mode must be forms or repeat')
        require(text(j.get('reason')) and j.get('invalid') == 'error', 'JSON substitution reason and error policy required')
        require(type(j.get('max_bytes')) is int and 1 <= j['max_bytes'] <= 65535, 'JSON TEXT byte limit required')
        if j['mode'] == 'forms':
            variants = j.get('variants', [])
            require(bool(variants), 'JSON variants required')
            lengths = []
            for v in variants:
                require(v.get('form') in ids and isinstance(v.get('items'), list), 'variant form/items required')
                lengths.append(len(v['items']))
                for s in v['items']: schema(s)
                require(isinstance(v.get('defaults'), dict), 'explicit defaults required')
                # These are wrapper defaults, not new SQL/JSON parameters.
                require(all(text(k) for k in v['defaults']), 'invalid default name')
            require(sorted(j.get('allowed_lengths', [])) == sorted(set(lengths)), 'allowed lengths must exactly match variants')
        else:
            require(type(j.get('min_items')) is int and type(j.get('max_items')) is int and 0 <= j['min_items'] <= j['max_items'], 'repeat bounds required')
            schema(j.get('items'))
    all_public = {a['name'] for f in forms for a in f['arguments']}
    for j in arrays:
        if j['mode'] == 'forms':
            require(len({v['form'] for v in j['variants']}) == len(j['variants']), 'duplicate variant form')
            for v in j['variants']:
                require(set(v['defaults']) <= all_public, 'defaults must refer to public source arguments')
                require(not set(v['defaults']) & {a['name'] for a in internal}, 'internal default exposed')
    for m in mappings:
        used = set()
        ordered = []
        form = next(f for f in forms if f['id'] == m['form'])
        for a in form['arguments']:
            b = m['bindings'][a['name']]
            used.add(b['argument'])
            ordered.append((names.index(b['argument']), b.get('index', -1)))
            if 'index' in b:
                require(b['argument'] in seen, 'indexed binding requires JSON contract')
                j = next(j for j in arrays if j['argument'] == b['argument'])
                if j['mode'] == 'forms':
                    variants = [v for v in j['variants'] if v['form'] == m['form']]
                    require(len(variants) == 1 and b['index'] < len(variants[0]['items']), 'array binding outside source form')
        require(used == set(names), 'unused target argument would expose an extra parameter')
        require(ordered == sorted(ordered) and len(ordered) == len(set(ordered)), 'public argument order/positions must be preserved')
    return c


def argument_types(m):
    return [a['abi'] for a in validate(m['public_contract'])['target']['arguments']]


def check_form_coverage(m):
    """Require successful non-SQL-NULL inputs for every declared source form.

    This checks the authored inventory, not completeness against upstream sources.
    JSON form selection mirrors the generated parser (length AND member types).
    """
    c = validate(m['public_contract'])
    ids = {f['id'] for f in c['origin']['forms']}
    names = [a['name'] for a in c['target']['arguments']]
    covered = set()
    for case in m['cases']:
        if 'expected_error' in case:
            continue
        rows = case['rows'] if m.get('kind') == 'handle-udaf' else [case['args']]
        for row in rows:
            if any(v is None for v in row):
                continue
            candidates = set(ids)
            for j in c.get('json_arguments', []):
                raw = json_text(row[names.index(j['argument'])])
                try:
                    values = json.loads(raw)
                except (ValueError, TypeError):
                    candidates.clear(); break
                if not isinstance(values, list) or len(raw.encode('utf-8')) > j['max_bytes']:
                    candidates.clear(); break
                if j['mode'] == 'forms':
                    matches_form = {v['form'] for v in j['variants']
                                    if len(values) == len(v['items'])
                                    and all(matches(x, s) for x, s in zip(values, v['items']))}
                    # Each parser must select a unique form, even with several JSON arguments.
                    candidates &= matches_form if len(matches_form) == 1 else set()
                elif not (j['min_items'] <= len(values) <= j['max_items']
                          and all(matches(x, j['items']) for x in values)):
                    candidates.clear()
            if len(candidates) == 1:
                covered.update(candidates)
    require(covered == ids, 'uncovered source forms need successful non-NULL cases: ' + ', '.join(sorted(ids - covered)))
    return sorted(covered)


def sql_pairs(m):
    return [('arg_' + a['name'], TYPES[a['abi']][0]) for a in m['public_contract']['target']['arguments']]


def json_text(value):
    if isinstance(value, dict) and set(value) == {'json_array'}:
        require(isinstance(value['json_array'], list), 'json_array requires list')
        return json.dumps(value['json_array'], ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return value


def sql_literal(value):
    from common import literal
    if isinstance(value, dict) and set(value) == {'json_array'}:
        require(isinstance(value['json_array'], list), 'json_array requires list')
        def element(v):
            if isinstance(v,str): return 'CONVERT(' + literal(v) + ' USING utf8mb4)'
            if type(v) is bool: return 'TRUE' if v else 'FALSE'
            return literal(v)
        # Nested values use a JSON text input test; JSON_BUILD_ARRAY SQL support is
        # deliberately restricted to primitive members until live nested SQL is verified.
        require(not any(isinstance(v, (list, dict)) for v in value['json_array']), 'use explicit JSON text for nested SQL test inputs')
        return 'JSON_BUILD_ARRAY(' + ', '.join(element(v) for v in value['json_array']) + ')'
    return literal(value)
