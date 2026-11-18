#!/usr/bin/env python3
"""term25.py [N…] — выделенные (**…**) слова блока «Главное для запоминания», которых нет в тексте ответа:
блок не должен называть то, что в ответе не раскрыто."""
import re, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
st = lambda w: w[:5] if len(w) > 6 else w[:4]
words = lambda s: [w for w in re.findall(r'[а-яёa-z]+', s.lower().replace('ё', 'е')) if len(w) >= 4]
only = [int(a) for a in sys.argv[1:]]; n = 0; qs = 0
for q in range(1, 150):
    if only and q not in only: continue
    L = open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')
    bl = next((l for l in L if l.startswith('!! ')), ''); body = ' '.join(l for l in L if not l.startswith('!! '))
    bs = set(st(w) for w in words(body)); miss = []
    for m in re.finditer(r'\*\*(.+?)\*\*', bl):
        ws = words(m.group(1))
        if not ws: continue
        lost = [w for w in ws if st(w) not in bs]
        if lost and len(lost) * 2 >= len(ws): miss.append(m.group(1))
    if miss: qs += 1; n += len(miss); print('q%03d: %s' % (q, ' | '.join(miss)))
print('ответов:', qs, 'выделений:', n)
