#!/usr/bin/env python3
"""punkt26.py SRC ЧАСТЬ_ИМЕНИ_ФАЙЛА N [N…] [--w=N] — текст пункта N из акта без статей (постановление Пленума, приказ, правила, положение).
Пункты ищутся подряд по возрастанию номера, поэтому «5.» в середине другого пункта не принимается за пункт 5."""
import sys, os, re
a = [x for x in sys.argv[1:] if not x.startswith('--')]
o = dict(x[2:].split('=') for x in sys.argv[1:] if x.startswith('--'))
W = int(o.get('w', 600))
fs = sorted(f for f in os.listdir(a[0]) if re.search(a[1], f))
if not fs: sys.exit('нет файла')
f = fs[int(o.get('f', 0))]
T = re.sub(r'\s+', ' ', open(os.path.join(a[0], f), encoding='utf-8', errors='ignore').read())
start = T.find(o['from']) if 'from' in o else 0
pos = max(start, 0); P = {}
for n in range(1, 400):
    m = re.search(r'(?<![\d.№N]) ?(?<!\d)%d\. ?(?=[А-ЯЁ«(])' % n, T[pos:pos + int(o.get('gap', 40000))])
    if not m:
        if n > max([int(float(x)) for x in a[2:]] + [0]): break
        continue
    P[n] = pos + m.start(); pos += m.end()
keys = sorted(P)
print('[%s] пунктов найдено: %d' % (f[:60], len(P)))
for x in a[2:]:
    if '.' in x:
        n = int(x.split('.')[0])
        if n not in P: print('п. %s: НЕТ' % x); continue
        nx = [k for k in keys if k > n]; e = P[nx[0]] if nx else len(T)
        m = re.search(r'(?<![\d]) ?%s\.? ' % re.escape(x), T[P[n]:e])
        print('п. %s: %s' % (x, T[P[n] + m.start(): P[n] + m.start() + W] if m else 'НЕТ подпункта; ' + T[P[n]:P[n] + 200]))
    else:
        n = int(x)
        if n not in P: print('п. %d: НЕТ' % n); continue
        nx = [k for k in keys if k > n]; e = P[nx[0]] if nx else len(T)
        print('п. %d: %s' % (n, T[P[n]:min(e, P[n] + W)]))
