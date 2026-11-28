#!/usr/bin/env python3
"""numx2.py SRC DIR_ОТВЕТОВ — числа с единицами (сутки, дни, часы, годы, месяцы, рубли, минуты, метры, проценты) рядом со ссылкой
на акт (кроме КоАП РФ) ищутся в тексте этого акта цифрами и словами; печатаются ненайденные."""
import sys, os, re, glob, io, contextlib
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
src=sys.argv[1]; A=sys.argv[2]
import cut25
cut25.A=A if A.endswith('/') else A+'/'
with contextlib.redirect_stdout(io.StringIO()):
    import qcheck2
from sancheck import gen  # noqa
U=['','один','два','три','четыре','пять','шесть','семь','восемь','девять','десять','одиннадцать','двенадцать','тринадцать','четырнадцать','пятнадцать','шестнадцать','семнадцать','восемнадцать','девятнадцать']
T=['','','двадцать','тридцать','сорок','пятьдесят','шестьдесят','семьдесят','восемьдесят','девяносто']
H=['','сто','двести','триста','четыреста','пятьсот','шестьсот','семьсот','восемьсот','девятьсот']
def nom3(n,fem=False):
    w=[H[n//100]]; r=n%100
    if r<20: w.append({1:'одна',2:'две'}.get(r,U[r]) if fem else U[r])
    else: w+= [T[r//10], ({1:'одна',2:'две'}.get(r%10,U[r%10]) if fem else U[r%10])]
    return ''.join(w)
def nom(n):
    s=''
    if n>=1000000: m=n//1000000; s+=nom3(m)+'миллион'; n%=1000000
    if n>=1000: k=n//1000; s+=nom3(k,True)+'тысяч'; n%=1000
    return s+nom3(n)
files={}
for l in open(os.path.join(src,'_index.tsv'),encoding='utf-8'):
    nm,rel=l.rstrip('\n').split('\t'); files[rel]=os.path.join(src,nm)
cache={}
def text(fp):
    if fp not in cache:
        raws=[open(f,encoding='utf-8',errors='replace').read() for n,f in sorted(files.items()) if re.search(fp,n)]
        raw=' '.join(raws).lower().replace('ё','е')
        cache[fp]=(re.sub(r'\s+',' ',raw), re.sub(r'[^а-яa-z0-9]','',raw))
    return cache[fp]
UN=[('сут','сут'),('дн','дн|ден|дневн'),('день','дн|ден|дневн'),('час','час'),('лет','лет|год'),('год','лет|год'),('месяц','месяц|месячн'),('рубл','рубл'),('минут','минут'),('метр','метр'),('процент','процент'),('%','процент')]
NUM=r'(\d{1,3}(?:[  ]\d{3})+|\d+)'
PAT=re.compile(NUM+r'(?:\s*(тыс\.|млн))?\s*(суток|сутки|дней|дня|день|часов|часа|час|лет|года|год|месяц\w*|рубл\w*|минут\w*|метр\w*|процент\w*|%)')
END=re.compile(r'(?<![ (/]ч)(?<![ (/]п)(?<!ст)(?<!подп)(?<!гл)(?<![ (/]Ч)(?<!Ст)\. |; ')
tot=bad=0
only=set(int(x) for x in sys.argv[3:]) if len(sys.argv)>3 else None
for f in sorted(glob.glob(cut25.A+'q*.txt')):
    n=int(os.path.basename(f)[1:4])
    if only and n not in only: continue
    lines=open(f,encoding='utf-8').read().split('\n')
    pieces=[((i,0),l) for i,l in enumerate(lines) if l.strip()]
    res,names=cut25.resolve(pieces)
    for (i,_z),line in pieces:
        refs=[]
        for k,m in enumerate(cut25.REF.finditer(line)):
            disp=names.get(((i,0),k)); act,art=res.get(((i,0),k),(None,None))
            refs.append((m.start(),disp,art))
        if not refs: continue
        for m in PAT.finditer(line):
            v=int(re.sub(r'\D','',m.group(1)))*{None:1,'тыс.':1000,'млн':1000000}[m.group(2)]
            if v>2000000000 or (m.group(3).startswith(('год','лет')) and v>1900): continue
            unit=m.group(3)
            stem=[s for u,s in UN if unit.startswith(u)]
            if not stem: continue
            stem=stem[0]
            seg_l=line[:m.start()]; cut_l=max([x.start() for x in END.finditer(seg_l)] or [-1])
            cand=[r for r in refs if cut_l<r[0]<m.start()]
            ref=cand[-1] if cand else None
            if not ref:
                seg_r=line[m.end():]; e=([x.start() for x in END.finditer(seg_r)] or [len(seg_r)])[0]+m.end()
                cand=[r for r in refs if m.start()<r[0]<e]; ref=cand[0] if cand else None
            if not ref or not ref[1]: continue
            kind,fp=qcheck2.act_files(ref[1])
            if kind in ('KOAP','UNK') or not fp: continue
            raw,sq=text(fp)
            if not raw.strip(): continue
            tot+=1
            ds=str(v); ds2=re.sub(r'(?<=\d)(?=(\d{3})+$)',' ',ds)
            ok=re.search(r'(?<![\d.,])(?:%s|%s)(?:-?х?)?\s*-?\s*(?:%s)'%(re.escape(ds),re.escape(ds2),stem),raw) is not None
            if not ok:
                for w in {gen(v),nom(v)}:
                    if w and re.search(w+r'(?:%s)'%stem,sq): ok=True;break
            if not ok and stem=='процент' and re.search(r'(?<![\d.,])%s\s*(?:%%|процент)'%re.escape(ds),raw): ok=True
            if not ok:
                bad+=1; print('%03d:%d [%s%s] «%s» | %s'%(n,i+1,ref[1][:40],(' '+ref[2]) if ref[2] else '',m.group(0),line[max(0,m.start()-110):m.end()+60].replace('\n',' ')))
print('проверено',tot,'не найдено',bad)
