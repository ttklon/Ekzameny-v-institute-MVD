#!/usr/bin/env python3
"""Сверка ответа УПП с одним актом (постановлением Пленума, законом): пары «утверждение — ближайшее место акта».

upppl.py N ФАЙЛ_АКТА.txt [--min=55] [--w=380]
Каждая строка ответа делится на утверждения; для каждого ищется окно из двух предложений акта
с наибольшим совпадением значимых слов. Печатаются пары с совпадением не ниже --min процентов.
"""
import sys, os, re, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K, uppver as V
args = [a for a in sys.argv[1:] if not a.startswith('--')]
n, path = int(args[0]), args[1]
mn, width = 55, 380
for x in sys.argv:
    if x.startswith('--min='): mn = int(x[6:])
    if x.startswith('--w='): width = int(x[4:])
t = open(path, encoding='utf-8', errors='ignore').read(); t = re.sub(r'-\s*\n\s*', '', t); t = re.sub(r'\s+', ' ', t)
ss = [x for x in re.split(r'(?<=[.;!?])\s+', t) if len(x) > 25]
st = [set(K.tokens(x)) for x in ss]
df = {}
for s in st:
    for w in s: df[w] = df.get(w, 0) + 1
N = len(ss)
out = 0
for ln, line in enumerate(open(os.path.join(HERE, '..', 'upp', 'q%03d.txt' % n), encoding='utf-8'), 1):
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('!!'): continue
    for cl in re.split(r'(?<=[.;])\s+', line):
        ct = V.toks(cl); toks = list(dict.fromkeys(s for s, _ in ct))
        if len(toks) < 4: continue
        wt = {w: math.log(1 + N / (1 + df.get(w, 0))) for w in toks}; T = sum(wt.values())
        best = (0, 0)
        for i in range(N):
            have = st[i] | (st[i + 1] if i + 1 < N else set())
            sc = sum(wt[w] for w in toks if w in have)
            if sc > best[0]: best = (sc, i)
        cv = round(100 * best[0] / T)
        if cv < mn: continue
        out += 1
        print('%d:%d [%d%%] %s' % (n, ln, cv, re.sub(r'\*\*|//', '', cl)[:width]))
        print('    ▸ ' + ' '.join(ss[best[1]:best[1] + 2])[:width])
print('пар: %d' % out)
