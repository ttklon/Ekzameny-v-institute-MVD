import re,glob,sys,os
subj,src=sys.argv[1],sys.argv[2]; thr=float(sys.argv[3]) if len(sys.argv)>3 else 0.6
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..',subj)
AUTH=eval(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'auth_%s.txt'%subj),encoding='utf-8').read())
STOP=set('это этот эта эти того тому также либо если когда может могут должен должна должны быть есть был были будет который которая которые которых которого которым ними него неё нее них или что как для при над под без про через между после перед только уже ещё еще так там тут где кто чем все всех всем свой своя свои своих своего себя нужно можно нельзя иной иные иных другой другие других пособие пособии пособия пособию соавторов называет приводит пишет указывает отмечает кодекс кодекса кодексе статья статьи статье часть части пункт пункта действующей действующем редакции сейчас тексте прежней'.split())
def st(s):
    s=s.lower().replace('ё','е'); return [w[:5] for w in re.findall(r'[а-я]{4,}',s) if w not in STOP]
SRC={}
def load(c):
    if c not in SRC:
        t=open(glob.glob(src+'/%s*'%c)[0],encoding='utf-8').read().replace('\xad',''); t=re.sub(r'(\w)-\s*\n\s*(\w)',r'\1\2',t)
        pg=[(m.start(),m.group(1)) for m in re.finditer(r'@@ (\d+) \|',t)]
        w=[(m.start(),m.group().lower().replace('ё','е')[:5]) for m in re.finditer(r'[А-Яа-яЁё]{4,}',t)]
        SRC[c]=(t,pg,w)
    return SRC[c]
def best(c,a):
    t,pg,w=load(c); W=90; bs=0; bp=0
    A_=set(a)
    hits=[i for i,(p,x) in enumerate(w) if x in A_]
    j=0
    import bisect
    for k,i in enumerate(hits):
        # window starting at i
        e=bisect.bisect_right(hits,i+W)
        s=len({w[h][1] for h in hits[k:e]})
        if s>bs: bs=s; bp=w[i][0]
    page='?'
    for p,n in pg:
        if p<=bp: page=n
        else: break
    return bs/len(A_),page,re.sub(r'\s+',' ',t[bp:bp+420])
tot=0; fl=0
for f in sorted(glob.glob(A+'/q[0-9][0-9][0-9].txt')):
    n=int(os.path.basename(f)[1:4])
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        if l.startswith(('!!','#')): continue
        cur=[c for a,c in AUTH if re.search(a,l)]
        if not cur: continue
        body=re.sub(r'//\([^)]*\)//',' ',l)
        body=re.sub(r'\((?:пособи|учебн|стать)[^)]*\)',' ',body)
        for a,c in AUTH: body=re.sub(a+r'\w*',' ',body)
        body=re.sub(r'Федоренко|\(\d{4}\)|\d{4}',' ',body)
        a=st(body)
        if len(set(a))<5: continue
        tot+=1
        r=max((best(c,a) for c in cur),key=lambda x:x[0])
        if r[0]<thr:
            fl+=1; print('%d:%d %.0f%% [%s с.%s]\n   О: %s\n   И: %s'%(n,i,r[0]*100,','.join(cur),r[1],l[:420],r[2][:380]))
print('строк с названным пособием:',tot,'ниже порога:',fl)
