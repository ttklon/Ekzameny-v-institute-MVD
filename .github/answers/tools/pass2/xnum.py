import re,glob,collections,sys
W={'один':1,'одна':1,'одного':1,'одной':1,'одну':1,'два':2,'две':2,'двух':2,'три':3,'трёх':3,'трех':3,'четыре':4,'четырёх':4,'пять':5,'пяти':5,'шесть':6,'шести':6,'семь':7,'семи':7,'восемь':8,'восьми':8,'девять':9,'девяти':9,'десять':10,'десяти':10,'двенадцать':12,'двенадцати':12,'четырнадцать':14,'четырнадцати':14,'пятнадцать':15,'пятнадцати':15,'шестнадцати':16,'восемнадцати':18,'двадцать':20,'двадцати':20,'тридцать':30,'тридцати':30,'сорок':40,'сорока':40,'пятьдесят':50,'пятидесяти':50,'полутора':1.5}
ADJ={'двухнедельн':(2,'недел'),'трёхдневн':(3,'дн'),'трехдневн':(3,'дн'),'десятидневн':(10,'дн'),'месячн':(1,'месяц'),'двухмесячн':(2,'месяц'),'трёхмесячн':(3,'месяц'),'недельн':(1,'недел'),'годичн':(1,'год'),'пятидневн':(5,'дн'),'семидневн':(7,'дн'),'шестимесячн':(6,'месяц')}
U=r'(рабоч\w+ |календарн\w+ )?(дн\w+|день|дня|суток|сутки|недел\w+|месяц\w*|год\w*|лет|час\w*|процент\w*|раз\w*|оклад\w*)'
D=collections.defaultdict(lambda: collections.defaultdict(set))
for f in sorted(glob.glob('q0*.txt')):
    n=int(f[1:4])
    for l in open(f,encoding='utf-8').read().split('\n'):
        if l.startswith('!!'): continue
        cs=re.findall(r'//\(([^)]*)\)//',l)
        arts=set()
        for c in cs:
            if re.search(r'закон|Конституц|постановлен|Положени|Правил|приказ|Указ|кодекса об|процессуальн|Граждан|того же',c,re.I): continue
            for a in re.findall(r'стать[яиюей]+ ([\d., –и]+)',c):
                for x in re.findall(r'\d+(?:\.\d+)?',a): arts.add(x)
        m=re.match(r'Статья (\d+(?:\.\d+)?)\.',l)
        if not arts: continue
        t=re.sub(r'//\([^)]*\)//','',l).lower()
        vals=set()
        for m in re.finditer(r'(\d+(?:[.,]\d+)?|[а-яё]+) '+U,t):
            v=m.group(1); 
            if not v[0].isdigit():
                if v not in W: continue
                v=str(W[v])
            u=(m.group(2) or '')[:3]+m.group(3)[:3]
            vals.add(v+' '+u)
        for k,(v,u) in ADJ.items():
            if re.search(r'\b'+k,t): vals.add('%s %s'%(v,u[:3]))
        for a in arts:
            for v in vals: D[a][v].add(n)
for a in sorted(D,key=lambda x: float(x) if x.count('.')<2 else 0):
    if sum(len(s) for s in D[a].values())<2: continue
    print('ст.%s: '%a+'; '.join('%s←%s'%(v,','.join(map(str,sorted(s)))) for v,s in sorted(D[a].items())))
