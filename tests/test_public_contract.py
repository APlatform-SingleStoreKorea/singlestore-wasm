"""Contract regressions; generated projects are always outside the checkout."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]/'skills/singlestore-wasm'
sys.path.insert(0,str(SKILL/'scripts'))
from public_contract import validate, matches, sql_literal
from typed import generate, generate_udaf
from compatibility import validate_manifest
from common import manifest
from return_contracts import check_project


def integer(nullable=False):
    return {'type':'integer','nullable':nullable,'min':-2147483648,'max':2147483647}


def contract(json_mode=False, udaf=False):
    source_args=[{'name':n,'type':t,'meaning':n,'default':None} for n,t in [('label','text'),('count','integer')]]
    c={'version':1,'origin':{'database':'test specification','version':'1','documentation':'tests/test_public_contract.py',
       'forms':[{'id':'short','arguments':source_args,'returns':'integer'}],
       'nulls':'propagate','empty':'empty label allowed','errors':'invalid input rejected','boundaries':'signed 32 bit count'},
       'target':{'version':'9.1.1','capability_evidence':'explicit test interface; no product overload conclusion',
                 'arguments':[{'name':'label','abi':'string','meaning':'label'}, {'name':'count','abi':'s32','meaning':'count'}],
                 'sql_null':'reject' if udaf else 'propagate'},
       'mappings':[{'form':'short','bindings':{'label':{'argument':'label'},'count':{'argument':'count'}},
                    'source_call':"source('a', 2)",'target_call':"target('a', 2)"}],
       'internal':[{'name':'trusted','expression':'false','evidence':'synthetic private control for non-exposure regression'}],
       'representations':[], 'json_arguments':[], 'differences':[]}
    if json_mode:
        c['target']['arguments']=[{'name':'payload','abi':'string','meaning':'public arguments only'}]
        c['origin']['forms'].append({'id':'long','arguments':source_args+[{'name':n,'type':'integer','meaning':n,'default':None} for n in ('x','y','z')],'returns':'integer'})
        c['mappings']=[]
        for f in c['origin']['forms']:
            c['mappings'].append({'form':f['id'],'bindings':{a['name']:{'argument':'payload','index':i} for i,a in enumerate(f['arguments'])},
                                  'source_call':'source(label, count, ...)','target_call':'target(JSON_BUILD_ARRAY(label, count, ...))'})
        c['json_arguments']=[{'argument':'payload','mode':'forms','reason':'explicit test JSON interface', 'max_bytes':1024,'invalid':'error', 'allowed_lengths':[2,5],
          'variants':[{'form':'short','items':[{'type':'string','nullable':False},integer()], 'defaults':{'x':1,'y':1,'z':1}},
                      {'form':'long','items':[{'type':'string','nullable':False}]+[integer()]*4,'defaults':{}}]}]
    return c


class PublicContractTest(unittest.TestCase):
    def test_fixed_order_and_internal_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'project';generate(p,SKILL,'fixed',contract())
            self.assertEqual((p/'interface.wit').read_text(),'evaluate: func(arg-label: string, arg-count: s32) -> s64\n')
            self.assertNotIn('trusted',(p/'interface.wit').read_text())
            m=json.loads((p/'function.json').read_text());m['cases']=[{'id':'one','args':['a',2],'expected':3}]
            (p/'function.json').write_text(json.dumps(m));manifest(p);check_project(p,m)
            with self.assertRaises(FileExistsError):generate(p,SKILL,'fixed',contract())
    def test_contract_change_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'project';generate(p,SKILL,'fixed',contract())
            m=json.loads((p/'function.json').read_text())
            m['public_contract']['origin']['version']='2'
            with self.assertRaisesRegex(ValueError,'generated input contract differs'):check_project(p,m)
    def test_sql_wrapper_argument_tamper_rejected(self):
        from return_contracts import check_sql, contract as returns
        m={'shape':'typed-scalar','public_contract':contract(),'name':'test'}
        with self.assertRaisesRegex(ValueError,'SQL public arguments differ'):
            check_sql(m,m,returns('s64','BIGINT',True),'CREATE FUNCTION f(arg_count INT NULL, arg_label TEXT NULL)\nRETURNS BIGINT NULL AS','test')
    def test_internal_cannot_be_public(self):
        c=contract();c['internal'][0]['name']='count'
        with self.assertRaisesRegex(ValueError,'internal argument exposed'): validate(c)
    def test_exact_lengths_and_separate_arities(self):
        c=contract(True);validate(c)
        self.assertEqual([len(f['arguments']) for f in c['origin']['forms']],[2,5])
        self.assertEqual(len(c['target']['arguments']),1)
        c['json_arguments'][0]['allowed_lengths']=[2,3,4,5]
        with self.assertRaisesRegex(ValueError,'exactly match'):validate(c)
    def test_null_types_bounds(self):
        self.assertFalse(matches(None,integer()));self.assertTrue(matches(None,integer(True)))
        for v in (True,'1',1.5,2147483648):self.assertFalse(matches(v,integer()))
        self.assertTrue(matches(-3,integer()))
    def test_legacy_manifest_unmodified(self):
        m={'shape':'string-pair-i64'};self.assertIsNone(validate_manifest(m));self.assertEqual(m,{'shape':'string-pair-i64'})
    def test_sql_json_primitives(self):
        sql=sql_literal({'json_array':['a,b',-1,1.5,True,None]})
        self.assertEqual(sql,"JSON_BUILD_ARRAY(CONVERT(X'612c62' USING utf8mb4), -1, 1.5, TRUE, NULL)")
        with self.assertRaisesRegex(ValueError,'explicit JSON text'):sql_literal({'json_array':[[1]]})
    def test_rejects_unresolved_difference(self):
        c=contract();c['differences']=[{'aspect':'semantics','original':'all','proposed':'subset','impact':'limited','accepted':False}]
        with self.assertRaisesRegex(ValueError,'unresolved'):validate(c)
    def test_rejects_reordered_fixed_arguments(self):
        c=contract();c['target']['arguments'].reverse()
        with self.assertRaisesRegex(ValueError,'order'):validate(c)
    def test_rejects_extra_array_slot_binding(self):
        c=contract(True);c['mappings'][0]['bindings']['count']['index']=3
        with self.assertRaisesRegex(ValueError,'outside'):validate(c)
    def test_postgresql_public_mapping_example(self):
        # REL_18_0 fuzzystrmatch.c SQL wrappers supply costs and trusted=false.
        # Static mapping evidence only: no PostgreSQL SQL execution is claimed.
        c=contract(True);c['origin'].update(database='PostgreSQL',version='18.0',
            documentation='https://www.postgresql.org/docs/18/fuzzystrmatch.html')
        c['origin']['forms'][0]['arguments']=[{'name':n,'type':'text','meaning':n,'default':None} for n in ('source','target')]
        c['origin']['forms'][1]['arguments']=c['origin']['forms'][0]['arguments']+[{'name':n,'type':'integer','meaning':n,'default':None} for n in ('ins_cost','del_cost','sub_cost')]
        for f,m in zip(c['origin']['forms'],c['mappings']):
            m['bindings']={a['name']:{'argument':'payload','index':i} for i,a in enumerate(f['arguments'])}
            m['source_call']='levenshtein(source, target, ...)'
            m['target_call']='ported(JSON_BUILD_ARRAY(source, target, ...))'
        j=c['json_arguments'][0];j['variants'][0]['items']=[{'type':'string','nullable':True}]*2
        j['variants'][1]['items']=[{'type':'string','nullable':True}]*2+[integer(True)]*3
        j['variants'][0]['defaults']={'ins_cost':1,'del_cost':1,'sub_cost':1}
        c['internal']=[{'name':'trusted','expression':'false','evidence':'https://github.com/postgres/postgres/blob/REL_18_0/contrib/fuzzystrmatch/fuzzystrmatch.c'}]
        validate(c)
        self.assertNotIn('trusted',c['mappings'][0]['bindings'])
        self.assertEqual(c['internal'][0]['expression'],'false')

    def test_udaf_mixed_transport(self):
        c=contract(False,True)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'project';generate_udaf(p,SKILL,'mixed',c)
            m=json.loads((p/'function.json').read_text());check_project(p,m)
            self.assertEqual(m['argument_types'],['string','s32'])
            self.assertIn('arg-label: string, arg-count: s32',(p/'interface.wit').read_text())

if __name__=='__main__':unittest.main()
