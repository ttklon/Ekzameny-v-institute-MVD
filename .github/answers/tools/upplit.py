#!/usr/bin/env python3
"""Утверждения ответов УПП без ссылки на норму — рядом с подлинным текстом ближайшего места в источниках.

upplit.py IDX_ACTS DIR_ACTS IDX_LIT DIR_LIT [N1 N2] [--max=70] [--w=420]
Для каждого утверждения без ссылки на статью берутся лучшие отрезки по указателям (srcidx25.py),
в найденных файлах ищется окно из трёх предложений с наибольшим совпадением и печатается как в источнике.
Печатаются утверждения, покрытые меньше --max процентов, и все, где есть число.
"""
import sys, os, re, math, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K, uppver as V
from uppsent import Idx

CACHE = {}
def sents_of(path):
    if path not in CACHE:
        t = open(path, encoding='utf-8', errors='ignore').read()
        t = re.sub(r'-\s*\n\s*', '', t); t = re.sub(r'\s+', ' ', t)
        ss = [x for x in re.split(r'(?<=[.;!?])\s+', t) if len(x) > 20]
        CACHE[path] = (ss, [set(K.tokens(x)) for x in ss])
        if len(CACHE) > 60: CACHE.pop(next(iter(CACHE)))
    return CACHE[path]

def window(path, toks, wt):
    ss, st = sents_of(path)
    best = (0, 0)
    for i in range(len(ss)):
        have = st[i] | (st[i + 1] if i + 1 < len(ss) else set()) | (st[i + 2] if i + 2 < len(ss) else set())
        sc = sum(wt[w] for w in toks if w in have)
        if sc > best[0]: best = (sc, i)
    i = best[1]
    have = set().union(*st[i:i + 3]) if ss else set()
    return best[0], ' '.join(ss[i:i + 3]), have

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    A, DA, L, DL = Idx(args[0]), args[1], Idx(args[2]), args[3]
    a, b = (int(args[4]), int(args[5])) if len(args) >= 6 else (1, 999)
    mx, width = 70, 420
    for x in sys.argv:
        if x.startswith('--max='): mx = int(x[6:])
        if x.startswith('--w='): width = int(x[4:])
    files = {}
    for d in (DA, DL):
        for f in glob.glob(os.path.join(d, '*.txt')): files[os.path.basename(f)[:6]] = f
    NC = A.C + L.C; tot = shown = 0
    for n in range(a, b + 1):
        if not os.path.exists(os.path.join(HERE, '..', 'upp', 'q%03d.txt' % n)): continue
        res, st = V.check(n, show_all=False)
        for ln, kind, label, cov, miss, soft, text, nt in res:
            if kind != 'БЕЗ ССЫЛКИ': continue
            ct = V.toks(text); toks = list(dict.fromkeys(s for s, _ in ct))
            if len(toks) < 2: continue
            word = dict((s, w) for s, w in ct)
            wt = {w: max(0.3, math.log(NC / (1 + A.df(w) + L.df(w)))) for w in toks}
            T = sum(wt.values()); tot += 1
            cand = []
            for I in (A, L):
                for sc, got, c in I.best(toks, wt, k=3):
                    nm = I.names[I.cfile[c]]
                    if nm[:6] in files: cand.append(files[nm[:6]])
            bestw = (0, '', set(), '')
            for p in dict.fromkeys(cand):
                sc, txt, have = window(p, toks, wt)
                if sc > bestw[0]: bestw = (sc, txt, have, p)
            cv = round(100 * bestw[0] / T)
            num = bool(re.search(r'\d', re.sub(r'\*\*', '', text)))
            if cv >= mx and not num: continue
            shown += 1
            un = [word[w] for w in toks if w not in bestw[2]]
            print('%d:%d [%d%%] %s' % (n, ln, cv, text[:width]))
            print('    нет: ' + ' '.join(un[:14]))
            print('    ▸ [' + os.path.basename(bestw[3])[7:67] + '] ' + bestw[1][:width])
    print('утверждений без ссылки %d, напечатано %d' % (tot, shown))
