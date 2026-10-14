"""Execute actual f64 Wasm and, when configured, compare with inspected Python source.

Not a translator or a sandbox: Codex must inspect source and dependencies before
configuring python_reference. NULL propagation is tested by the SQL wrapper.
"""
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import runpy
import warnings

from common import finite_number, scalar_matches


def project_file(project, relative):
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or not path.is_file():
        raise ValueError('reference file must be inside project')
    return path


def verify(project, binary, spec):
    import wasmtime
    engine = wasmtime.Engine()
    module = wasmtime.Module(engine, binary)
    store = wasmtime.Store(engine)
    instance = wasmtime.Instance(store, module, [])
    evaluate = instance.exports(store)['evaluate']
    sentinel = spec.get('error_sentinel')
    report = {'status': 'passed', 'engine': 'wasmtime',
              'engine_version': importlib.metadata.version('wasmtime'),
              'cases': [], 'null_cases_deferred_to_sql': [],
              'python_reference': {'status': 'not_configured'}}
    for case in spec['cases']:
        if any(x is None for x in case['args']):
            report['null_cases_deferred_to_sql'].append(case['id'])
            continue
        actual = evaluate(store, *map(float, case['args']))
        passed = (sentinel is not None and actual == sentinel if 'expected_error' in case
                  else scalar_matches(actual, case, spec))
        report['cases'].append({'id': case['id'], 'actual': actual if math.isfinite(actual) else str(actual),
                                'passed': passed})
    if not report['cases'] or not all(row['passed'] for row in report['cases']):
        report['status'] = 'failed'
    reference = spec.get('python_reference')
    if not reference:
        return report
    source = project_file(project, reference['source'])
    evidence = {'status': 'running', 'source': reference['source'],
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'comparison': spec['comparison'], 'cases': [], 'max_absolute_error': 0.0,
                'max_relative_error': 0.0}
    report['python_reference'] = evidence
    try:
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            namespace = runpy.run_path(str(source))
        function = namespace[reference['callable']]
        if not callable(function):
            raise ValueError('reference callable is not callable')
    except (ImportError, OSError) as exc:
        evidence.update(status='unavailable', reason=str(exc),
                        fallback='manifest expected cases on actual Wasm and Rust tests; Python equivalence unverified')
        return report
    evidence['dependency_versions'] = {}
    for package in reference.get('packages', []):
        evidence['dependency_versions'][package] = importlib.metadata.version(package)
    reference_cases = list(spec['cases'])
    if reference.get('extra_cases'):
        reference_cases += json.loads(project_file(project, reference['extra_cases']).read_text())
    for case in reference_cases:
        if any(x is None for x in case['args']):
            continue
        row = {'id': case['id']}
        try:
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                warnings.simplefilter('ignore', RuntimeWarning)
                result = float(function(*map(float, case['args'])))
            error = not finite_number(result)
            row['python'] = str(result) if error else result
        except (ArithmeticError, ValueError, TypeError) as exc:
            error = True
            row['python_error'] = type(exc).__name__ + ': ' + str(exc)
        actual = evaluate(store, *map(float, case['args']))
        row['wasm'] = actual if math.isfinite(actual) else str(actual)
        if error:
            row['passed'] = sentinel is not None and actual == sentinel
            if 'expected' in case:
                row['passed'] = False
        else:
            row['passed'] = scalar_matches(actual, {'expected': result}, spec)
            if 'expected_error' in case:
                row['passed'] = False
            if 'expected' in case:
                row['passed'] &= scalar_matches(result, case, spec)
            absolute = abs(actual - result)
            relative = absolute / abs(result) if result else 0.0
            if math.isfinite(absolute):
                evidence['max_absolute_error'] = max(evidence['max_absolute_error'], absolute)
            if math.isfinite(relative):
                evidence['max_relative_error'] = max(evidence['max_relative_error'], relative)
        evidence['cases'].append(row)
    evidence['status'] = 'passed' if evidence['cases'] and all(c['passed'] for c in evidence['cases']) else 'failed'
    if evidence['status'] == 'failed':
        report['status'] = 'failed'
    return report
