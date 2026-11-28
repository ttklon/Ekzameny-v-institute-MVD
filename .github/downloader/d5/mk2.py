# -*- coding: utf-8 -*-
"""Вторая волна заданий: загрузка отобранных изданий библиотеки и статей (по дисциплинам, параллельными списками)."""
import os, sys, json, glob, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5
os.chdir(ROOT)
SH = '.github/downloader/shards/'
QP = D5 + 'queued.txt'   # цели, уже поставленные в очередь прежними волнами (повторно не ставятся)
QUEUED = set(open(QP, encoding='utf-8').read().split('\n')) if os.path.exists(QP) else set()
for f in glob.glob(SH + '*.tsv'):
    for l in open(f, encoding='utf-8'):
        r = l.rstrip('\n').split('\t')
        if len(r) == 3: QUEUED.add(r[2])
    os.remove(f)
open(QP, 'w', encoding='utf-8').write('\n'.join(sorted(QUEUED)))
RETRY = set(open(D5 + 'retry.txt', encoding='utf-8').read().split()) if os.path.exists(D5 + 'retry.txt') else set()
QUEUED -= RETRY
def write(name, rows):
    with open(SH + name + '.tsv', 'w', encoding='utf-8') as f:
        for r in rows: f.write('\t'.join(r) + '\n')
    print(name, len(rows))
for code in DISC:
    mp = D5 + 'manifest_%s.json' % code
    placed = {m['key'] for m in json.load(open(mp, encoding='utf-8'))} if os.path.exists(mp) else set()
    p = D5 + 'lib_%s_list.json' % code
    if os.path.exists(p):
        L = json.load(open(p, encoding='utf-8'))
        rows = [('get', urllib.parse.quote(o['url'], safe=':/'), '.work/d5/%s/lib/%s.pdf' % (code, o['n'])) for o in L if o['n'] not in placed and not os.path.exists('.work/d5/%s/lib/%s.pdf' % (code, o['n'])) and '.work/d5/%s/lib/%s.pdf' % (code, o['n']) not in QUEUED]
        k = max(1, (len(rows) + 44) // 45)
        for i in range(k):
            if rows: write('lib_%s%s' % (code, '' if k == 1 else '_%d' % (i + 1)), rows[i::k])
    S = []
    for p in (D5 + 'cyber_%s_selected.json' % code, D5 + 'cyber_%s2_selected.json' % code):
        if os.path.exists(p): S += json.load(open(p, encoding='utf-8'))
    if S:
        rows = [('get', 'https://cyberleninka.ru%s/pdf' % c['slug'], '.work/d5/%s/art/%s.pdf' % (code, c['n'])) for c in S if c['n'] not in placed and not os.path.exists('.work/d5/%s/art/%s.pdf' % (code, c['n'])) and '.work/d5/%s/art/%s.pdf' % (code, c['n']) not in QUEUED]
        if not rows: continue
        k = max(1, (len(rows) + 179) // 180)
        for i in range(k): write('art_%s%s' % (code, '' if k == 1 else '_%d' % (i + 1)), rows[i::k])
if os.path.exists(D5 + 'extra_tasks.tsv'):
    rows = [tuple(l.rstrip('\n').split('\t')) for l in open(D5 + 'extra_tasks.tsv', encoding='utf-8') if l.strip() and not l.startswith('#')]
    rows = [r for r in rows if r[2] not in QUEUED and not os.path.exists(r[2])]
    for i in range(0, len(rows), 5): write('extra_%d' % (i // 5 + 1), rows[i:i + 5])
