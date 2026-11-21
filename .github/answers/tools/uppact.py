#!/usr/bin/env python3
"""Сверка всех утверждений ответов УПП с актами и судебной практикой, кроме кодексов и Конституции.

uppact.py IDX_ACTS DIR_ACTS [N1 N2] [--min=60] [--w=380] [--num]
Для каждого утверждения (со ссылкой на норму или без неё) берутся лучшие отрезки указателя актов,
кодексы и Конституция пропускаются, в найденном файле ищется окно из двух предложений и печатается пара.
--num — печатать только пары, где в утверждении или в найденном месте есть число.
"""
import sys, os, re, math, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K, uppver as V
from uppsent import Idx
SKIP = re.compile(r'Уголовно-процессуальный кодекс|Уголовный кодекс|Конституция РФ|введении в действие')
CACHE = {}
def sents_of(path):
    if path not in CACHE:
        t = open(path, encoding='utf-8', errors='ignore').read()
        t = re.sub(r'-\s*\n\s*', '', t); t = re.sub(r'\s+', ' ', t)
        ss = [x for x in re.split(r'(?<=[.;!?])\s+', t) if len(x) > 25]
        CACHE[path] = (ss, [set(K.tokens(x)) for x in ss])
    return CACHE[path]
args = [a for a in sys.argv[1:] if not a.startswith('--')]
A, DA = Idx(args[0]), args[1]
a, b = (int(args[2]), int(args[3])) if len(args) >= 4 else (1, 999)
mn, width = 60, 380
for x in sys.argv:
    if x.startswith('--min='): mn = int(x[6:])
    if x.startswith('--w='): width = int(x[4:])
files = {os.path.basename(f)[:6]: f for f in glob.glob(os.path.join(DA, '*.txt'))}
tot = out = 0
for n in range(a, b + 1):
    p = os.path.join(HERE, '..', 'upp', 'q%03d.txt' % n)
    if not os.path.exists(p): continue
    for ln, line in enumerate(open(p, encoding='utf-8'), 1):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('!!'): continue
        for cl in re.split(r'(?<=[.;])\s+', line):
            ct = V.toks(cl); toks = list(dict.fromkeys(s for s, _ in ct))
            if len(toks) < 5: continue
            tot += 1
            wt = {w: max(0.3, math.log(A.C / (1 + A.df(w)))) for w in toks}; T = sum(wt.values())
            best = (0, '', '')
            seen = set()
            for sc, got, c in A.best(toks, wt, k=8):
                nm = A.names[A.cfile[c]]
                if SKIP.search(nm) or nm[:6] not in files or nm[:6] in seen: continue
                seen.add(nm[:6])
                ss, st = sents_of(files[nm[:6]])
                for i in range(len(ss)):
                    have = st[i] | (st[i + 1] if i + 1 < len(ss) else set())
                    s2 = sum(wt[w] for w in toks if w in have)
                    if s2 > best[0]: best = (s2, ' '.join(ss[i:i + 2]), nm)
            cv = round(100 * best[0] / T)
            if cv < mn: continue
            c2 = re.sub(r'\*\*|//', '', cl)
            if '--num' in sys.argv and not (re.search(r'\d', V.K.REFNUM.sub('', c2)) ): continue
            out += 1
            print('%d:%d [%d%%] %s' % (n, ln, cv, c2[:width]))
            print('    ▸ [' + best[2][7:60] + '] ' + best[1][:width])
print('утверждений %d, пар %d' % (tot, out))
