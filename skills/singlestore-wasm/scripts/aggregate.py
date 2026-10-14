"""Data-driven legacy Canonical HANDLE UDAF profile (numeric and explicit TEXT inputs).

Algorithms and state serialization belong to each Rust project, not this module.
SQL remains structured statements from generation through execution.
"""
import base64
import math
import re

TYPES = {'s64': ('BIGINT', 'i64'), 'u64': ('BIGINT UNSIGNED', 'i64'),
         's32': ('INT', 'i32'), 'u32': ('INT UNSIGNED', 'i32'), 'f64': ('DOUBLE', 'f64'),
         'string': ('TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin', 'i32')}
from return_contracts import resolve, sql_type, check_project
CALLBACKS = ('initialize', 'iterate', 'merge', 'terminate', 'serialize', 'deserialize')
OPTIONAL = ('copymerge', 'clone', 'destroy')


def ident(value):
    from common import identifier
    return identifier(value)


def value(value, kind):
    if kind == 'string':
        from common import string_literal
        if isinstance(value, dict) and set(value) == {'json_array'}:
            def element(v):
                if v is None: return 'NULL'
                if type(v) is bool: return 'TRUE' if v else 'FALSE'
                if type(v) is int: return str(v)
                raise ValueError('JSON_BUILD_ARRAY test elements must be integer, boolean or NULL')
            if not isinstance(value['json_array'], list): raise ValueError('json_array must be a list')
            return 'JSON_BUILD_ARRAY('+', '.join(element(v) for v in value['json_array'])+')'
        if not isinstance(value, str): raise ValueError('string input requires text or json_array')
        return string_literal(value)
    if kind == 'f64':
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError('expected finite f64')
    else:
        width = 64 if kind.endswith('64') else 32
        low, high = (0, 2**width) if kind.startswith('u') else (-(2**(width-1)), 2**(width-1))
        if type(value) is not int or not low <= value < high:
            raise ValueError('argument outside ' + kind)
    return str(value)


def validate(m):
    if m.get('schema_version') != 1 or m.get('kind') != 'handle-udaf':
        raise ValueError('unsupported aggregate schema')
    ident(m['name'])
    types = m['argument_types']
    if not isinstance(types, list) or not types or any(t not in TYPES for t in types):
        raise ValueError('unsupported HANDLE argument type')
    input_declarations(m)
    array = m.get('condition_array')
    if m.get('json_array_input') and array is None:
        raise ValueError('decide condition_array input policy for this request before building')
    if array is not None:
        if (not isinstance(array, dict) or type(array.get('argument_index')) is not int
                or not 0 <= array['argument_index'] < len(types)
                or types[array['argument_index']] != 'string'
                or any(type(array.get(k)) is not int for k in ('min_items','max_items','max_json_bytes'))
                or not 0 <= array['min_items'] <= array['max_items']
                or not 1 <= array['max_json_bytes'] <= 65535
                or array.get('sql_null') != 'not_null'
                or array.get('json_null') not in ('skip_row','reject','preserve')
                or not isinstance(array.get('empty_result'), str)):
            raise ValueError('invalid condition_array input policy')
        if len(m['aggregates']) != 1:
            raise ValueError('condition_array uses one public aggregate, not per-length variants')
    variants = m['aggregates']
    if not variants: raise ValueError('aggregate variants required')
    for suffix, variant in variants.items():
        if suffix and not re.fullmatch(r'_[a-z][a-z0-9_]*', suffix): raise ValueError('invalid suffix')
        ident('ssws_' + m['name'] + suffix)
        resolve(m, variant)
        cb = variant['callbacks']
        if not set(CALLBACKS) <= cb.keys() or set(cb) - set(CALLBACKS + OPTIONAL):
            raise ValueError('invalid callback set')
        if set(cb) & set(OPTIONAL) and not set(OPTIONAL) <= cb.keys():
            raise ValueError('copymerge/clone/destroy must be supplied together')
        if any(not re.fullmatch(r'[a-z][a-z0-9-]*', export) for export in cb.values()):
            raise ValueError('invalid WIT callback name')
    cases = m.get('cases')
    if not isinstance(cases, list) or not cases: raise ValueError('independent cases required')
    ids = set()
    for case in cases:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', case['id']) or case['id'] in ids:
            raise ValueError('invalid or duplicate test id')
        ids.add(case['id'])
        if case.get('variant', '') not in variants: raise ValueError('unknown variant')
        if ('expected' in case) == ('expected_error' in case): raise ValueError('one expectation required')
        if not isinstance(case.get('rows'), list): raise ValueError('rows required')
        for row in case['rows']:
            if len(row) != len(types): raise ValueError('argument arity mismatch')
            for v, t in zip(row, types): value(v, t)
        if 'expected_error' in case:
            e = case['expected_error']
            if type(e.get('code')) is not int or not e.get('contains') or any(not isinstance(x,str) or not x for x in e['contains']):
                raise ValueError('expected_error requires code and message fragments')
        else:
            expected = case['expected']; ret = resolve(m, variants[case.get('variant', '')])['abi']
            if ret == 'option-s64':
                if expected is not None: value(expected, 's64')
            elif ret == 'string':
                if not isinstance(expected,str): raise ValueError('string expectation required')
                expected.encode('utf-8')
            elif ret == 'bytes':
                if not isinstance(expected, dict) or set(expected) != {'hex'}: raise ValueError('bytes expectation needs hex')
                bytes.fromhex(expected['hex'])
            else: value(expected, ret)
            tolerance = case.get('tolerance')
            if tolerance is not None and (ret != 'f64' or type(tolerance) not in (int,float) or tolerance < 0 or not math.isfinite(tolerance)):
                raise ValueError('tolerance only for finite f64 results')
    for fixture in m.get('fixtures', []):
        ident(fixture['id'])
        columns = fixture['columns']
        for n,t in columns.items(): ident(n); TYPES[t]
        if not set(fixture['shard_by']) <= columns.keys(): raise ValueError('invalid shard key')
        for row in fixture['rows']:
            if len(row) != len(columns): raise ValueError('fixture arity mismatch')
            for v,t in zip(row,columns.values()): value(v,t)
        for case in fixture['cases']:
            if case['id'] in ids: raise ValueError('duplicate test id')
            ids.add(case['id']); ident(case['id'])
            if case.get('variant','') not in variants: raise ValueError('unknown variant')
            if len(case['arguments']) != len(types): raise ValueError('fixture argument count')
            for arg,t in zip(case['arguments'],types):
                if set(arg)=={'column'}:
                    if arg['column'] not in columns or columns[arg['column']]!=t: raise ValueError('fixture argument type')
                elif set(arg)=={'literal'}: value(arg['literal'],t)
                else: raise ValueError('invalid fixture expression')
            if not set(case['group_by']) <= columns.keys(): raise ValueError('invalid grouping')
            if case.get('grouping','group') not in ('group','cube','rollup'): raise ValueError('invalid grouping mode')
            if 'where_lt' in case:
                name,limit=case['where_lt']; value(limit,columns[name])
            if not isinstance(case.get('expected_rows'),list) or not case['expected_rows']:
                raise ValueError('fixture expected rows required')
            if any(len(row)!=len(case['group_by'])+1 for row in case['expected_rows']): raise ValueError('expected row arity')
    return m


def signatures(m):
    expected = {'canonical_abi_realloc': (['i32']*4,['i32']), 'canonical_abi_free': (['i32']*3,[])}
    for variant in m['aggregates'].values():
        ret = resolve(m, variant)['abi']
        sigs = {'initialize':([],['i32']), 'iterate':(['i32']+sum((['i32','i32'] if t=='string' else [TYPES[t][1]] for t in m['argument_types']), []),['i32']),
                'merge':(['i32','i32'],['i32']), 'terminate':(['i32'],[TYPES[ret][1] if ret in TYPES else 'i32']),
                'serialize':(['i32'],['i32']), 'deserialize':(['i32','i32'],['i32']),
                'copymerge':(['i32','i32'],['i32']), 'clone':(['i32'],['i32']), 'destroy':(['i32'],['i32'])}
        for role, export in variant['callbacks'].items():
            if export in expected and expected[export]!=sigs[role]: raise ValueError('conflicting callback signature')
            expected[export]=sigs[role]
    return expected


def input_declarations(m):
    contracts = m.get('input_contracts', {})
    expected_keys = {str(i) for i,t in enumerate(m['argument_types']) if t == 'string'}
    if set(contracts) != expected_keys:
        raise ValueError('each string input requires an explicit input_contracts entry')
    result = []
    for i,t in enumerate(m['argument_types']):
        if t == 'string':
            expected = {'abi':'string','sql_type':'TEXT','charset':'utf8mb4','collation':'utf8mb4_bin','nullable':False}
            if contracts[str(i)] != expected:
                raise ValueError('HANDLE string input contract requires explicit TEXT utf8mb4 utf8mb4_bin NOT NULL; JSON/LONGTEXT are not interchangeable')
            if m.get('target_version') != '9.1.1':
                raise ValueError('string input profile targets SingleStore 9.1.1')
            result.append(sql_type(expected))
        else: result.append(TYPES[t][0]+' NOT NULL')
    return result


def registrations(project, m, database, public):
    b64=(project/'artifacts/module.wasm.b64').read_text().strip()
    wit=base64.b64encode((project/'interface.wit').read_bytes()).decode()
    check_project(project,m)
    items=[]
    for suffix,variant in m['aggregates'].items():
        name=ident(public+suffix)
        sql=f'CREATE AGGREGATE `{ident(database)}`.`{name}` ('+', '.join(input_declarations(m))+')\n'
        sql+=f"RETURNS {sql_type(resolve(m,variant))}\nWITH STATE HANDLE\nAS WASM FROM BASE64 '{b64}'\nWITH WIT FROM BASE64 '{wit}'\n"
        sql+='\n'.join(role.upper()+' WITH '+export.replace('-','_') for role,export in variant['callbacks'].items())
        items.append({'name':name,'kind':'AGGREGATE','suffix':suffix,'sql':sql})
    check_project(project,m,registrations=items)
    return items


def cases(m, database, public):
    result=[]
    for case in m['cases']:
        types=m['argument_types']; columns=[f'a{i}' for i in range(len(types))]
        selects=['SELECT '+', '.join(value(v,t)+f' AS {n}' for v,t,n in zip(row,types,columns)) for row in case['rows']]
        if selects: source=' UNION ALL '.join(selects)
        else: source='SELECT * FROM (SELECT '+', '.join((value('[]',t) if t=='string' else '0')+' AS '+n for n,t in zip(columns,types))+') AS empty_source WHERE 1=0'
        name=ident(public+case.get('variant',''))
        sql=f'SELECT `{ident(database)}`.`{name}`('+', '.join(columns)+f') AS actual FROM ({source}) AS events'
        if 'expected' in case:
            expected=case['expected']; ret=resolve(m,m['aggregates'][case.get('variant','')])['abi']
            if expected is None: literal='NULL'
            elif ret=='string':
                from common import string_literal
                literal=string_literal(expected)
            elif ret=='bytes': literal="X'"+bytes.fromhex(expected['hex']).hex()+"'"
            else: literal=value(expected,'s64' if ret=='option-s64' else ret)
            comparison='actual <=> expected'
            if 'tolerance' in case:
                comparison=f"COALESCE(ABS(actual - expected) <= {value(case['tolerance'],'f64')}, 0)"
            sql=f'SELECT actual, expected, ({comparison}) AS passed FROM (SELECT actual, {literal} AS expected FROM ({sql}) AS measured) AS checked'
        result.append({'case':case,'sql':sql})
    return result


def fixture_plan(m, database, public):
    fixtures=[]
    for fixture in m.get('fixtures',[]):
        name=ident(public+'_'+fixture['id']); columns=fixture['columns']
        table=f'`{ident(database)}`.`{name}`'
        create=f'CREATE ROWSTORE TABLE {table} ('+', '.join(f'`{n}` {TYPES[t][0]} NOT NULL' for n,t in columns.items())
        create+=', SHARD KEY('+', '.join('`'+n+'`' for n in fixture['shard_by'])+'))'
        inserts=[]
        for i in range(0,len(fixture['rows']),500):
            rows=fixture['rows'][i:i+500]
            inserts.append(f'INSERT INTO {table} VALUES '+','.join('('+','.join(value(v,t) for v,t in zip(row,columns.values()))+')' for row in rows))
        checks=[]
        for case in fixture['cases']:
            args=[f"`{arg['column']}`" if 'column' in arg else value(arg['literal'],t) for arg,t in zip(case['arguments'],m['argument_types'])]
            groups=', '.join('`'+n+'`' for n in case['group_by'])
            sql=f"SELECT {groups}, `{database}`.`{ident(public+case.get('variant',''))}`("+', '.join(args)+f') AS actual FROM {table}'
            if 'where_lt' in case:
                col,limit=case['where_lt'];sql+=f' WHERE `{col}` < {value(limit,columns[col])}'
            mode=case.get('grouping','group')
            sql+=' GROUP BY '+(groups if mode=='group' else mode.upper()+'('+groups+')')
            checks.append({'case':case,'sql':sql})
        fixtures.append({'name':name,'kind':'TABLE','sql':create,'inserts':inserts,'checks':checks})
    return fixtures


def actual_matches(actual, case):
    expected=case['expected']
    if isinstance(expected,dict) and 'hex' in expected: expected=bytes.fromhex(expected['hex'])
    if 'tolerance' in case: return actual is not None and abs(actual-expected)<=case['tolerance']
    return actual==expected


def error_matches(exc, case):
    expected=case.get('expected_error')
    return (isinstance(expected,dict) and exc.args and exc.args[0] != 1064 and exc.args[0]==expected['code']
            and all(fragment in str(exc) for fragment in expected['contains']))
