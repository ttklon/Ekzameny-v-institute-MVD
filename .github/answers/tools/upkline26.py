#!/usr/bin/env python3
"""upkline26.py N [ПОРОГ] [СЛОВ] — ответ УПП № N построчно против УПК РФ.
Для каждой строки со ссылкой //(ч. 2 ст. 108)// берётся текст названной части (tools/upk26.py). Печатаются строки, у которых
доля общих слов с нормой ниже ПОРОГА (по умолчанию 50 %), есть срок (сутки, часы, месяцы, годы), которого в норме нет, или названной части не существует.
Под строкой — отрезок нормы с наибольшим совпадением (СЛОВ, по умолчанию 38). Ссылка без статьи («ч. 3») примеряется ко всем статьям,
уже названным в ответе; выбранная помечена «?». Пометка не означает ошибку: пересказ своими словами даёт низкое совпадение — строка читается глазами.
    python3 tools/upkline26.py 63
    for n in $(seq 1 108); do python3 tools/upkline26.py $n; done
"""
import sys,re
sys.path.insert(0,'tools'); import upk26
N=int(sys.argv[1]); THR=int(sys.argv[2]) if len(sys.argv)>2 else 50; W=int(sys.argv[3]) if len(sys.argv)>3 else 38
A,_=upk26.load()
NUMW={'1':'одн|перв|сутки','2':'дв|втор','3':'тр','4':'четыр','5':'пят','6':'шест','7':'сем','8':'восьм|восем','9':'девят','10':'десят','12':'двенадцат','14':'четырнадцат','15':'пятнадцат','18':'восемнадцат','20':'двадцат','30':'тридцат','40':'сорок','45':'сорока пят','60':'шестидесят','90':'девяност'}
def nz(s): return s.lower().replace('ё','е')
def toks(s): return set(w[:5] for w in re.findall(r'[а-яё]{4,}',nz(s)))
def AR(x):
    r=[]
    for m in re.finditer(r'ст\. ((?:\d+(?:\.\d+)?(?:, | и |–)?)+)',x):
        r+=re.findall(r'\d+(?:\.\d+)?',m.group(1))
    return r
def plist(g):
    ps=re.search(r'ч\. ([\d\.,–\- и]+?)(?= ст|\)|$|,? п|;)',g); out=[]
    if not ps: return out
    for x in re.split(r'[, и]+',ps.group(1).strip()):
        x=x.rstrip('.')
        if re.search('[–-]',x):
            a,b=re.split('[–-]',x)[:2]
            try: out+=[str(k) for k in range(int(float(a)),int(float(b))+1)]
            except: out.append(a)
        elif x: out.append(x)
    return out
def text(art,ps):
    if art not in A: return None
    if not ps:
        P=upk26.parts(art); return ' '.join(str(v) for v in (P.values() if isinstance(P,dict) else P))
    r=[]
    for p in ps:
        try: t=upk26.part(art,p)
        except Exception: t=None
        if not t: return None
        r.append(t)
    return ' '.join(r)
seen=[]
for i,l in enumerate(open('upp/q%03d.txt'%N,encoding='utf-8').read().split('\n'),1):
    if not l.strip(): continue
    refs=[g for g in re.findall(r'//\(?([^/]+?)\)?//',l) if not re.search(r'УК|Конституц|Закон|ГК|ГПК|КоАП|Пленум|ФЗ|УИК',g)]
    body=re.sub(r'//[^/]+//','',l); lt=toks(body)
    got=[]
    for g in refs:
        for seg in re.split(r';\s*',g):
            arts=AR(seg); ps=plist(seg)
            if arts:
                for a in arts:
                    if a in seen: seen.remove(a)
                    seen.insert(0,a)
                # «ч. 1 ст. 50, ч. 2 ст. 51» — делим по запятой перед «ч.»
                for sub in re.split(r',\s*(?=ч\. |п\. )',seg):
                    a2=AR(sub)
                    for a in (a2 or arts[:1]):
                        t=text(a,plist(sub)); got.append(('%s ст. %s'%(','.join(plist(sub)) or '—',a),t))
            elif ps:
                best=None
                for a in seen[:8]:
                    t=text(a,ps)
                    if not t: continue
                    c=len(lt&toks(t))
                    if best is None or c>best[0]: best=(c,a,t)
                got.append(('%s ст. %s?'%(','.join(ps),best[1]),best[2]) if best else (','.join(ps)+' — статья не определена',None))
    if not got or l.startswith('#') or l.startswith('!!'): continue
    allv=nz(' '.join(re.sub(r'\s+',' ',t or '') for _,t in got)); vt=toks(allv)
    cov=100*len(lt&vt)//max(1,len(lt))
    nums=re.findall(r'(?<![\d.,])(\d{1,3})(?= (?:сут|час|дн|мес|лет|год|минут))',body)
    miss=[x for x in nums if not re.search(r'(?<!\d)%s(?!\d)'%x,allv) and not re.search(NUMW.get(x,'#####'),allv)]
    none=[k for k,t in got if t is None]
    if cov>=THR and not miss and not none: continue
    print('%d: ~%d%%%s%s %s'%(i,cov,(' ЧИСЛА '+' '.join(miss)) if miss else '',(' НЕТ '+'; '.join(none)) if none else '',l[:520]))
    for k,t in got:
        if not t: continue
        ws=re.sub(r'\s+',' ',t).split(); bi=0
        if len(ws)>W:
            sc=[1 if nz(w).strip('.,;:()«»"')[:5] in lt else 0 for w in ws]; c=sum(sc[:W]); b=c
            for j in range(1,len(ws)-W+1):
                c+=sc[j+W-1]-sc[j-1]
                if c>b: b=c;bi=j
        print('      [%s] %s%s'%(k,'…' if bi else '',' '.join(ws[bi:bi+W])))
