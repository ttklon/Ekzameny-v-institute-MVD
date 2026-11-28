import re,sys,glob,os
subj,src=sys.argv[1],sys.argv[2]; thr=float(sys.argv[3]) if len(sys.argv)>3 else 0.5
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..',subj)
MON={m:i+1 for i,m in enumerate('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split())}
FILES={}
for f in glob.glob(src+'/*Постановление Пленума*'):
    m=re.search(r'от (\d\d\.\d\d\.\d{4}) № (\d+)',os.path.basename(f))
    if m: FILES.setdefault(m.group(2),{})[m.group(1)]=f
TXT={}
def text(f):
    if f not in TXT: TXT[f]=re.sub(r'\s+',' ',open(f,encoding='utf-8').read())
    return TXT[f]
def punkt(f,n):
    t=text(f); n=str(n)
    ms=list(re.finditer(r'(?<=[ .)»"]) ?'+re.escape(n).replace(r'\.',r'\s?\.?\s?')+r'\. ?(?=[А-ЯЁ«(])',t))
    if not ms: return None
    best=''
    for m in ms:
        s=m.start()
        nx=str(int(float(n))+1) if '.' not in n else None
        e=len(t)
        m2=re.search(r'(?<=[ .)»"]) ?%s\. ?(?=[А-ЯЁ«(])'%nx,t[s+3:]) if nx else None
        if m2: e=s+3+m2.start()
        seg=t[s:min(e,s+9000)]
        if len(seg)>len(best): best=seg
    return best
STOP=set('это этот эта эти того тому также либо если когда может могут должен должна должны быть есть был были будет который которая которые которых которого которым ними него неё нее них или что как для при над под без про через между после перед только уже ещё еще так там тут где кто чем все всех всем свой своя свои своих своего себя нужно можно нельзя пленум пленума верховного суда российской федерации постановление постановления постановлении пункт пункта пункте разъяснения разъяснению'.split())
def st(s):
    s=s.lower().replace('ё','е'); return {w[:5] for w in re.findall(r'[а-я]{4,}',s) if w not in STOP}
def dnorm(s):
    m=re.match(r'(\d{1,2}) ([а-я]+) (\d{4})',s)
    if m and m.group(2) in MON: return '%02d.%02d.%s'%(int(m.group(1)),MON[m.group(2)],m.group(3))
    return s
tot=0;fl=0;nf=0
for f in sorted(glob.glob(A+'/q[0-9][0-9][0-9].txt')):
    q=int(os.path.basename(f)[1:4]); t=open(f,encoding='utf-8').read(); L=t.split('\n')
    alias={}  # num -> date
    for m in re.finditer(r'от (\d\d\.\d\d\.\d{4}|\d{1,2} [а-я]+ \d{4})(?: года)? № (\d+)\b(?!-)',t): alias.setdefault(m.group(2),dnorm(m.group(1)))
    last=None
    for i,l in enumerate(L,1):
        for m in re.finditer(r'№ (\d+)\b(?!-|н)',l):
            if m.group(1) in FILES: last_in_line=m.group(1)
        mm=[m.group(1) for m in re.finditer(r'[Пп]остановлени\w+[^№;]{0,140}№ (\d+)\b',l)]
        for c in re.finditer(r'пункт\w* ((?:\d+(?:\.\d+)?)(?:(?:, | и |–)\d+(?:\.\d+)?)*)(?! (?:част|стат))([^;)/]{0,160})',l):
            rest=c.group(2)
            if re.search(r'стать|Положени|Правил|Обзор|Указ|устав|приказ|Основ|Инструкц|Порядк|Регламент',rest[:60]): continue
            mnum=re.search(r'№ (\d+)\b',rest)
            num=mnum.group(1) if mnum else (mm[-1] if mm else last)
            if 'постановлен' not in rest and not mm and not last: continue
            if not num or num not in FILES: continue
            ns=re.split(r', | и ',c.group(1)); pts=[]
            for x in ns:
                if '–' in x:
                    a,b=x.split('–'); pts+= [str(k) for k in range(int(a),int(b)+1)] if a.isdigit() and b.isdigit() else [a,b]
                else: pts.append(x)
            cand=FILES[num]; d=alias.get(num)
            fs=[cand[d]] if d in cand else list(cand.values())
            body=re.sub(r'//\([^)]*\)//',' ',l); a=st(body)
            if len(a)<4:
                # header line: use following bullet lines until blank
                j=i; extra=[]
                while j<len(L) and L[j].startswith('- '): extra.append(L[j]); j+=1
                a=st(' '.join(extra)) if extra else a
            if len(a)<4: continue
            tot+=1; best=0; found=False
            for ff in fs:
                seg=' '.join(filter(None,(punkt(ff,p) for p in pts)))
                if seg: found=True; best=max(best,len(a&st(seg))/len(a))
            if not found: nf+=1; print('%d:%d НЕТ ПУНКТА %s № %s | %s'%(q,i,pts,num,l[:200])); continue
            if best<thr: fl+=1; print('%d:%d %.0f%% п.%s № %s (%s) | %s'%(q,i,best*100,','.join(pts),num,d,l[:300]))
        if mm: last=mm[-1]
print('ссылок на пункты постановлений Пленума:',tot,'ниже порога:',fl,'пункт не найден:',nf)
