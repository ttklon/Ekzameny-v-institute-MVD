#!/usr/bin/env python3
"""find.py ПАПКА_ТЕКСТОВ [-f ЧАСТЬ_ИМЕНИ] [-k СКОЛЬКО=2] [-w ШИРИНА=250] РЕГ [РЕГ…] — места в текстах источников по регулярному выражению
(пробелы и переносы строк сведены к одному пробелу, «ё» = «е», регистр не важен)."""
import sys,glob,re,os
A=sys.argv[1:]; src=A.pop(0); name=None; K=2; Wd=250
while A and A[0] in ('-f','-k','-w'):
    o=A.pop(0); v=A.pop(0)
    if o=='-f': name=v
    elif o=='-k': K=int(v)
    else: Wd=int(v)
for pat in A:
    n=0; rx=re.compile(pat.replace('ё','е'),re.I)
    for f in sorted(glob.glob(src+'/*.txt')):
        if name and name.lower() not in os.path.basename(f).lower(): continue
        t=open(f,encoding='utf-8',errors='ignore').read().replace('ё','е'); t=re.sub(r'(?m)^@@.*$',' ',t); t=re.sub(r'[-\u00ad]\s*\n\s*','',t); t=re.sub(r'\s+',' ',t)
        for m in rx.finditer(t):
            print('[%s] %s: …%s…'%(pat[:28],os.path.basename(f)[:44],t[max(0,m.start()-Wd):m.end()+Wd])); n+=1
            if n>=K: break
        if n>=K: break
    if not n: print('[%s] НЕТ'%pat[:40])
