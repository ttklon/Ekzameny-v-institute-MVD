#!/usr/bin/env python3
"""sanpart26.py SRC ПАПКА|ФАЙЛ… — санкции КоАП РФ по частям.
Строка ответа делится на отрезки (между «;» и точками). Числа отрезка (рубли, сутки, часы) ищутся в санкции той части статьи КоАП,
которая названа в этом отрезке; если ссылки в отрезке нет — берётся последняя ссылка строки, затем статья из заголовка раздела,
из строки «Норма: ст. …» или из начала предыдущего пункта того же раздела. Ключ -v печатает отрезки, для которых статья не определена.
Числа санкций в кодексе записаны словами («от одной тысячи пятисот») — переводятся в цифры.
SRC — папка с текстами источников (tools/extract_src.py). Пометка не означает ошибку: суммы ущерба, пороги стоимости, срок задержания
в 48 часов в санкции не входят — такие отрезки читаются глазами.
    python3 tools/sanpart26.py /tmp/src adp2
"""
import sys,re,glob,os
SRC=sys.argv[1]
# --- текст КоАП ---
def _load():
    f=max(glob.glob(SRC+'/e7501c*.txt'),key=lambda x:len(x))
    t=re.sub(r'\s+',' ',open(f,encoding='utf-8',errors='replace').read())
    t=re.sub(r'\((?:В редакции|Дополнение|Абзац|Пункт|Часть|Утратил|Статья|Наименование|Подпункт|Примечани)[^()]*\)','',t)
    return t
T=_load()
def art(n,W=80000):
    p=n.split('.'); pat=r'Статья '+re.escape(p[0])+r'\.'+p[1]+(r' '+p[2] if len(p)>2 else r'')+r' ?\. ?[А-ЯЁ]'
    ms=list(re.finditer(pat,T))
    if not ms: return ''
    s=T[ms[-1].start():ms[-1].start()+W]
    e=re.search(r' Статья \d+\.\d+(?: \d+)? ?\. ?[А-ЯЁ]| ГЛАВА \d+',s[20:])
    return s[:e.start()+20] if e else s
def parts(a):
    s=re.sub(r'\s+',' ',art(a))
    ms=list(re.finditer(r'(?:(?<=[.\)»]) |^)(\d{1,2}(?: \d{1,2})? ?\.) (?=[А-Я])',s))
    if not ms: return [('—',s)]
    out=[('загл',s[:ms[0].start()])]
    for i,m in enumerate(ms):
        e=ms[i+1].start() if i+1<len(ms) else len(s)
        out.append((m.group(1).replace(' .','').replace('.','').replace(' ','.'),s[m.end():e]))
    return out
# --- числительные ---
U={'одного':1,'одной':1,'одну':1,'один':1,'двух':2,'трех':3,'четырех':4,'пяти':5,'шести':6,'семи':7,'восьми':8,'девяти':9,'десяти':10,'одиннадцати':11,'двенадцати':12,'тринадцати':13,'четырнадцати':14,'пятнадцати':15,'шестнадцати':16,'семнадцати':17,'восемнадцати':18,'девятнадцати':19,'двадцати':20,'тридцати':30,'сорока':40,'пятидесяти':50,'шестидесяти':60,'семидесяти':70,'восьмидесяти':80,'девяноста':90,'ста':100,'двухсот':200,'трехсот':300,'четырехсот':400,'пятисот':500,'шестисот':600,'семисот':700,'восьмисот':800,'девятисот':900,'полутора':1.5,
 'два':2,'две':2,'три':3,'четыре':4,'пять':5,'шесть':6,'семь':7,'восемь':8,'девять':9,'десять':10,'двадцать':20,'тридцать':30,'сорок':40,'пятьдесят':50,'сто':100,'двести':200,'триста':300,'пятьсот':500}
W='|'.join(sorted(U,key=len,reverse=True))
PAT=re.compile(r'\b(?:(?:%s|тысяч[иа]?|миллион(?:ов|а)?)\b\s*)+'%W)
def conv(s):
    s=s.replace('ё','е')
    def f(m):
        ws=m.group(0).split(); tot=0; cur=0; seen=False
        for w in ws:
            if w.startswith('тысяч'): tot+=(cur or 1)*1000; cur=0; seen=True
            elif w.startswith('миллион'): tot+=(cur or 1)*1000000; cur=0; seen=True
            else: cur+=U[w]; seen=True
        v=tot+cur
        return ('%d'%v if v==int(v) else '%g'%v)+' '
    return PAT.sub(f,s)
def nums(s):
    s=conv(s.lower()); s=re.sub(r'(?<=\d)[ \u00a0](?=\d{3}\b)','',s); s=s.replace(',','.')
    return [x for x in re.findall(r'\d+(?:\.\d+)?',s)]
# --- сверка ---
cache={}
def P(a):
    if a not in cache:
        cache[a]={}
        try:
            for k,v in parts(a): cache[a].setdefault(k,v)
        except Exception: pass
        d=cache[a]
        if 'загл' in d and '1' not in d: d['1']=d['загл']
        if '—' in d: d['1']=d['—']
    return cache[a]
def san(t):
    j=re.search(r' - (влеч[её]т|влекут) ',t); return t[j.start():] if j else ''
def plist(x): 
    out=[]
    for y in re.split(r'[, и]+',x):
        y=y.rstrip('.')
        if '–' in y:
            a,b=y.split('–')[:2]; out+=[a,b]
        elif y: out.append(y)
    return out
AMT=re.compile(r'\d[\d  ]*(?:,\d)?(?: (?:до|–|-) \d[\d  ]*)? ?(?:рубл|суток|часов)')
REF=re.compile(r'(?:[Чч]\. ?([\d\.]+(?:(?:[–,]| и ) ?[\d\.]+)*),? )?[Сс]т\. (\d+\.\d+(?:\.\d+)?)((?:, \d+\.\d+(?:\.\d+)?)*)|(?:[Чч]\. ?|[Чч]аст[ьи] )([\d\.]+(?:(?:[–,]| и ) ?[\d\.]+)*)')
args=sys.argv[2:]; files=[]
args=[a for a in args if a!='-v']
for a in args: files+= sorted(glob.glob(a+'/*.txt')) if os.path.isdir(a) else [a]
tot=bad=noref=0
for f in files:
    head=None; carry=None; q=os.path.basename(f)[:-4]
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        if l.startswith('#'):
            m=re.search(r'[Сс]т(?:атья|\.) (\d+\.\d+(?:\.\d+)?)',l)
            if m: head=m.group(1)
            elif l.startswith('## ') or l.startswith('# '): head=None
            carry=None
            continue
        m=re.match(r'- \*\*Норма:?\*\*:? /*[Сс]т\. (\d+\.\d+(?:\.\d+)?)',l)
        if m: head=m.group(1); continue
        if not AMT.search(l):
            lead=re.match(r'[-\d. ]*\*\*(?://)?(?:[Чч]\. ?[\d\., –и]+ )?[Сс]т\. (\d+\.\d+(?:\.\d+)?)',l)
            if lead: carry=lead.group(1)
            continue
        last=None; lastart=head or carry
        lead=re.match(r'[-\d. ]*\*\*(?://)?(?:[Чч]\. ?[\d\., –и]+ )?[Сс]т\. (\d+\.\d+(?:\.\d+)?)',l)
        if lead: carry=lead.group(1); lastart=carry
        for cl in re.split(r'(?<=[;.]) (?=[\*/А-Яа-я«(])',l):
            cl0=cl; refs=[]
            for m in REF.finditer(cl):
                after=cl[m.end():m.end()+40]
                if re.match(r'/* ?(?:Уголовного|УК|Закона|УПК|Конституции|Правил|Федерального|Положения|Инструкции|Наставления|Порядка|Пленума|КАС|ГК|НК|№)',after): continue
                if m.group(2):
                    arts=[m.group(2)]+re.findall(r'\d+\.\d+(?:\.\d+)?',m.group(3) or '')
                    for a in arts: refs.append((a,plist(m.group(1)) if (m.group(1) and a==arts[0]) else None))
                    lastart=arts[-1]
                elif lastart:
                    refs.append((lastart,plist(m.group(4))))
            am=[a.group(0) for a in AMT.finditer(re.sub(r'//[^/]*//','',cl))]
            if refs: last=refs
            if not am: continue
            use=refs or last or ([(head,None)] if head else None)
            if not use:
                noref+=1
                if '-v' in sys.argv: print('без ссылки %s:%d %s'%(q,i,cl0[:200]))
                continue
            st=''
            for a,ps in use:
                d=P(a)
                if not d: continue
                st+=' '.join(san(d.get(p,'')) for p in (ps or [k for k in d if k not in('загл','—')]))+' '
            if not st.strip(): continue
            sn=set(nums(st)); ln=set()
            for a in am: ln|=set(nums(a))
            tot+=1; miss=sorted(ln-sn,key=float)
            if not miss: continue
            bad+=1
            print('%s:%d [%s] нет: %s'%(q,i,'; '.join('%s ст. %s'%(','.join(ps) if ps else '—',a) for a,ps in use)[:70],' '.join(miss)))
            print('    '+cl0[:300])
            print('    => '+conv(st)[:260].replace('наложение административного штрафа','штраф'))
print('отрезков с суммой или сроком: %d, с ненайденным числом: %d, без ссылки на КоАП: %d'%(tot,bad,noref))
