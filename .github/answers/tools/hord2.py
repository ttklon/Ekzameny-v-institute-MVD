#!/usr/bin/env python3
"""hord2.py — порядок разделов: заголовки ответа, которые идут не в том порядке, что в полной редакции 30db505
(возвращённый раздел мог встать не на своё место)."""
import re, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2'); n = 0
h = lambda L: [re.sub(r'^## \d+\. ', '', l) for l in L if l.startswith('## ')]
for q in range(1, 150):
    C = h(open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n'))
    O = h(subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n'))
    idx = [(O.index(c) if c in O else None) for c in C]; last = -1
    for c, i in zip(C, idx):
        if i is None: print('q%03d новый заголовок: %s' % (q, c)); continue
        if i < last: n += 1; print('q%03d не на месте: «%s» (в полной редакции — раздел %d)' % (q, c, i + 1))
        last = max(last, i)
print('всего', n)
