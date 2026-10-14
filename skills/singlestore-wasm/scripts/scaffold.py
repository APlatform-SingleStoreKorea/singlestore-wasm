#!/usr/bin/env python3
"""Create an editable function project; never replace an existing directory."""
import argparse
import json
import re
import shutil
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name', required=True)
    ap.add_argument('--shape', choices=['string-pair-i64', 'i64-unary', 'f64-scalar', 'json-array-udaf'], required=True)
    ap.add_argument('--arguments', nargs='+', help='f64-scalar argument names in source order')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--compatibility', type=Path, help='Analyzed scope and public-contract decisions')
    ns = ap.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,35}', ns.name):
        ap.error('name must be a lowercase identifier of at most 36 characters')
    floating = ns.shape == 'f64-scalar'
    if floating and (not ns.arguments or len(ns.arguments) > 16
                     or len(set(ns.arguments)) != len(ns.arguments)
                     or any(not re.fullmatch(r'[a-z][a-z0-9_]{0,35}', n) for n in ns.arguments)):
        ap.error('f64-scalar requires 1..16 unique lowercase --arguments')
    if not floating and ns.arguments:
        ap.error('--arguments applies to f64-scalar only')
    decision = None
    if ns.compatibility:
        from compatibility import require_ready
        try:
            decision = json.loads(ns.compatibility.read_text())
            require_ready(decision, len(ns.arguments) if floating else (2 if ns.shape == 'string-pair-i64' else 1))
        except (OSError, ValueError) as exc:
            ap.error(str(exc))
    if ns.shape == 'json-array-udaf':
        if decision is not None:
            from compatibility import require_ready
            require_ready(decision, 1, [''])
        shutil.copytree(SKILL/'templates/json-array-udaf', ns.output)
        for filename in ('Cargo.toml', 'rust-toolchain.toml'):
            data = (SKILL/'templates/rust'/filename).read_text()
            (ns.output/filename).write_text(data.replace('{{name}}', ns.name))
        manifest = json.loads((ns.output/'function.json').read_text())
        manifest['name'] = ns.name
        if decision is not None:
            manifest['compatibility'] = decision
        (ns.output/'function.json').write_text(json.dumps(manifest, indent=2)+'\n')
        print(f'Created {ns.output}; implement logic, input policy, return contract and independent cases; verification not run.')
        return
    ns.output.mkdir(parents=True, exist_ok=False)
    (ns.output / 'src').mkdir()
    for filename in ['Cargo.toml', 'rust-toolchain.toml']:
        data = (SKILL / 'templates/rust' / filename).read_text()
        (ns.output / filename).write_text(data.replace('{{name}}', ns.name))
    strings = ns.shape == 'string-pair-i64'
    abi = (SKILL / 'templates/rust' / ('string_pair.rs' if strings else 'i64_unary.rs')).read_text()
    if floating:
        params = ', '.join('arg_' + n + ': f64' for n in ns.arguments)
        names = ', '.join('arg_' + n for n in ns.arguments)
        abi = ('#[cfg(target_arch = "wasm32")]\n#[export_name = "evaluate"]\n'
               f'pub extern "C" fn evaluate_export({params}) -> f64 {{\n'
               f'    crate::logic::evaluate({names})\n}}\n')
    (ns.output / 'src/lib.rs').write_text('pub mod logic;\n' + abi)
    (ns.output / 'src/logic.rs').write_text('compile_error!("Implement the requested function and independent tests before building");\n')
    signature = '(left: string, right: string)' if strings else '(value: s64)'
    if floating:
        signature = '(' + ', '.join('arg-' + n.replace('_', '-') + ': float64' for n in ns.arguments) + ')'
    (ns.output / 'interface.wit').write_text(f'evaluate: func{signature} -> {"float64" if floating else "s64"}\n')
    from return_contracts import contract
    manifest = {'name': ns.name, 'shape': ns.shape, 'null_policy': 'propagate', 'cases': [],
                'returns': contract('f64' if ns.shape=='f64-scalar' else 's64',
                                    'DOUBLE' if ns.shape=='f64-scalar' else 'BIGINT', True)}
    if decision is not None:
        manifest['compatibility'] = decision
    if floating:
        manifest.update(arguments=ns.arguments, comparison={'absolute': 0.0, 'relative': 0.0})
    (ns.output / 'function.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Created {ns.output}; implement src/logic.rs and function.json cases next.')

if __name__ == '__main__':
    main()
