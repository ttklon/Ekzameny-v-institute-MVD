#!/usr/bin/env python3
"""Запись правок: возвращены целиком удалённые при сокращении разделы, в которых пропало
шесть и более статей КоАП РФ (подведомственность, группы составов, ответственность).
Уже применено; повторный запуск не нужен."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import norm25 as N, art25 as T
import normfixB25 as B
THR = 6
def plan():
    out = []
    for q in range(1, 150):
        l = set(T.lost(q))
        if not l: continue
        o = N.old(q).split('\n'); c = N.cur(q)
        ch = {N.hk(x) for x in c.split('\n') if x.startswith('## ')}
        sec = ''; cnt = {}
        for line in o:
            if line.startswith('## '): sec = line
            if line.startswith('!! ') or not sec or N.hk(sec) in ch: continue
            for a in l & T.arts(line): cnt.setdefault(sec, set()).add(a)
        for s, v in cnt.items():
            if len(v) >= THR: out.append((q, N.hk(s), len(v)))
    return out
if __name__ == '__main__':
    P = plan()
    for q, h, n in P:
        if len(sys.argv) > 1 and sys.argv[1] == 'apply': B.sec(q, h)
        else: print('q%03d %s (%d)' % (q, h[:70], n))
