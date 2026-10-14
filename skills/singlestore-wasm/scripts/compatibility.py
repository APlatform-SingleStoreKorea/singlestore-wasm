#!/usr/bin/env python3
"""Evaluate an agent-authored compatibility decision; never infer user consent."""
import argparse
import json
from pathlib import Path

ASPECTS = {'public_function_count', 'calling_convention', 'return_format', 'semantics'}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def arities(value):
    return (isinstance(value, list) and bool(value)
            and all(type(n) is int and n >= 0 for n in value)
            and len(set(value)) == len(value))


def evaluate(plan):
    if not isinstance(plan, dict):
        raise ValueError('compatibility must be an object')
    if not nonempty(plan.get('target_version')):
        raise ValueError('record the target SingleStore version')
    review = plan.get('review_basis')
    if not isinstance(review, list) or not review or not all(nonempty(x) for x in review):
        raise ValueError('review reference documents and target support before deciding')
    available = plan.get('available_arities')
    if not arities(available):
        raise ValueError('available_arities must be unique nonnegative integers')
    selected = plan.get('selected_arities')
    pending = []
    if selected is None:
        pending.append('support_scope')
        selected = []
    else:
        basis = plan.get('scope_basis')
        if (not isinstance(basis, dict)
                or basis.get('source') not in {'code', 'sql', 'conversation', 'user'}
                or not nonempty(basis.get('evidence'))):
            raise ValueError('selected scope requires code, SQL, or user/conversation evidence')
        if selected == 'all':
            if basis['source'] not in {'user', 'conversation'}:
                raise ValueError('all requires an explicit user request or prior agreement')
            selected = list(available)
        if not arities(selected) or not set(selected) <= set(available):
            raise ValueError('selected_arities must be a nonempty subset of available_arities')
    differences = plan.get('differences')
    if not isinstance(differences, list):
        raise ValueError('record public differences explicitly, or use an empty list')
    for index, difference in enumerate(differences):
        if (not isinstance(difference, dict) or difference.get('aspect') not in ASPECTS
                or not all(nonempty(difference.get(k)) for k in ('original', 'proposed', 'impact'))
                or type(difference.get('accepted')) is not bool):
            raise ValueError('each public difference needs aspect, original, proposed, impact and accepted')
        if difference['accepted']:
            if not nonempty(difference.get('evidence')):
                raise ValueError('accepted difference requires actual user agreement evidence')
        else:
            pending.append(f'differences[{index}].{difference["aspect"]}')
    return {'state': 'needs_user_input' if pending else 'ready',
            'selected_arities': [] if pending else sorted(selected),
            'pending': pending, 'differences': differences,
            'target_version': plan['target_version']}


def require_ready(plan, arity, public_variants=None):
    result = evaluate(plan)
    if result['state'] != 'ready':
        raise ValueError('compatibility needs user input: ' + ', '.join(result['pending']))
    if arity not in result['selected_arities']:
        raise ValueError('function arity is outside the selected support scope')
    if public_variants is not None:
        selected = plan.get('public_variants')
        if (not isinstance(selected, list) or not selected
                or not all(isinstance(x, str) for x in selected)
                or len(set(selected)) != len(selected)
                or set(selected) != set(public_variants)):
            raise ValueError('public aggregates differ from selected public_variants')
    return result


def validate_manifest(manifest):
    if manifest.get('request_review_required'):
        raise ValueError('new request review required; replace compatibility and clear request_review_required after reviewing contract, sources and cases')
    # Legacy pinned projects remain reproducible; new requests must record decisions.
    if 'compatibility' not in manifest:
        return None
    if manifest.get('kind') == 'handle-udaf':
        return require_ready(manifest['compatibility'], len(manifest['argument_types']),
                             list(manifest['aggregates']))
    shape = manifest.get('shape')
    if shape == 'f64-scalar':
        arity = len(manifest['arguments'])
    elif shape in {'string-pair-i64', 'i64-unary'}:
        arity = 2 if shape == 'string-pair-i64' else 1
    else:
        raise ValueError('extend compatibility arity validation for the new profile')
    return require_ready(manifest['compatibility'], arity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.plan.read_text()))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result['state'] == 'ready' else 2)


if __name__ == '__main__':
    main()
