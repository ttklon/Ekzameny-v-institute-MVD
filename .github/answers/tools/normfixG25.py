#!/usr/bin/env python3
"""normfixG25.py MAXW [RATIO] [norm] — шаг 8 (применён, повторно не запускать): абзацы-обрубки (см. stump2.py)
заменяются полной редакцией из 30db505. norm — только если отрезанная часть содержит ссылку //…// или цитату."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
mx = int(sys.argv[1]); ratio = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != 'norm' else 3.0
norm = 'norm' in sys.argv; dry = 'dry' in sys.argv; n = w = 0
for q in range(1, 150):
    p = os.path.join(A, 'q%03d.txt' % q); C = open(p, encoding='utf-8').read().split('\n')
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n')
    od = {}
    for l in O: od.setdefault(l[:28], l)
    ch = False
    for i, l in enumerate(C):
        if not l.strip() or l.startswith(('#', '!!')) or l in O: continue
        o = od.get(l[:28])
        if not o or o in C: continue
        cw, ow = len(l.split()), len(o.split())
        if cw <= mx and ow >= ratio * cw:
            rest = o[len(l) - 2:] if o.startswith(l[:-2]) else o
            if norm and '//' not in rest and '«' not in rest: continue
            if dry: print('q%03d:%d [%d→%d] %s ‖ %s' % (q, i + 1, cw, ow, l[:70], rest[:200]))
            C[i] = o.replace('УК РФа Российской Федерации', 'Уголовного кодекса Российской Федерации'); ch = True; n += 1; w += ow - cw
    if ch and not dry: open(p, 'w', encoding='utf-8').write('\n'.join(C))
print('строк', n, 'слов', w)
