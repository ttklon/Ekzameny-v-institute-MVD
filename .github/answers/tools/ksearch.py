#!/usr/bin/env python3
"""ksearch.py SRC ШАБЛОН [ШАБЛОН…] [-m МИН] [-c ЗНАКОВ] [-o КОД,…] — где в источниках дисциплины говорится о теме.

SRC — папка, которую сделал kextract.py. Шаблоны — регулярные выражения (без учёта регистра; пробел в шаблоне
совпадает с любыми пробелами и переносами строк). Для каждого источника печатается: код, число совпадений,
страницы файла с совпадениями (в скобках — сколько на странице) и имя. Просматриваются все источники без исключения;
в таблицу попадают те, где совпадений не меньше МИН (по умолчанию 1), в конце — сколько источников просмотрено.
-c ЗНАКОВ — напечатать под каждым источником совпадения с окружением такой длины.
-o КОДЫ — только источники с этими кодами (первые шесть знаков имени файла).
"""
import sys, os, re, glob
a = sys.argv[1:]; src = a.pop(0); mn = 1; ctx = 0; only = None; pats = []
while a:
    x = a.pop(0)
    if x == '-m': mn = int(a.pop(0))
    elif x == '-c': ctx = int(a.pop(0))
    elif x == '-o': only = a.pop(0).split(',')
    else: pats.append(x)
rx = re.compile('|'.join('(?:%s)' % p.replace(' ', r'\s+') for p in pats), re.I)
idx = {l.split('\t')[0]: l.split('\t')[1] for l in open(os.path.join(src, '_index.tsv'), encoding='utf-8')}
res = []; seen = 0
for name, rel in sorted(idx.items(), key=lambda kv: kv[1]):
    if only and name[:6] not in only: continue
    seen += 1
    t = open(os.path.join(src, name), encoding='utf-8').read()
    t = re.sub(r'(?<=[а-яё])-\n(?=[а-яё])', '', t)
    marks = [(m.start(), int(m.group(1)), m.group(2)) for m in re.finditer(r'@@ (\d+) \| (\S+)\n', t)]
    def page(pos, marks=marks):
        lo, hi = 0, len(marks) - 1; r = (0, '-')
        while lo <= hi:
            mid = (lo + hi) // 2
            if marks[mid][0] <= pos: r = marks[mid][1:]; lo = mid + 1
            else: hi = mid - 1
        return r
    hits = [(m.start(), m.end()) for m in rx.finditer(t)]
    if len(hits) < mn: continue
    pg = {}
    for s, e in hits: pg[page(s)[0]] = pg.get(page(s)[0], 0) + 1
    res.append((rel.split('/')[0][:2], -len(hits), name, pg, hits, t, page))
for top, n, name, pg, hits, t, page in sorted(res, key=lambda r: (r[0], r[1])):
    ps = ' '.join('%d(%d)' % (p, c) if c > 1 else str(p) for p, c in sorted(pg.items()))
    print('%s %s %4d  %s  | стр. %s' % (top, name[:6], -n, name[7:-4][:70], ps[:160]))
    if ctx:
        last = -10**9
        for s, e in hits:
            if s < last: continue
            a0 = max(0, s - ctx // 3); b0 = min(len(t), e + ctx * 2 // 3); last = b0
            frag = re.sub(r'@@ \d+ \| \S+\n', ' ', t[a0:b0]); frag = re.sub(r'\s+', ' ', frag)
            print('      [с. %d/%s] %s' % (page(s)[0], page(s)[1], frag))
print('просмотрено источников:', seen, '| с совпадениями:', len(res))
