#!/usr/bin/env python3
"""Проверка прямых цитат: каждая цитата в «ёлочках» длиной от N знаков ищется в текстах источников.
Запуск: quotes.py ПАПКА_ОТВЕТОВ ПАПКА_ТЕКСТОВ [N=25] [доп. текстовый файл ...]
Для ненайденной цитаты печатается место источника, где совпало больше всего её трёхсловий (подсказка для правки)."""
import sys,glob,re,os,collections
def norm(s): return re.sub(r'[^а-яa-z0-9]+',' ',s.lower().replace('ё','е')).strip()
def load(f):
    t=open(f,encoding='utf-8',errors='ignore').read()
    t=re.sub(r'(?m)^@@.*$',' ',t); t=re.sub(r'[-\u00ad]\s*\n\s*','',t)
    return norm(t)
ans,src=sys.argv[1],sys.argv[2]; N=int(sys.argv[3]) if len(sys.argv)>3 else 25
files=[f for f in sorted(glob.glob(src+'/*.txt'))]+sys.argv[4:]
texts=[load(f) for f in files]
ns=[t.replace(' ','') for t in texts]
def found(p):
    q=norm(p); qn=q.replace(' ','')
    if not qn: return True
    return any(qn in t for t in ns)
def hint(p):
    w=norm(p).split(); best=(0,None,None)
    grams=[' '.join(w[i:i+3]) for i in range(max(1,len(w)-2))]
    for fi,t in enumerate(texts):
        hits=[t.find(g) for g in grams]; hits=[h for h in hits if h>=0]
        if len(hits)>best[0]: best=(len(hits),fi,sorted(hits)[len(hits)//2])
    if not best[0]: return '— нигде'
    n,fi,pos=best; t=texts[fi]
    return '%d/%d [%s] …%s…'%(n,len(grams),os.path.basename(files[fi])[:46],t[max(0,pos-160):pos+len(norm(p))+160])
tot=bad=0
for f in sorted(glob.glob(ans+'/q*.txt')):
    for i,l in enumerate(open(f,encoding='utf-8'),1):
        if l.startswith('@@'): continue
        for q in re.findall(r'«([^«»]{%d,})»'%N,l):
            parts=[p for p in re.split(r'\s*(?:…|\.\.\.|\[[^\]]*\]|//)\s*',q) if len(p)>=12]
            tot+=1
            miss=[p for p in parts if not found(p)]
            if miss:
                bad+=1; print('%s:%d  «%s»'%(os.path.basename(f)[:4],i,miss[0][:260])); print('      '+hint(miss[0])[:700])
print('цитат',tot,'не найдено',bad)
