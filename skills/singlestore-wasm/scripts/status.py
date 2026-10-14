#!/usr/bin/env python3
"""Machine-readable completion and fail-closed artifact export."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from common import manifest, verify_build


def run_snapshot(project, report):
    # Older reports used the public function name as their run directory.
    name = report.get('run_id', report['public_function'])
    if not isinstance(name, str) or not name or name in ('.', '..') or Path(name).name != name or '\\' in name:
        raise ValueError('invalid DB run identifier')
    root = (project/'artifacts/runs').resolve()
    path = root/name
    if not path.resolve().is_relative_to(root):
        raise ValueError('DB run directory outside artifacts/runs')
    return path


def assess(project):
    if not (project/'artifacts').exists():
        return {'state':'not_run','exportable':False,'wasm_compile':'not_run',
                'base64_roundtrip':'not_run','db_verification':'not_run','semantic_verification':'not_run'}
    try:
        meta=verify_build(project)
        for stage in ('rust_tests','wasm_compile','base64_roundtrip'):
            if meta.get(stage)!='passed':raise ValueError('missing passed stage: '+stage)
        required={'module.wasm','module.wasm.b64','interface.wit.b64','register.sql','validate.sql','validate-errors.sql'}
        hashes=meta.get('artifact_hashes',{})
        if not required<=hashes.keys():raise ValueError('missing artifact hashes; rebuild with current tools')
        for name,digest in hashes.items():
            if Path(name).name!=name:raise ValueError('invalid artifact name')
            if hashlib.sha256((project/'artifacts'/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('artifact changed: '+name)
        m=manifest(project)
        if (m.get('local_verify') or m.get('shape') == 'f64-scalar') and meta.get('wasm_runtime')!='passed':raise ValueError('local Wasm verification missing')
        if m.get('shape') == 'f64-scalar' and 'numeric-verification.json' not in hashes:
            raise ValueError('numeric comparison evidence missing')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return {'state':'build_failed_or_stale','reason':str(exc),'exportable':False}
    result={'state':'local_passed_db_unverified','exportable':True,'wasm_sha256':meta['wasm_sha256'],
            'return_contracts':meta.get('return_contracts',[]),'static_return_validation':'passed' if meta.get('return_contracts') else 'unverified'}
    result['reference_verification'] = {'status': 'unverified', 'reason': 'no bound reference execution evidence'}
    if 'reference-verification.json' in hashes:
        result['reference_verification'] = json.loads((project/'artifacts/reference-verification.json').read_text())
    result['reference_sources'] = m.get('reference', {}).get('sources', [])
    result['input_contracts'] = m.get('input_contracts', {})
    result['condition_array'] = m.get('condition_array')
    result['semantic_verification'] = ('passed_for_manifest_cases' if
        result['reference_verification'].get('status') == 'passed' else 'unverified')
    if 'compatibility' in m:
        from compatibility import evaluate
        result['compatibility'] = evaluate(m['compatibility'])
        result['compatibility']['scope_basis'] = m['compatibility']['scope_basis']
    report=project/'artifacts/db-results-latest.json'
    if not report.exists():return result
    try:
        db=json.loads(report.read_text())
        # Every invocation binds evidence to the complete build, including SQL and tools.
        if db.get('build')!=meta:
            result['reason']='DB evidence belongs to another build';return result
        if meta.get('sql_public'):
            snapshot=run_snapshot(project,db)
            for name in ('register.sql','validate.sql','validate-errors.sql'):
                if (project/'artifacts'/name).read_bytes()!=(snapshot/name).read_bytes():
                    raise ValueError('SQL snapshot differs: '+name)
        expected=[c['id'] for c in m['cases']]+[c['id'] for f in m.get('fixtures',[]) for c in f['cases']]
        rows=db.get('cases',[])
        if (db.get('registration')=='passed' and db.get('execution')=='passed'
                and not db.get('failure') and not db.get('cleanup_errors')
                and all(db.get('sql_files',{}).get(name,{}).get('status')=='passed'
                        for name in ('register.sql','validate.sql','validate-errors.sql'))
                and sorted(r['id'] for r in rows)==sorted(expected)
                and rows and all(r.get('passed') is True for r in rows)):
            for contract in result['return_contracts']:contract['db_registration']='passed'
            result['runtime_paths']=db.get('runtime_paths',{})
            result.update(state='db_passed',db_cases=len(rows),database=db['database'],
                          server_version=db['preflight']['version'],function=db['public_function'])
        else:result.update(state='db_failed',exportable=False,reason='DB verification incomplete or failed')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result.update(state='db_failed',exportable=False,reason='unreadable DB evidence: '+str(exc))
    return result


def bundle(project,output,require_db=False):
    status=assess(project)
    if not status['exportable'] or (require_db and status['state']!='db_passed'):
        raise ValueError('export blocked: '+status['state'])
    meta=json.loads((project/'artifacts/build.json').read_text())
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(output.suffix+'.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for name in sorted(meta['artifact_hashes']):z.write(project/'artifacts'/name,name)
        z.write(project/'artifacts/build.json','build.json')
        z.writestr('status.json',json.dumps(status,indent=2)+'\n')
        if status['state']=='db_passed':
            z.write(project/'artifacts/db-results-latest.json','db-results.json')
            db=json.loads((project/'artifacts/db-results-latest.json').read_text())
            snapshot=run_snapshot(project,db)
            for file in sorted(snapshot.glob('*')):
                if file.is_file() and file.name != 'db-results.json':z.write(file,'verified-run/'+file.name)
    with zipfile.ZipFile(temp) as z:
        for name,digest in meta['artifact_hashes'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('ZIP artifact hash mismatch: '+name)
    temp.replace(output)
    status['bundle_artifact_hashes']='passed'
    return status


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path)
    ap.add_argument('--bundle',type=Path);ap.add_argument('--require-db',action='store_true');args=ap.parse_args()
    result=bundle(args.project,args.bundle,args.require_db) if args.bundle else assess(args.project)
    print(json.dumps(result,indent=2))
    if not result['exportable'] or (args.require_db and result['state']!='db_passed'):raise SystemExit(1)


if __name__=='__main__':main()
