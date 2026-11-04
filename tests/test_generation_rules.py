"""Regression checks for complete call forms and database-independent SQL."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_public_contract import SKILL, contract
from typed import generate, generate_udaf, validate_cases
from common import write_sql, manifest
from aggregate import fixture_plan, input_declarations


class GenerationRulesTest(unittest.TestCase):
    def json_manifest(self):
        return {'name': 'forms', 'shape': 'typed-scalar', 'target_version': '9.1.1',
                'public_contract': contract(True), 'null_policy': 'propagate',
                'error_sentinel': -(2**63), 'error_message': 'invalid_input',
                'cases': [{'id': 'short', 'args': [{'json_array': ['ab', 3]}], 'expected': 8},
                          {'id': 'long', 'args': [{'json_array': ['ab', 3, 4, 5, 6]}], 'expected': 20}]}

    def test_missing_short_form_is_rejected(self):
        m = self.json_manifest()
        validate_cases(m)
        m['cases'] = m['cases'][1:]
        with self.assertRaisesRegex(ValueError, 'uncovered.*short'):
            validate_cases(m)

    def test_error_and_sql_null_do_not_cover_short_form(self):
        m = self.json_manifest()
        m['cases'][0]['expected_error'] = 'invalid_input'
        del m['cases'][0]['expected']
        m['cases'].append({'id': 'null', 'args': [None], 'expected': None})
        with self.assertRaisesRegex(ValueError, 'uncovered.*short'):
            validate_cases(m)

    def test_ambiguous_json_form_is_not_coverage(self):
        m = self.json_manifest()
        j = m['public_contract']['json_arguments'][0]
        # Same types and lengths can never select either form uniquely.
        j['variants'][0]['items'] = copy.deepcopy(j['variants'][1]['items'])
        j['allowed_lengths'] = [5]
        with self.assertRaisesRegex(ValueError, 'uncovered'):
            validate_cases(m)

    def test_udaf_missing_form_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'project'
            generate_udaf(p, SKILL, 'forms', contract(True, True))
            m = json.loads((p/'function.json').read_text())
            m['cases'] = [{'id': 'long', 'rows': [[{'json_array': ['ab', 3, 4, 5, 6]}]], 'expected': '20'}]
            (p/'function.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, 'uncovered.*short'):
                manifest(p)
            m['cases'].append({'id': 'short', 'rows': [[{'json_array': ['ab', 3]}]], 'expected': '8'})
            (p/'function.json').write_text(json.dumps(m))
            manifest(p)

    def test_udaf_defaults_and_omitted_sql_arguments_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'project'
            generate_udaf(p, SKILL, 'explicit_args', contract(udaf=True))
            m = json.loads((p/'function.json').read_text())
            m['cases'] = [{'id': 'row', 'rows': [['a', 2]], 'expected': '3'}]
            (p/'function.json').write_text(json.dumps(m))
            manifest(p)
            for defaults in ({'0': '[]'}, {'1': 0}):
                with self.subTest(defaults=defaults):
                    m['argument_defaults'] = defaults
                    (p/'function.json').write_text(json.dumps(m))
                    with self.assertRaisesRegex(ValueError, 'CREATE AGGREGATE.*DEFAULT'):
                        manifest(p)
                    with self.assertRaisesRegex(ValueError, 'pass all SQL arguments'):
                        input_declarations(m)
            del m['argument_defaults']
            m['cases'][0]['rows'] = [['a']]
            (p/'function.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, 'argument arity mismatch'):
                manifest(p)

    def test_scalar_and_udaf_sql_have_no_database(self):
        for udaf in (False, True):
            with self.subTest(udaf=udaf), tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'project'
                (generate_udaf if udaf else generate)(p, SKILL, 'plain', contract(udaf=udaf))
                m = json.loads((p/'function.json').read_text())
                m['cases'] = ([{'id': 'row', 'rows': [['a', 2]], 'expected': '3'}] if udaf else
                              [{'id': 'row', 'args': ['a', 2], 'expected': 3}])
                (p/'function.json').write_text(json.dumps(m))
                (p/'artifacts').mkdir()
                (p/'artifacts/module.wasm.b64').write_text('AA==')
                # SQL assembly test only; the smoke test compiles real modules.
                with patch('common.verify_build', return_value={}):
                    write_sql(p, 'ssws_plain')
                sql = '\n'.join(f.read_text() for f in (p/'artifacts').glob('*.sql'))
                self.assertNotRegex(sql, r'(?im)^\s*USE\s|`\w+`\s*\.\s*`')
                self.assertIn('`ssws_plain`', sql)
                if udaf:
                    self.assertNotRegex(sql, r'(?i)\bDEFAULT\b')
                    self.assertIn('`ssws_plain`(a0, a1)', sql)
                if not udaf:
                    self.assertIn('result = `ssws_plain_core`(', sql)

    def test_fixture_sql_has_no_database(self):
        m = {'argument_types': ['s64'], 'fixtures': [{'id': 'rows',
             'columns': {'g': 's64', 'v': 's64'}, 'shard_by': ['g'], 'rows': [[1, 2]],
             'cases': [{'group_by': ['g'], 'arguments': [{'column': 'v'}]}]}]}
        f = fixture_plan(m, 'ssws_plain')[0]
        sql = '\n'.join([f['sql'], *f['inserts'], f['checks'][0]['sql']])
        self.assertNotRegex(sql, r'(?im)^\s*USE\s|`\w+`\s*\.\s*`')
        self.assertIn('CREATE ROWSTORE TABLE `ssws_plain_rows`', sql)


if __name__ == '__main__':
    unittest.main()
