#!/usr/bin/env python3
"""tail2.py [N…] [all] — строки, у которых после сокращения отрезан хвост (строка = начало строки 30db505).
Без «all» печатаются только подозрительные: в оставшейся части есть слово-маркер сравнения или перечня
(«общий —», «при контроле», «первый», «с одной стороны», двоеточие в конце и т. п.), а пара к нему отрезана."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
only = [int(a) for a in sys.argv[1:] if a.isdigit()]; allm = 'all' in sys.argv; n = w = 0
for q in range(1, 150):
    if only and q not in only: continue
    C = open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n')
    for i, l in enumerate(C):
        if not l.strip() or l.startswith(('#', '!!')) or l in O: continue
        body = l.rstrip('.;')
        o = next((x for x in O if x.startswith(body) and len(x) > len(l) + 15), None)
        if not o or o in C: continue
        tail = o[len(body):].lstrip('.; ')
        n += 1; w += len(tail.split())
        if allm or only: print('q%03d:%d …%s ‖ %s' % (q, i + 1, l[-110:], tail[:260]))
print('строк', n, 'слов в хвостах', w)
