#!/usr/bin/env python3
"""ol25.py A B — оглавление ответов A..B с числом слов по разделам (для выбора разделов, которые убираются)."""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import cut25
a, b = int(sys.argv[1]), int(sys.argv[2])
for n in range(a, b + 1):
    txt = open(cut25.A + 'q%03d.txt' % n, encoding='utf-8').read(); L = txt.split('\n')
    w0 = len(txt.split()); tg = int(w0 * cut25.F_DEF); secs = []; cur = None
    for l in L[1:]:
        if l.startswith('## '): cur = [re.sub(r'^## \d+\. ', '', l), 0]; secs.append(cur)
        elif cur and not l.startswith('!!'): cur[1] += len(l.split())
    title = re.sub(r'^# Вопрос \d+\. ', '', L[0])
    print('%d|%d→%d −%d|%s|%s' % (n, w0, tg, w0 - tg, title[:80], '|'.join('%d%s %s=%d' % (i + 1, 'P' if cut25.PRAV.search(h) else '', h[:24], w) for i, (h, w) in enumerate(secs))))
