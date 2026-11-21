#!/usr/bin/env python3
"""sdup2.py [N…] — предложения (от 9 слов), повторённые внутри одного ответа вне блока «Главное»."""
import re, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
A = os.path.join(HERE, '..', 'adp2'); only = [int(a) for a in sys.argv[1:] if a.isdigit()]; n = 0
key = lambda s: re.sub(r'[^а-яёa-z0-9]+', ' ', re.sub(r'//.*?//', '', s).lower()).strip()
for q in range(1, 150):
    if only and q not in only: continue
    seen = {}
    for i, l in enumerate(open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')):
        if l.startswith(('!!', '#')) or not l.strip(): continue
        for s in cut25.split_sent(re.sub(r'^(\s*- |\d+\. |> )', '', l)):
            k = key(s)
            if len(k.split()) < 9: continue
            if k in seen and seen[k] != i + 1:
                n += 1; print('q%03d:%d = %d  %s' % (q, seen[k], i + 1, s.strip()[:150]))
            seen.setdefault(k, i + 1)
print('всего', n)
