"""Run an inspected upstream adapter and a Wasm adapter on identical cases.

Adapters are trusted project code, not a sandbox. Output is a JSON list of
complete cases with expected/expected_error populated from actual execution.
"""
import hashlib
import json
import subprocess


def verify(project, spec, binary):
    ref = spec.get('reference')
    if not ref:
        return {'status': 'unverified', 'reason': 'reference not configured'}
    result = {'status': 'unverified', 'sources': ref.get('sources', []),
              'reason': ref.get('unavailable_reason', '')}
    if not ref.get('command') or not ref.get('wasm_command'):
        result['reason'] = result['reason'] or 'reference or Wasm adapter unavailable'
        return result
    if not ref.get('sources') or not ref.get('revision'):
        raise ValueError('reference execution requires sources and immutable revision')
    result['revision'] = ref['revision']
    result['files'] = {}
    for name in ref.get('files', []):
        path = (project / name).resolve()
        if not path.is_relative_to(project.resolve()) or not path.is_file():
            raise ValueError('reference evidence file must be inside project')
        result['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not result['files']:
        raise ValueError('reference adapter/source evidence files required')
    if spec.get('fixtures'):
        result['scope'] = 'manifest cases only; fixtures excluded'
    cases = spec['cases']
    inputs = [{k: v for k, v in c.items() if k not in ('expected', 'expected_error')}
              for c in cases]
    def execute(command, wasm):
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError('adapter command must be an argv list')
        payload = {'cases': inputs}
        if wasm:
            payload['wasm'] = str(binary.resolve())
        completed = subprocess.run(command, cwd=project, input=json.dumps(payload),
                                   text=True, capture_output=True, check=True,
                                   timeout=ref.get('timeout_seconds', 120))
        return json.loads(completed.stdout)
    upstream = execute(ref['command'], False)
    actual = execute(ref['wasm_command'], True)
    # Exact case equality also binds the input, ordering, error contract and IDs.
    # Adapters must apply only explicitly documented public-contract mappings.
    result.update(reference_cases=upstream, wasm_cases=actual,
                  commands={'reference': ref['command'], 'wasm': ref['wasm_command']},
                  wasm_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    result['status'] = 'passed' if upstream == cases and actual == upstream else 'failed'
    result['comparison'] = 'exact; manifest cases only'
    return result
