#!/usr/bin/env python3
"""Common scalar/HANDLE build. A failed attempt invalidates earlier outputs."""
import argparse
import base64
import datetime
import hashlib
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tomllib
from pathlib import Path
from common import manifest, source_fingerprint, tool_fingerprint, write_sql
from inspect_wasm import inspect
from return_contracts import check_project


def passed_test_count(output):
    count = sum(int(n) for n in re.findall(r'^test result: ok\. (\d+) passed;', output, re.MULTILINE))
    if count < 1:
        raise ValueError('cargo test ran no passing Rust tests; add meaningful tests before building')
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', type=Path)
    ap.add_argument('--database', default='t')
    ap.add_argument('--sql-name')
    args = ap.parse_args()
    project = args.project.resolve(); out = project / 'artifacts'; out.mkdir(exist_ok=True)
    metadata = {'build_status':'in_progress', 'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    def save(): (out/'build.json').write_text(json.dumps(metadata,indent=2)+'\n')
    save(); log=[]
    def run(cmd, env=None):
        p=subprocess.run(cmd,cwd=project,env=env,capture_output=True,text=True)
        log.extend(['$ '+' '.join(cmd),p.stdout,p.stderr]);(out/'build.log').write_text('\n'.join(log))
        if p.returncode: raise RuntimeError('command failed: '+cmd[0]+'; see '+str(out/'build.log'))
        return p.stdout.strip()
    try:
        m=manifest(project)
        check_project(project,m)
        if not (project/'Cargo.lock').exists():run(['cargo','generate-lockfile','--offline'])
        fingerprint=source_fingerprint(project);tools=tool_fingerprint()
        versions={'rustc':run(['rustc','-Vv']),'cargo':run(['cargo','-V']),
                  'host':platform.platform(),'python':platform.python_version()}
        count=passed_test_count(run(['cargo','test','--locked','--offline']))
        limits=m.get('build',{})
        memory=limits.get('memory_bytes',16777216);stack=limits.get('stack_bytes',262144)
        if type(memory) is not int or memory < 65536 or memory % 65536 or memory > 2**32:
            raise ValueError('memory_bytes must be pages within wasm32 range')
        if type(stack) is not int or not 0 < stack < memory:raise ValueError('invalid stack_bytes')
        env=dict(os.environ,RUSTFLAGS=f'-C link-arg=--max-memory={memory} -C link-arg=-zstack-size={stack}')
        run(['cargo','build','--release','--locked','--offline','--target','wasm32-unknown-unknown'],env)
        cargo=tomllib.loads((project/'Cargo.toml').read_text())
        crate=cargo.get('lib',{}).get('name',cargo['package']['name']).replace('-','_')
        binary=(project/'target/wasm32-unknown-unknown/release'/f'{crate}.wasm').read_bytes()
        inventory=inspect(binary);exports={e['name']:e for e in inventory['exports']}
        handle=m.get('kind')=='handle-udaf'
        if handle:
            from aggregate import signatures
            expected=signatures(m)
        else:
            if m['shape'] == 'f64-scalar':
                expected = {'evaluate': (['f64'] * len(m['arguments']), ['f64'])}
                wit = 'evaluate: func(' + ', '.join('arg-' + n.replace('_', '-') + ': float64' for n in m['arguments']) + ') -> float64'
                if (project/'interface.wit').read_text().strip() != wit:
                    raise ValueError('numeric interface does not match manifest')
            else:
                expected={'evaluate':(['i32']*4 if m['shape']=='string-pair-i64' else ['i64'],['i64'])}
        check_project(project,m,inventory)
        for name,(parameters,results) in expected.items():
            if name not in exports or exports[name].get('parameters')!=parameters or exports[name].get('results')!=results:
                raise ValueError('Wasm signature mismatch: '+name)
        if handle or m.get('shape')=='string-pair-i64':
            for name in ('memory','canonical_abi_realloc','canonical_abi_free'):
                if name not in exports:raise ValueError('Missing ABI export: '+name)
        if inventory['memories'][0]['max_pages']!=memory//65536:raise ValueError('memory ceiling mismatch')
        runtime='not_run'
        if m.get('shape') == 'f64-scalar':
            from verify_numeric import verify
            result = verify(project, binary, m)
            (out/'numeric-verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
            if result['status'] != 'passed':
                raise ValueError('numeric Wasm/reference comparison failed; see numeric-verification.json')
            runtime = 'passed'
        if m.get('local_verify'):
            script=(project/m['local_verify']).resolve()
            if not script.is_relative_to(project) or script.suffix!='.py':raise ValueError('local verifier must be project Python source')
            result=json.loads(run([sys.executable,'-B',str(script),str(project/'target/wasm32-unknown-unknown/release'/f'{crate}.wasm')]))
            if result.get('status')!='passed':raise ValueError('local Wasm execution failed')
            (out/'local-verification.json').write_text(json.dumps(result,indent=2)+'\n');runtime='passed'
        from reference import verify as verify_reference
        reference_result = verify_reference(project, m, project/'target/wasm32-unknown-unknown/release'/f'{crate}.wasm')
        (out/'reference-verification.json').write_text(json.dumps(reference_result, indent=2)+'\n')
        if reference_result['status'] == 'failed':
            raise ValueError('upstream/manifest/Wasm comparison failed; see reference-verification.json')
        if source_fingerprint(project)!=fingerprint or tool_fingerprint()!=tools:raise ValueError('inputs changed during build')
        encoded=base64.b64encode(binary)
        if base64.b64decode(encoded,validate=True)!=binary:raise ValueError('Base64 roundtrip failed')
        (out/'module.wasm').write_bytes(binary);(out/'module.wasm.b64').write_bytes(encoded+b'\n')
        wit=(project/'interface.wit').read_bytes();(out/'interface.wit.b64').write_bytes(base64.b64encode(wit)+b'\n')
        metadata.update(build_status='passed', built_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_fingerprint=fingerprint,tool_fingerprint=tools,versions=versions,target='wasm32-unknown-unknown',
            rustflags=env['RUSTFLAGS'],rust_tests='passed',rust_tests_passed=count,wasm_compile='passed',
            wasm_runtime=runtime,base64_roundtrip='passed',wasm_bytes=len(binary),base64_characters=len(encoded),
            wasm_sha256=hashlib.sha256(binary).hexdigest(),wit_sha256=hashlib.sha256(wit).hexdigest(),inventory=inventory)
        save()
        public=args.sql_name or 'ssws_'+m['name']+'_'+secrets.token_hex(4)
        generated=write_sql(project,args.database,public)
        regs=generated if handle else [{'sql':x} for x in generated]
        contracts=check_project(project,m,inventory,regs)
        (out/'return-contracts.json').write_text(json.dumps({'static':'passed','db':'not_run','returns':contracts},indent=2)+'\n')
        metadata.update(sql_database=args.database,sql_public=public,return_contracts=contracts)
        manual_files = []
        for name, relative in m.get('manual_sql', {}).items():
            path = (project/relative).resolve()
            if (not re.fullmatch(r'manual-[a-z-]+\.sql', name)
                    or not path.is_relative_to((project/'tests').resolve()) or not path.is_file()):
                raise ValueError('manual SQL must be a tests/ template and use a manual-*.sql output name')
            sql = path.read_text().replace('{{database}}', args.database).replace('{{public}}', public)
            (out/name).write_text(sql)
            manual_files.append(name)
        if handle and m.get('fixtures'):
            from aggregate import fixture_plan
            blocks = ['-- NOT EXECUTED here. User-only fixture setup and checks. Existing names cause CREATE to fail.']
            for fixture in fixture_plan(m, args.database, public):
                blocks.extend([fixture['sql']+';']+[s+';' for s in fixture['inserts']])
                for check in fixture['checks']:
                    blocks.append('-- Expected rows: '+json.dumps(check['case']['expected_rows']))
                    blocks.append(check['sql']+';')
            (out/'manual-fixtures.sql').write_text('\n'.join(blocks)+'\n')
            manual_files.append('manual-fixtures.sql')
        metadata['artifact_hashes']={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in
            ('module.wasm','module.wasm.b64','interface.wit.b64','register.sql','validate.sql','validate-errors.sql','return-contracts.json','reference-verification.json')}
        if handle:metadata['artifact_hashes']['sql-plan.json']=hashlib.sha256((out/'sql-plan.json').read_bytes()).hexdigest()
        for name in manual_files:
            metadata['artifact_hashes'][name] = hashlib.sha256((out/name).read_bytes()).hexdigest()
        for name in ('numeric-verification.json', 'local-verification.json'):
            if (name == 'numeric-verification.json' and m.get('shape') == 'f64-scalar') or (name == 'local-verification.json' and m.get('local_verify')):
                metadata['artifact_hashes'][name] = hashlib.sha256((out/name).read_bytes()).hexdigest()
        save()
    except Exception as exc:
        metadata.update(build_status='failed',failure=str(exc));save();raise
    print(json.dumps({k:metadata[k] for k in ('build_status','rust_tests_passed','wasm_compile','wasm_runtime','base64_roundtrip','wasm_bytes')},indent=2))


if __name__=='__main__':main()
