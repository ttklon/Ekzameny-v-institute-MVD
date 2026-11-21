#!/usr/bin/env python3
"""uppsent.py IDX_ACTS IDX_LIT [N1 N2] [--all] [--w=N] [--show] — утверждения ответов УПП без ссылки на норму: поиск опоры в источниках.

IDX_ACTS — указатель srcidx25.py по текстам актов и судебной практики (extract_src.py), IDX_LIT — по учебной и
научной литературе (extract_lit.py). Для каждого утверждения, которое uppver.py печатает как «БЕЗ ССЫЛКИ»
(с ключом --all — для всех утверждений), ищется место в актах и место в литературе, где собрано больше всего
его слов (слово весит тем больше, чем оно реже). Печатает: ответ:строка, долю слов в лучшем месте актов и
литературы, слова, которых нет ни там, ни там, текст и имя лучшего источника. С ключом --show — и сам найденный отрывок.
Это отбор мест для чтения, а не вывод об ошибке.
"""
import sys, os, re, pickle, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K, uppver as V


class Idx:
    def __init__(s, d):
        m = pickle.load(open(os.path.join(d, 'meta.pkl'), 'rb')); s.vocab = m['vocab']; s.names = m['names']; s.W = m['W']
        ld = lambda n: np.load(os.path.join(d, n + '.npy'), mmap_mode='r')
        s.T = ld('T'); s.pch = ld('pch'); s.poff = ld('poff'); s.cstart = ld('cstart'); s.cfile = np.array(ld('cfile'))
        s.C = len(s.cstart); s.N = len(s.T); s.inv = None

    def df(s, w):
        i = s.vocab.get(w); return 0 if i is None else int(s.poff[i + 1] - s.poff[i])

    def best(s, toks, wt, k=1):
        sc = np.zeros(s.C + 1, dtype=np.float32)
        for w in toks:
            i = s.vocab.get(w)
            if i is None: continue
            sc[s.pch[s.poff[i]:s.poff[i + 1]]] += wt[w]
        two = sc[:-1] + sc[1:]
        out = []
        for c in np.argsort(-two)[:k * 3]:
            c = int(c)
            a = int(s.cstart[c]); b = int(s.cstart[c + 2]) if c + 2 < s.C else s.N
            have = set(np.unique(s.T[a:b]).tolist())
            got = {w for w in toks if s.vocab.get(w) in have}
            out.append((sum(wt[w] for w in got), got, c))
        out.sort(key=lambda x: -x[0])
        return out[:k]

    def text(s, c):
        if s.inv is None:
            s.inv = {i: w for w, i in s.vocab.items()}
        a = int(s.cstart[c]); b = int(s.cstart[c + 2]) if c + 2 < s.C else s.N
        return ' '.join(s.inv[int(x)] for x in s.T[a:b])


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    A, L = Idx(args[0]), Idx(args[1])
    a, b = (int(args[2]), int(args[3])) if len(args) >= 4 else (1, 999)
    width = 160
    for x in sys.argv:
        if x.startswith('--w='): width = int(x[4:])
    NC = A.C + L.C
    low = tot = 0
    for n in range(a, b + 1):
        if not os.path.exists(os.path.join(HERE, '..', 'upp', 'q%03d.txt' % n)): continue
        res, st = V.check(n, show_all='--all' in sys.argv)
        for ln, kind, label, cov, miss, soft, text, nt in res:
            if kind not in ('БЕЗ ССЫЛКИ',) and '--all' not in sys.argv: continue
            if kind in ('НЕТ', 'БЛОК'): continue
            ct = V.toks(text)
            toks = list(dict.fromkeys(s for s, _ in ct))
            if len(toks) < 2: continue
            word = dict((s, w) for s, w in ct)
            wt = {w: max(0.3, math.log(NC / (1 + A.df(w) + L.df(w)))) for w in toks}
            T = sum(wt.values())
            ba = A.best(toks, wt)[0]; bl = L.best(toks, wt)[0]
            ca, cl = ba[0] / T, bl[0] / T
            un = [word[w] for w in toks if w not in ba[1] and w not in bl[1]]
            tot += 1
            if not un and max(ca, cl) >= 0.8: continue
            low += 1
            src = (A.names[A.cfile[ba[2]]] if ca >= cl else L.names[L.cfile[bl[2]]])[7:60]
            print('%d:%d А%d Л%d %s | %s | %s' % (n, ln, round(ca * 100), round(cl * 100), ' '.join('!' + w for w in un), text[:width], src))
            if '--show' in sys.argv:
                print('      ▸А ' + A.text(ba[2])[:500]); print('      ▸Л ' + L.text(bl[2])[:500])
    print('утверждений без ссылки %d, из них для чтения %d' % (tot, low))
