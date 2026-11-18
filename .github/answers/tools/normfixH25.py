#!/usr/bin/env python3
"""normfixH25.py — шаг 9 (применён, повторно не запускать): строкам, у которых при сокращении был отрезан хвост
(см. tail2.py: половины сравнений «контроль — … ; надзор — …», пояснения к пунктам, ссылки), возвращена
полная редакция 30db505."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2'); n = w = 0
for q in range(1, 150):
    p = os.path.join(A, 'q%03d.txt' % q); C = open(p, encoding='utf-8').read().split('\n')
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n')
    ch = False
    for i, l in enumerate(C):
        if not l.strip() or l.startswith(('#', '!!')) or l in O: continue
        body = l.rstrip('.;')
        o = next((x for x in O if x.startswith(body) and len(x) > len(l) + 15), None)
        if not o or o in C: continue
        w += len(o.split()) - len(l.split()); n += 1; ch = True
        C[i] = o.replace('УК РФа Российской Федерации', 'Уголовного кодекса Российской Федерации')
    if ch: open(p, 'w', encoding='utf-8').write('\n'.join(C))
print('строк', n, 'слов', w)
