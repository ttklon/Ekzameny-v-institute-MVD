#!/usr/bin/env python3
"""Проверка прямых цитат: каждая цитата в «ёлочках» длиной от N знаков ищется в текстах источников.
Запуск: quotes.py ПАПКА_ОТВЕТОВ ПАПКА_ТЕКСТОВ [N=40] [доп. текстовый файл ...]"""
import sys,glob,re,os
norm=lambda s: re.sub(r'[^а-яa-z0-9]+',' ',s.lower().replace('ё','е')).strip()
ans,src=sys.argv[1],sys.argv[2]; N=int(sys.argv[3]) if len(sys.argv)>3 else 40
big=[]
for f in sorted(glob.glob(src+'/*'))+sys.argv[4:]:
    try: big.append(norm(open(f,encoding='utf-8',errors='ignore').read()))
    except Exception as e: pass
big=' \n '.join(big); big_ns=big.replace(' ','')
tot=bad=0
for f in sorted(glob.glob(ans+'/q*.txt')):
    for i,l in enumerate(open(f,encoding='utf-8'),1):
        if l.startswith('@@'): continue
        for q in re.findall(r'«([^«»]{%d,})»'%N,l):
            parts=[p for p in re.split(r'\s*(?:…|\.\.\.|\[[^\]]*\])\s*',q) if len(p)>=15]
            tot+=1
            miss=[p for p in parts if norm(p) not in big and norm(p).replace(' ','') not in big_ns]
            if miss: bad+=1; print('%s:%d  %s'%(os.path.basename(f)[:4],i,miss[0][:230]))
print('цитат',tot,'не найдено',bad)
