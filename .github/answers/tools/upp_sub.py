#!/usr/bin/env python3
"""sub.py N <<< 'старое\n=>\nновое\n@@\nстарое2\n=>\nновое2' — точечные замены в upp/qNNN.txt (каждое «старое» должно встретиться ровно столько раз, сколько указано: по умолчанию 1)."""
import sys
n = int(sys.argv[1])
p = '/home/user/Ekzameny-v-institute-MVD/.github/answers/upp/q%03d.txt' % n
t = open(p, encoding='utf-8').read()
for blk in sys.stdin.read().split('\n@@\n'):
    a, b = blk.split('\n=>\n')
    a = a.strip('\n'); b = b.strip('\n')
    c = t.count(a)
    if c != 1:
        print('!! %d вхождений: %s' % (c, a[:70])); continue
    t = t.replace(a, b)
open(p, 'w', encoding='utf-8').write(t)
print('ok', n)
