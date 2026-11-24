#!/usr/bin/env python3
"""rep.py ФАЙЛ — замены из стандартного ввода: строки «было ⇒ стало»; каждая «было» должна встретиться в файле ровно один раз."""
import sys
p=sys.argv[1]; x=open(p,encoding='utf-8').read()
for l in sys.stdin.read().split('\n'):
    if '⇒' not in l: continue
    a,b=l.split(' ⇒ ',1)
    assert x.count(a)==1,(p,x.count(a),a[:60])
    x=x.replace(a,b)
open(p,'w',encoding='utf-8').write(x)
