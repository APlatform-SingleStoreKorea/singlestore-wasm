"""Build and execute contract starters in an external directory; no DB claims."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from test_public_contract import SKILL, contract, integer
sys.path.insert(0,str(SKILL/'scripts'))
from typed import generate, generate_udaf


def run(project, *command):
    subprocess.run(command,cwd=project,check=True)


def save_cases(p,cases):
    m=json.loads((p/'function.json').read_text());m['cases']=cases;(p/'function.json').write_text(json.dumps(m,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--fetch',action='store_true');ns=ap.parse_args()
    root=ns.output.resolve();root.mkdir(parents=True,exist_ok=False)
    p=root/'fixed';generate(p,SKILL,'fixed',contract())
    (p/'src/logic.rs').write_text('''pub fn evaluate(label:&str,count:i32)->Result<i64,String>{ Ok(label.chars().count() as i64 + count as i64) }
#[cfg(test)] mod tests { #[test] fn independent(){assert_eq!(super::evaluate("한글",-1).unwrap(),1);} }
''')
    save_cases(p,[{'id':'unicode','args':['한글',-1],'expected':1},{'id':'null','args':[None,2],'expected':None}])
    q=root/'json';generate(q,SKILL,'json_forms',contract(True))
    (q/'src/logic.rs').write_text('''pub fn evaluate(p:&crate::json_input::Input)->Result<i64,String>{
let base=p.values[0].as_str().unwrap().chars().count() as i64 + p.values[1].as_i64().unwrap();
let extras=if p.form=="short" {p.defaults["x"].as_i64().unwrap()+p.defaults["y"].as_i64().unwrap()+p.defaults["z"].as_i64().unwrap()} else {p.values[2..].iter().map(|v|v.as_i64().unwrap()).sum()}; Ok(base+extras) }
#[cfg(test)] mod tests { #[test] fn independent(){let p=crate::json_input::Input {values:vec![serde_json::json!("ab"),serde_json::json!(3)],defaults:serde_json::json!({"x":1,"y":1,"z":1}),form:"short".into()};assert_eq!(super::evaluate(&p).unwrap(),8);} }
''')
    cases=[{'id':'short','args':[{'json_array':['ab',3]}],'expected':8}, {'id':'long','args':[{'json_array':['ab',3,4,5,6]}],'expected':20},
           {'id':'escaped','args':[{'json_array':['a,"b',-2]}],'expected':5}, {'id':'sql_null','args':[None],'expected':None}]
    for i,v in enumerate(['[]','["a"]','["a",1,2]','["a",1,2,3]','["a",1,2,3,4,5]', '["a",null]', '["a",true]', '["a",1.5]', '["a",2147483648]', '["a",1,]', '["a",01]', '{}','null','["a",1]x','["'+('x'*1100)+'",1]']):
        cases.append({'id':'invalid_'+str(i),'args':[v],'expected_error':'invalid_input'})
    save_cases(q,cases)
    # Nested values, exact i64, explicit JSON null and floats in a distinct schema.
    c=contract(True);j=c['json_arguments'][0];j['allowed_lengths']=[2];j['variants']=j['variants'][:1];j['variants'][0]['defaults']={}
    c['origin']['forms']=c['origin']['forms'][:1];c['mappings']=c['mappings'][:1]
    j['variants'][0]['items']=[{'type':'object','nullable':False,'properties':{'text':{'type':'string','nullable':False}, 'bounds':{'type':'array','nullable':False,'min_items':2,'max_items':2,'items':{'type':'integer','nullable':False,'min':-(2**63),'max':2**63-1}}}}, {'type':'number','nullable':True,'min':-10,'max':10}]
    z=root/'nested';generate(z,SKILL,'nested',c)
    (z/'src/logic.rs').write_text('''pub fn evaluate(p:&crate::json_input::Input)->Result<i64,String>{Ok(p.values[0]["bounds"][1].as_i64().unwrap())}
#[cfg(test)] mod tests { #[test] fn exact(){let p=crate::json_input::Input {values:vec![serde_json::json!({"bounds":[-2,9007199254740993i64]}),serde_json::Value::Null],defaults:serde_json::json!({}),form:"short".into()};assert_eq!(super::evaluate(&p).unwrap(),9007199254740993);} }
''')
    good='[{"text":"a,b\\\"c","bounds":[-2,9007199254740993]},null]'
    save_cases(z,[{'id':'exact_nested','args':[good],'expected':9007199254740993}, {'id':'float','args':[good.replace('null','-1.25')],'expected':9007199254740993}, {'id':'bad_bounds','args':[good.replace('9007199254740993','9223372036854775808')],'expected_error':'invalid_input'}, {'id':'bad_key','args':[good.replace('"text"','"wrong"')],'expected_error':'invalid_input'}])
    u=root/'udaf';c=contract(False,True)
    c['json_arguments']=[{'argument':'label','mode':'repeat','reason':'explicit repeat-array test','max_bytes':1000,'invalid':'error','min_items':0,'max_items':10,'items':{'type':'boolean','nullable':False}}]
    generate_udaf(u,SKILL,'mixed_aggregate',c)
    (u/'src/logic.rs').write_text('''#[derive(Default,Clone)] pub struct State(i64);
impl State {
pub fn add(&mut self,p:&crate::json_input::Input,count:i32)->Result<(),String>{self.0+=p.values.iter().filter(|v|v.as_bool()==Some(true)).count() as i64*count as i64; Ok(())}
pub fn merge(&mut self,b:&Self)->Result<(),String>{self.0+=b.0;Ok(())}
pub fn render(self)->String{self.0.to_string()}
pub fn encode(self)->Vec<u8>{self.0.to_le_bytes().to_vec()}
pub fn decode(b:&[u8])->Result<Self,String>{Ok(Self(i64::from_le_bytes(b.try_into().map_err(|_|"state")?)))} }
#[cfg(test)] mod tests {use super::*; #[test] fn state_roundtrip(){assert_eq!(State::decode(&State(7).encode()).unwrap().render(),"7");assert_eq!(State::default().render(),"0");}}
''')
    save_cases(u,[{'id':'empty','rows':[],'expected':'0'}, {'id':'mixed','rows':[['[true,false,true]',3],['[true]',2]],'expected':'8'}])
    import shutil
    (u/'scripts').mkdir()
    shutil.copyfile(Path(__file__).with_name('verify_mixed_udaf.py'),u/'scripts/verify.py')
    m=json.loads((u/'function.json').read_text());m['local_verify']='scripts/verify.py';(u/'function.json').write_text(json.dumps(m,indent=2)+'\n')
    legacy=root/'legacy'
    run(root,sys.executable,str(SKILL/'scripts/scaffold.py'),'--name','legacy','--shape','i64-unary','--output',str(legacy))
    (legacy/'src/logic.rs').write_text('pub fn evaluate(v:i64)->i64{v+1}\n#[cfg(test)] mod tests {#[test] fn value(){assert_eq!(super::evaluate(-2),-1);}}\n')
    save_cases(legacy,[{'id':'legacy','args':[-2],'expected':-1}])
    numeric=root/'numeric'
    run(root,sys.executable,str(SKILL/'scripts/scaffold.py'),'--name','numeric','--shape','f64-scalar','--arguments','v','--output',str(numeric))
    (numeric/'src/logic.rs').write_text('pub fn evaluate(v:f64)->f64{v+1.0}\n#[cfg(test)] mod tests {#[test] fn value(){assert_eq!(super::evaluate(-2.0),-1.0);}}\n')
    save_cases(numeric,[{'id':'numeric','args':[-2.0],'expected':-1.0}])
    for project in (p,q,z,u,legacy,numeric):
        if ns.fetch:run(project,'cargo','fetch','--target','wasm32-unknown-unknown')
        run(project,sys.executable,'-B',str(SKILL/'scripts/build.py'),str(project))
        from common import manifest
        from db_verify import plan
        from sql_files import read_statements
        meta=json.loads((project/'artifacts/build.json').read_text())
        assert meta['sql_database'] is None
        planned=plan(project,manifest(project),meta['sql_public'])
        assert read_statements(project/'artifacts/register.sql') == [r['sql'] for r in planned['registrations']]
        for path in (project/'artifacts').glob('*.sql'):
            assert not re.search(r'(?im)^\s*USE\s|`\w+`\s*\.\s*`',path.read_text()),path
    report={'static':'passed','wasm_build':'passed','scalar_wasm_execution':'passed','udaf_callbacks':'passed',
            'unqualified_sql':'passed','registration_plan_matches_files':'passed',
            'original_db':'not_run','singlestore_registration':'not_run','singlestore_calls':'not_run'}
    (root/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
