#!/usr/bin/env python3
"""stump2.py [MAXW] — абзацы, от которых после сокращения остался обрубок: строка до MAXW (по умолчанию 14) слов,
а в 30db505 она начиналась так же и была не менее чем втрое длиннее."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
mx = int(sys.argv[1]) if len(sys.argv) > 1 else 14; n = 0
for q in range(1, 150):
    C = open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n')
    od = {}
    for l in O: od.setdefault(l[:28], l)
    for i, l in enumerate(C):
        if not l.strip() or l.startswith(('#', '!!')) or l in O: continue
        o = od.get(l[:28])
        if not o: continue
        w, ow = len(l.split()), len(o.split())
        if w <= mx and ow >= 3 * w:
            n += 1; print('q%03d:%d [%d из %d сл.] %s\n      БЫЛО: %s' % (q, i + 1, w, ow, l[:120], o[len(l) - 3:len(l) + 260] if o.startswith(l[:-1]) else o[:300]))
print('всего', n)
