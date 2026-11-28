# Запуск: python3 nocite.py tp|gpp ПАПКА_С_ТЕКСТАМИ [порог]
import os as _os, tempfile as _tf
ANS=_os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'..','..'))+'/'
REPO=_os.path.normpath(_os.path.join(ANS,'..','..'))+'/'
TMP=_tf.gettempdir()+'/'
# Третий проход: числа с единицей измерения в строках БЕЗ ссылки //(…)// — есть ли такое же число с той же единицей
# в источниках предмета рядом со словами строки.
import re,glob,sys,os,pickle
subj,src=sys.argv[1],sys.argv[2]
A=ANS+subj
W={'один':1,'одного':1,'одному':1,'одним':1,'одна':1,'одной':1,'одну':1,'одно':1,'два':2,'две':2,'двух':2,'двум':2,'двумя':2,'три':3,'трёх':3,'трех':3,'трём':3,'трем':3,'тремя':3,
'четыре':4,'четырёх':4,'четырех':4,'четырём':4,'пять':5,'пяти':5,'пятью':5,'шесть':6,'шести':6,'семь':7,'семи':7,'восемь':8,'восьми':8,'девять':9,'девяти':9,'десять':10,'десяти':10,
'одиннадцать':11,'одиннадцати':11,'двенадцать':12,'двенадцати':12,'тринадцать':13,'тринадцати':13,'четырнадцать':14,'четырнадцати':14,'пятнадцать':15,'пятнадцати':15,'шестнадцать':16,'шестнадцати':16,
'семнадцать':17,'семнадцати':17,'восемнадцать':18,'восемнадцати':18,'девятнадцать':19,'девятнадцати':19,'двадцать':20,'двадцати':20,'тридцать':30,'тридцати':30,'сорок':40,'сорока':40,
'пятьдесят':50,'пятидесяти':50,'шестьдесят':60,'шестидесяти':60,'семьдесят':70,'семидесяти':70,'восемьдесят':80,'девяносто':90,'сто':100,'ста':100,'полтора':1.5,'полутора':1.5,
'двухнедельный':'2нед','двухнедельного':'2нед','трёхдневный':'3дн','трехдневный':'3дн','пятидневный':'5дн','десятидневный':'10дн','месячный':'1мес','двухмесячный':'2мес','трёхмесячный':'3мес','трехмесячный':'3мес','шестимесячный':'6мес','годичный':'1год','недельный':'1нед','семидневный':'7дн','трёхдневного':'3дн'}
U=[('дн',r'(?:рабочих |календарных |рабочего |календарного )?(?:дн|день|дня|суток|сутк)'),('мес',r'месяц'),('год',r'(?:год|лет\b)'),('нед',r'недел'),('час',r'час'),('руб',r'(?:тысяч\w* )?рубл'),('проц',r'(?:процент|%)'),('мин',r'минут')]
NUM=r'(\d[\d ]*(?:[.,]\d+)?|'+'|'.join(sorted([k for k,v in W.items() if not isinstance(v,str)],key=len,reverse=True))+r')'
def pairs(t):
    t=t.lower().replace('\xa0',' '); res=set()
    for code,u in U:
        for m in re.finditer(r'(?<![\w.])'+NUM+r'(?:[- ](?:и более|до|или|–|—)?[ ]?'+NUM+r')?[ ]?'+u,t):
            for g in (m.group(1),m.group(2)):
                if not g: continue
                g=g.strip(); v=W.get(g)
                if v is None:
                    try: v=float(g.replace(' ','').replace(',','.'))
                    except: continue
                res.add((float(v),code,m.start()))
    for m in re.finditer(r'[а-яё]+',t):
        v=W.get(m.group(0))
        if isinstance(v,str): res.add((float(re.match(r'\d+',v).group(0)),v[len(re.match(r'\d+',v).group(0)):],m.start()))
    return res
def stems(t): return {w[:6] for w in re.findall(r'[а-яё]{5,}',t.lower())}
cache=TMP+'pass3_nocite_%s.pkl'%subj
if os.path.exists(cache): S=pickle.load(open(cache,'rb'))
else:
    S={}
    for f in sorted(glob.glob(src+'/*.txt')):
        t=re.sub(r'\s+',' ',open(f,encoding='utf-8').read().replace('\xad','')).lower()
        for v,c,p in pairs(t): S.setdefault((v,c),[]).append((os.path.basename(f)[:6],stems(t[max(0,p-350):p+350])))
    pickle.dump(S,open(cache,'wb'))
tot=fl=0
for f in sorted(glob.glob(A+'/q*.txt')):
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        if '//(' in l or l.startswith(('#','!!')): continue
        ps={(v,c) for v,c,p in pairs(l)}
        if not ps: continue
        st=stems(l)
        for v,c in sorted(ps):
            if (c=='год' and v>=1900) or re.search(r'стать\w+ %g\b'%v,l): continue
            tot+=1; best=0; bid=''
            for fid,ss in S.get((v,c),[]):
                k=len(st&ss)
                if k>best: best,bid=k,fid
            sc=best/max(1,len(st))
            if sc<float(sys.argv[3] if len(sys.argv)>3 else 0.5):
                fl+=1; print('%s:%d [%g %s] %.2f %s | %s'%(os.path.basename(f)[:4],i,v,c,sc,bid,l[:230]))
print('пар число+единица в строках без ссылки:',tot,'ниже порога:',fl)
