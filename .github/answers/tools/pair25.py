#!/usr/bin/env python3
"""Пары «акт — статья (пункт)», на которые ответ ссылался до сокращения (30db505) и не ссылается теперь.
Неполные ссылки (//ч. 2//, //ст. 12//) разрешаются как в cut25.resolve(). Блок «!!» не считается.
  pair25.py [show] [N…]
"""
import sys, re, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import norm25 as N, cut25 as C
def pairs(t):
    L = [(i, l) for i, l in enumerate(t.split('\n')) if not l.startswith('!! ')]
    res, names = C.resolve(L)
    out = collections.defaultdict(list)
    for (i, k), (act, art) in res.items():
        if art: out[(act, art)].append(i)
    return out
def lost(q):
    o = pairs(N.old(q)); c = pairs(N.cur(q))
    return {p: v for p, v in o.items() if p not in c}
if __name__ == '__main__':
    show = len(sys.argv) > 1 and sys.argv[1] == 'show'
    only = [int(x) for x in sys.argv[2:] if x.isdigit()]
    tot = 0; byact = collections.Counter(); lines = 0; words = 0
    for q in range(1, 150):
        if only and q not in only: continue
        l = lost(q)
        if not l: continue
        tot += len(l)
        for (a, s) in l: byact[a] += 1
        o = N.old(q).split('\n'); ls = sorted({v[0] for v in l.values()})
        lines += len(ls); words += sum(len(o[i].split()) for i in ls)
        if show: print('q%03d (%d): %s' % (q, len(l), '; '.join('%s ст. %s' % (a, s) for (a, s) in sorted(l, key=str))[:1500]))
    print('пар потеряно: %d; строк с первым упоминанием: %d, слов в них: %d' % (tot, lines, words))
    for a, n in byact.most_common(25): print('  %4d  %s' % (n, a))
