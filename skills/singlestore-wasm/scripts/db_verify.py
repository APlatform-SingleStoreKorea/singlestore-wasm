#!/usr/bin/env python3
"""CREATE-only live verification of scalar and HANDLE projects; execute structured SQL."""
import argparse
import configparser
import datetime
import json
import hashlib
import shutil
import time
import uuid
from pathlib import Path
import pymysql
from common import manifest, identifier, verify_build, sql_statements, validation_sql, validation_file, scalar_matches
from aggregate import registrations, cases, fixture_plan, actual_matches, error_matches
from return_contracts import check_project
from inspect_wasm import inspect
from sql_files import read_statements, validation_items, file_evidence


def preflight_queries(database):
    database = identifier(database)
    return [('version', 'SELECT @@memsql_version, @@version, DATABASE()'),
            ('wasm_variables', "SHOW VARIABLES LIKE '%wasm%'"),
            ('max_allowed_packet', "SHOW VARIABLES LIKE 'max_allowed_packet'")] + [
        (kind + '_before', f'SHOW {kind.upper()} IN `{database}`')
        for kind in ('functions', 'aggregates', 'procedures', 'tables')]


def existing_object_names(preflight):
    return {str(cell).lower() for key in ('functions_before', 'aggregates_before', 'procedures_before', 'tables_before')
            for row in preflight[key] for cell in row}


def expected_user_error(exc, case, spec):
    return (bool(exc.args) and exc.args[0] == 2242 and 'expected_error' in case
            and case['expected_error'] in str(exc) and spec.get('error_message', '') in str(exc))


def plan(project, m, database, public):
    if m.get('kind') == 'handle-udaf':
        return {'registrations': registrations(project,m,database,public),
                'cases': cases(m,database,public), 'fixtures': fixture_plan(m,database,public)}
    raw, wrapper = sql_statements(project,database,public)
    return {'registrations': [{'name':identifier(public+'_core'),'kind':'FUNCTION','sql':raw},
                              {'name':public,'kind':'FUNCTION','sql':wrapper}],
            'cases':[{'case':case,'sql':sql} for case,sql in validation_sql(m,database,public)], 'fixtures':[]}


def snapshot_sql(out,snapshot):
    evidence={}
    for name in ('register.sql','validate.sql','validate-errors.sql'):
        shutil.copyfile(out/name,snapshot/name)
        original=(out/name).read_bytes(); copied=(snapshot/name).read_bytes()
        if original!=copied:raise ValueError('SQL snapshot differs: '+name)
        evidence[name]={'status':'passed','sha256':hashlib.sha256(original).hexdigest(),
                        'snapshot_sha256':hashlib.sha256(copied).hexdigest()}
    return evidence


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project',type=Path);ap.add_argument('--config',type=Path,required=True)
    ap.add_argument('--database',default='t');ap.add_argument('--name')
    ap.add_argument('--cleanup',action='store_true',help='Drop only objects created by this invocation, including after failures')
    ns=ap.parse_args();project=ns.project.resolve();m=manifest(project);database=identifier(ns.database)
    meta=verify_build(project)
    if not meta.get('sql_public'):raise ValueError('rebuild with current tools to bind SQL names')
    public=identifier(meta['sql_public'])
    if (ns.name and ns.name!=public) or meta.get('sql_database')!=database:
        raise ValueError('SQL name/database differs from build; rebuild with --sql-name/--database')
    if not public.startswith('ssws_'):ap.error('use ssws_ prefix')
    if ns.config.stat().st_mode & 0o077:ap.error('credential file must have mode 600 or stricter')
    cfg=configparser.ConfigParser(interpolation=None);cfg.read(ns.config);c=cfg['client']
    if c['database']!=database:ap.error('database must match connection setting')
    b64=(project/'artifacts/module.wasm.b64').read_text().strip()
    def clean(exc):
        text=str(exc).replace(b64,'[WASM_BASE64]')
        for key in ('password','host','user'):
            if c.get(key):text=text.replace(c[key],'[REDACTED]')
        return text
    p=plan(project,m,database,public)
    static_contracts=check_project(project,m,inspect((project/'artifacts/module.wasm').read_bytes()),p['registrations'])
    objects=p['registrations']+p['fixtures']
    names=[x['name'].lower() for x in objects]
    if len(names)!=len(set(names)):raise ValueError('duplicate planned object names')
    run_id=public+'_'+uuid.uuid4().hex
    out=project/'artifacts';snapshot=out/'runs'/run_id;snapshot.mkdir(parents=True,exist_ok=False)
    report={'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'database':database,'public_function':public,'run_id':run_id,'build':meta,'created_objects':[],
            'registration':'not_run','execution':'not_run','cases':[],
            'static_return_contracts':static_contracts, 'show_create':{},
            'runtime_paths':{'merge':'unverified','serialize_deserialize':'unverified','null_input':'unverified','empty_input':'unverified'},
            'sql_files':{name:{'status':'not_run'} for name in ('register.sql','validate.sql','validate-errors.sql')}}
    path=out/f'db-results-{public}.json'
    def save():
        content=json.dumps(report,indent=2,ensure_ascii=False,default=str)+'\n'
        (snapshot/'db-results.json').write_text(content)
        path.write_text(content);(out/'db-results-latest.json').write_text(content)
    (snapshot/'sql-plan.json').write_text(json.dumps(p,indent=2)+'\n')
    (snapshot/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    report['sql_snapshot_hashes'] = snapshot_sql(out,snapshot)
    queries=preflight_queries(database)
    (snapshot/'preflight.sql').write_text(';\n'.join(sql for _,sql in queries)+';\n')
    stage='connect';db=None;save()
    try:
        db=pymysql.connect(host=c['host'],port=c.getint('port',3306),user=c['user'],password=c.get('password',''),
                           database=database,charset='utf8mb4',autocommit=True,connect_timeout=10,read_timeout=120,write_timeout=60)
        with db.cursor() as cur:
            stage='preflight';report['preflight']={}
            for key,sql in queries:
                cur.execute(sql);report['preflight'][key]=cur.fetchall()
            if set(names)&existing_object_names(report['preflight']):raise ValueError('object name collision; nothing changed')
            def create(obj):
                cur.execute(obj['sql']);report['created_objects'].append({'name':obj['name'],'kind':obj['kind']});save()
            stage='register.sql'
            registration_sql=read_statements(snapshot/'register.sql')
            if registration_sql and registration_sql[0]==f'USE `{database}`':cur.execute(registration_sql.pop(0))
            if registration_sql != [x['sql'] for x in p['registrations']]:raise ValueError('artifact SQL differs from checked registration plan')
            if len(registration_sql)!=len(p['registrations']):raise ValueError('registration file count mismatch')
            for obj,sql in zip(p['registrations'],registration_sql):
                stage='register:'+obj['name'];create(dict(obj,sql=sql))
            report['sql_files']['register.sql']=file_evidence(snapshot/'register.sql',len(registration_sql))
            stage='show_create'
            for obj in p['registrations']:
                cur.execute(f"SHOW CREATE {obj['kind']} `{database}`.`{obj['name']}`")
                report['show_create'][obj['name']]=cur.fetchall()
            report['registration']='passed';report['execution']='running';save()
            def check(item, grouped=False):
                case=item['case'];row={'id':case['id'],'passed':False};start=time.perf_counter()
                try:
                    cur.execute(item['sql']);values=cur.fetchall()
                    if grouped:
                        row.update(actual=[list(r) for r in values],expected=case['expected_rows'])
                        row['passed']=sorted(map(tuple,row['actual']),key=repr)==sorted(map(tuple,row['expected']),key=repr)
                    else:
                        row.update(actual=values[0][0],expected=case.get('expected'))
                        matches = (actual_matches(values[0][0],case) if m.get('kind') == 'handle-udaf'
                                   else scalar_matches(values[0][0],case,m))
                        row['passed']=('expected_error' not in case and matches
                                       and len(values[0])==3 and values[0][2]==1)
                except pymysql.MySQLError as exc:
                    row.update(error=clean(exc),error_code=exc.args[0] if exc.args else None)
                    row['passed']=bool(error_matches(exc,case) if m.get('kind')=='handle-udaf' else expected_user_error(exc,case,m))
                row['elapsed_seconds']=round(time.perf_counter()-start,6);report['cases'].append(row);save()
                if not row['passed']:raise ValueError('SQL verification failed: '+case['id'])
            stage='execute'
            for filename,errors in [('validate.sql',False),('validate-errors.sql',True)]:
                stage=filename
                report['sql_files'][filename]['status']='running';save()
                items=validation_items(snapshot/filename,p['cases'],errors)
                cur.execute(read_statements(snapshot/filename)[0])
                for item in items:check(item)
                report['sql_files'][filename]=file_evidence(snapshot/filename,len(items)+1);save()
            report['distributed_plans']={}
            for fixture in p['fixtures']:
                stage='fixture:'+fixture['name'];create(fixture)
                for sql in fixture['inserts']:cur.execute(sql)
                for item in fixture['checks']:
                    cur.execute('EXPLAIN '+item['sql']);report['distributed_plans'][item['case']['id']]=cur.fetchall()
                    check(item,True)
            report['execution']='passed' if report['cases'] and all(x['passed'] for x in report['cases']) else 'failed'
            report['runtime_paths']['empty_input']='passed' if any(c.get('rows')==[] for c in m['cases']) else 'unverified: no empty-input case'
            report['runtime_paths']['null_input']='passed' if any('args' in c and None in c['args'] for c in m['cases']) else 'unverified: no NULL-input case'
            if p['fixtures']:
                report['runtime_paths']['merge']='distributed queries passed; callback execution not directly instrumented'
                report['runtime_paths']['serialize_deserialize']='distributed queries passed; callback execution not directly instrumented'
            if report['execution']!='passed':raise ValueError('expected-result comparison failed; see report')
    except Exception as exc:
        report['failure']={'stage':stage,'error':clean(exc)}
        if stage in report['sql_files']:report['sql_files'][stage]['status']='failed'
        report['execution']='failed'
    finally:
        if db is not None:
            if ns.cleanup:
                report['cleanup_errors']=[]
                with db.cursor() as cur:
                    for obj in reversed(report['created_objects']):
                        try:cur.execute(f"DROP {obj['kind']} `{database}`.`{obj['name']}`")
                        except Exception as exc:report['cleanup_errors'].append(clean(exc))
                report['cleaned_up']=not report['cleanup_errors']
            db.close()
        save()
    print(json.dumps({'function':public,'registration':report['registration'],'execution':report['execution'],
                      'passed':sum(x['passed'] for x in report['cases']),'total':len(report['cases']),
                      'report':str(path),'failure':report.get('failure'),'cleaned_up':report.get('cleaned_up')},indent=2))
    if report.get('failure') or report.get('cleanup_errors'):raise SystemExit(1)


if __name__=='__main__':main()
