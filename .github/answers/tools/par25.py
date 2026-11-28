#!/usr/bin/env python3
"""par25.py [N…] — пункт перечня, сохранившийся дословно, должен стоять под той же вводной строкой
(или в том же разделе, если вводной строки не было), что и до сокращения (30db505)."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
isb = lambda s: bool(re.match(r'\s*(-|\d+\.)\s', s))
def parent(L, i):
    for k in range(i - 1, -1, -1):
        s = L[k]
        if not s.strip() or isb(s): continue
        return s
    return ''
key = lambda s: re.sub(r'^##\s*\d+\.\s*', '## ', s)[:30]
only = [int(a) for a in sys.argv[1:]]; n = 0
for q in range(1, 150):
    if only and q not in only: continue
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True, cwd=HERE).stdout.split('\n')
    C = open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')
    for i, l in enumerate(C):
        if not isb(l): continue
        oi = [k for k, x in enumerate(O) if x == l]
        if not oi: continue
        pc = parent(C, i); po = [parent(O, k) for k in oi]
        if key(pc) not in [key(p) for p in po]:
            n += 1; print('q%03d:%d %s\n      было под: %s\n      теперь под: %s' % (q, i + 1, l[:90], po[0][:90], pc[:90]))
print('всего', n)
