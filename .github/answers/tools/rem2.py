#!/usr/bin/env python3
"""rem2.py [N…] [apply] — разделы «## », которые были в редакции 30db505 и которых нет теперь (слова в скобках);
apply возвращает их все функцией sec() на прежнее место."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(os.path.join(HERE, '..'))
import normfixB25 as B, norm25 as N
args = sys.argv[1:]; apply = 'apply' in args; only = {int(x) for x in args if x.isdigit()}
tot = w = 0
for q in range(1, 150):
    if only and q not in only: continue
    o = N.old(q).split('\n'); cur = {N.hk(l) for l in B.rd(q) if l.startswith('## ')}
    miss = []
    for i, l in enumerate(o):
        if l.startswith('## ') and N.hk(l) not in cur:
            j = next((k for k in range(i + 1, len(o)) if o[k].startswith('## ') or o[k].startswith('!! ')), len(o))
            miss.append((N.hk(l), sum(len(x.split()) for x in o[i + 1:j])))
    for h, n in miss:
        tot += 1; w += n
        if apply: B.sec(q, h)
        else: print('q%03d  %s (%d)' % (q, h, n))
print('разделов', tot, 'слов', w)
