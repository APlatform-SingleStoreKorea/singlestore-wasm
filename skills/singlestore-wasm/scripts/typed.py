"""Mixed fixed SQL arguments and JSON transport, Canonical scalar i64 result.

No source algorithm is supplied. The authored logic returns Result<i64, String>.
"""
import json
import shutil
from public_contract import TYPES, validate, argument_types, json_text, require


def generate(project, skill, name, c):
    validate(c)
    require(c['target']['sql_null'] == 'propagate', 'typed scalar currently supports SQL NULL propagation only')
    project.mkdir(parents=True, exist_ok=False)
    (project/'src').mkdir()
    (project/'src/public-contract.json').write_text(json.dumps(c,indent=2)+'\n')
    for filename in ('Cargo.toml', 'rust-toolchain.toml'):
        (project/filename).write_text((skill/'templates/rust'/filename).read_text().replace('{{name}}', name))
    arrays = {j['argument']: j for j in c.get('json_arguments', [])}
    if arrays:
        with (project/'Cargo.toml').open('a') as f:
            f.write('\n[dependencies]\nserde_json = { version = "=1.0.140", features = ["arbitrary_precision"] }\n')
        shutil.copyfile(skill/'templates/typed/json_input.rs', project/'src/json_input.rs')
    # Reuse the inspected legacy allocator and string lifting ownership contract.
    abi = (skill/'templates/rust/string_pair.rs').read_text()
    abi = abi[:abi.index('    #[export_name = "evaluate"]')]
    params = []; calls = []; decode = []; wit = []; logical = []
    for i,a in enumerate(c['target']['arguments']):
        n = 'arg_' + a['name']; t = a['abi']
        wit.append('arg-' + a['name'].replace('_','-') + ': ' + TYPES[t][2])
        if t == 'string':
            params += [f'p{i}: *mut u8', f'n{i}: usize']; decode.append(f'let {n} = lift(p{i}, n{i});')
        else: params.append(n + ': ' + TYPES[t][1])
        if a['name'] in arrays:
            spec = 'include_str!("public-contract.json"), ' + json.dumps(a['name'])
            decode.append(f'let {n} = match crate::json_input::parse(&{n}, {spec}) {{ Ok(v) => v, Err(_) => return i64::MIN }};')
            logical.append(n + ': &crate::json_input::Input'); calls.append('&'+n)
        else:
            logical.append(n + ': ' + ('&str' if t == 'string' else TYPES[t][1])); calls.append('&'+n if t == 'string' else n)
    abi += '    #[export_name = "evaluate"]\n    pub unsafe extern "C" fn evaluate_export(' + ', '.join(params) + ') -> i64 {\n'
    abi += '\n'.join('        '+x for x in decode)
    abi += '\n        crate::logic::evaluate(' + ', '.join(calls) + ').unwrap_or(i64::MIN)\n    }\n}\n'
    (project/'src/lib.rs').write_text('pub mod logic;\n' + ('pub mod json_input;\n' if arrays else '') + abi)
    (project/'src/logic.rs').write_text('// Implement public SQL behavior; internal-only arguments stay here.\n' +
        'pub fn evaluate(' + ', '.join(logical) + ') -> Result<i64, String> {\n    compile_error!("Implement source SQL semantics and independent tests");\n}\n')
    (project/'interface.wit').write_text('evaluate: func(' + ', '.join(wit) + ') -> s64\n')
    from return_contracts import contract
    m = {'name': name, 'shape': 'typed-scalar', 'target_version': c['target']['version'], 'public_contract': c,
         'null_policy': 'propagate', 'error_sentinel': -(2**63), 'error_message': 'invalid_input',
         'returns': contract('s64','BIGINT',True), 'cases': []}
    (project/'function.json').write_text(json.dumps(m, indent=2, ensure_ascii=False)+'\n')


def validate_cases(m):
    from common import finite_number
    types = argument_types(m)
    require(m.get('null_policy') == 'propagate' and m['public_contract']['target']['sql_null'] == 'propagate', 'typed scalar SQL NULL propagation required')
    require(m.get('error_sentinel') == -(2**63) and m.get('error_message') == 'invalid_input', 'typed scalar reserves i64::MIN for invalid_input')
    require(m.get('target_version') == m['public_contract']['target']['version'], 'target version mismatch')
    cases = m.get('cases'); require(isinstance(cases,list) and bool(cases), 'independent cases required')
    ids = set()
    for c in cases:
        import re
        require(isinstance(c.get('id'),str) and re.fullmatch(r'[A-Za-z0-9_-]+', c['id']) and c['id'] not in ids, 'unique valid test id required'); ids.add(c['id'])
        require(isinstance(c.get('args'),list) and len(c['args']) == len(types), 'target SQL arity mismatch')
        for v,t in zip(c['args'],types):
            v = json_text(v)
            if v is None: continue
            if t == 'string': require(isinstance(v,str), 'text input required')
            elif t == 'f64': require(finite_number(v), 'finite double input required')
            else:
                bits = 32 if t == 's32' else 64
                require(type(v) is int and -(2**(bits-1)) <= v < 2**(bits-1), 'integer SQL range exceeded')
        require(('expected' in c) != ('expected_error' in c), 'one expectation required')
        if 'expected_error' in c: require(c['expected_error'] == 'invalid_input', 'unsupported error mapping')
        else: require(c['expected'] is None or type(c['expected']) is int and -(2**63) < c['expected'] < 2**63, 'expected result outside supported non-sentinel i64')
        if any(v is None for v in c['args']): require('expected' in c and c['expected'] is None, 'SQL NULL must propagate before evaluation')
    from public_contract import check_form_coverage
    check_form_coverage(m)
    return m


def verify(project, binary, m):
    import wasmtime
    engine = wasmtime.Engine(); store = wasmtime.Store(engine)
    instance = wasmtime.Instance(store, wasmtime.Module(engine,binary), [])
    ex = instance.exports(store); rows = []; deferred = []
    for case in m['cases']:
        if any(v is None for v in case['args']): deferred.append(case['id']); continue
        args = []
        for v,t in zip(case['args'], argument_types(m)):
            v = json_text(v)
            if t == 'string':
                data = v.encode('utf-8'); ptr = ex['canonical_abi_realloc'](store,0,0,1,len(data))
                ex['memory'].write(store,data,ptr); args += [ptr,len(data)]
            else: args.append(v)
        actual = ex['evaluate'](store,*args)
        expected = -(2**63) if 'expected_error' in case else case['expected']
        rows.append({'id':case['id'], 'actual':actual, 'passed':actual == expected})
    return {'status':'passed' if rows and all(r['passed'] for r in rows) else 'failed', 'cases':rows,
            'null_cases_deferred_to_sql':deferred, 'sql_error_mapping':'db_unverified'}


def generate_udaf(project, skill, name, c):
    """Keep existing HANDLE lifecycle; replace only row argument transport."""
    validate(c)
    require(c['target']['sql_null'] == 'reject', 'HANDLE profile requires SQL NOT NULL inputs')
    # Build shared files without weakening the scalar profile's SQL NULL rule.
    import copy
    temp = copy.deepcopy(c); temp['target']['sql_null'] = 'propagate'
    generate(project,skill,name,temp)
    scalar = (project/'src/lib.rs').read_text()
    start = scalar.index('pub unsafe extern "C" fn evaluate_export(')
    signature = scalar[start:].split(') -> i64',1)[0].split('evaluate_export(',1)[1]
    body = scalar[start:].split('{',1)[1].split('crate::logic::evaluate(',1)[0]
    body = body.replace('return i64::MIN', 'panic!("invalid_input")')
    call = scalar[start:].split('crate::logic::evaluate(',1)[1].split(').unwrap_or',1)[0]
    lib = (skill/'templates/json-array-udaf/src/lib.rs').read_text()
    lib = lib.replace('pub mod json_array;', 'pub mod json_input;' if c.get('json_arguments') else '')
    lift = '    unsafe fn lift(p:*mut u8,n:usize)->String { String::from_utf8(input(p,n)).expect("invalid_utf8") }\n'
    begin = lib.index('    #[export_name="agg-step"]')
    end = lib.index('    #[export_name="agg-merge"]')
    lib = lib[:begin] + lift + '    #[export_name="agg-step"] pub unsafe extern "C" fn step(h:i32,' + signature + ')->i32 {\n' + body + '(*(h as *mut State)).add(' + call + ').expect("invalid_input"); h\n    }\n' + lib[end:]
    (project/'src/lib.rs').write_text(lib)
    (project/'src/public-contract.json').write_text(json.dumps(c,indent=2)+'\n')
    wit=(skill/'templates/json-array-udaf/interface.wit').read_text()
    params=(project/'interface.wit').read_text().split('func(',1)[1].split(') ->',1)[0]
    wit=wit.replace('s: state, conditions: string', 's: state, '+params)
    (project/'interface.wit').write_text(wit)
    manifest=json.loads((skill/'templates/json-array-udaf/function.json').read_text())
    manifest.update(name=name, public_contract=c, target_version=c['target']['version'],
                    argument_types=[a['abi'] for a in c['target']['arguments']], json_array_input=False)
    manifest.pop('condition_array',None)
    from return_contracts import contract
    manifest['input_contracts']={str(i):contract('string','TEXT',False,'utf8mb4','utf8mb4_bin') for i,a in enumerate(c['target']['arguments']) if a['abi']=='string'}
    (project/'function.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (project/'src/logic.rs').write_text('compile_error!("Implement State Default+Clone, add with the generated step argument types, merge, render, encode, decode and independent tests; choose original empty-group semantics");\n')
