#!/usr/bin/env python3
"""g.py REGEX ЧАСТЬ_ИМЕНИ [ctx=220] [max=3] [dir=/tmp/src]"""
import sys,re,os,glob
rx=re.compile(sys.argv[1],re.I|re.S); part=sys.argv[2]; ctx=int(sys.argv[3]) if len(sys.argv)>3 else 220; mx=int(sys.argv[4]) if len(sys.argv)>4 else 3
dirs=sys.argv[5:] or ['/tmp/src']
n=0; seen=set()
for d in dirs:
    for f in sorted(os.listdir(d)):
        if not re.search(part,f,re.I): continue
        t=re.sub(r'\s+',' ',open(os.path.join(d,f),encoding='utf-8',errors='ignore').read()); k=0
        for m in rx.finditer(t):
            sn=t[max(0,m.start()-ctx//3):m.end()+ctx]; key=re.sub(r'\W','',sn)[:120]
            if key in seen: continue
            seen.add(key); print('[%s] …%s…'%(f[:46],sn)); k+=1; n+=1
            if k>=mx: break
if not n: print('НЕТ: %s в %s'%(sys.argv[1],part))
