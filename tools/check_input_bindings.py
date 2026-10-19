#!/usr/bin/env python3
"""Verify the PC default binding table has no undeclared clash.

The table lives in godot/core/services/input_service.gd as the single source of
truth. This mirrors the pure `undeclared_clashes()` check so it can run in CI
without a Godot binary — which matters, because a binding clash is the kind of
bug that only shows up when a player presses the key.

Usage: python3 -I tools/check_input_bindings.py
"""
import re, sys, pathlib, collections

SRC = pathlib.Path(__file__).resolve().parent.parent / 'godot/core/services/input_service.gd'
text = SRC.read_text(encoding='utf-8')

block = text[text.index('const DEFAULTS := {'):]
block = block[:block.index('\n}\n')]

rows = {}
for m in re.finditer(r'^\t"([a-z_]+)":\s*\{(.+)\},\s*$', block, re.M):
    action, body = m.group(1), m.group(2)
    ctx = re.search(r'"context":\s*"(\w+)"', body)
    entry = {
        'context': ctx.group(1) if ctx else 'shared',
        'keys': re.findall(r'KEY_([A-Z0-9_]+)', body),
        'mouse': re.findall(r'(MB_[A-Z_]+)', body),
        'joy': re.findall(r'(JOY_BUTTON_[A-Z_]+)', body),
        'shares_with': re.findall(r'"shares_with":\s*\[([^\]]*)\]', body),
    }
    entry['shares_with'] = re.findall(r'"(\w+)"', entry['shares_with'][0]) if entry['shares_with'] else []
    rows[action] = entry

if not rows:
    sys.exit('could not parse the DEFAULTS table — did its shape change?')

def shares(a, b):
    return b in rows[a]['shares_with'] or a in rows[b]['shares_with']

seen = collections.defaultdict(list)
clashes = []
for action, e in rows.items():
    for kind in ('keys', 'mouse', 'joy'):
        for code in e[kind]:
            key = f'{kind}:{code}'
            for other in seen[key]:
                oc, c = rows[other]['context'], e['context']
                overlap = oc == c or oc == 'shared' or c == 'shared'
                if overlap and not shares(action, other):
                    clashes.append((action, other, key, c, oc))
            seen[key].append(action)

unbound = [a for a, e in rows.items() if not (e['keys'] or e['mouse'] or e['joy'])]

print(f'actions: {len(rows)}  contexts: {sorted({e["context"] for e in rows.values()})}')
declared = [(a, s) for a, e in rows.items() for s in e['shares_with']]
if declared:
    print('declared intentional pairs: ' + ', '.join(f'{a}+{b}' for a, b in declared))

ok = True
if clashes:
    ok = False
    print('\nUNDECLARED CLASHES:')
    for a, b, key, c, oc in clashes:
        print(f'  {a} ({c}) and {b} ({oc}) are both bound to {key}')
if unbound:
    ok = False
    print('\nACTIONS WITH NO BINDING AT ALL: ' + ', '.join(unbound))

if ok:
    print('\nno undeclared clashes; every action has at least one binding')
sys.exit(0 if ok else 1)
