import sys,re
sys.path.insert(0,'tools')
import norm25 as N, normext25 as X
R=X.items()
SKIP=set(int(x) for x in sys.argv[1].split(',')) if len(sys.argv)>1 and sys.argv[1] else set()
byq={}
for k,r in enumerate(R):
    r['k']=k
    if r['secok'] and r['q'] not in (46,) and k not in SKIP: byq.setdefault(r['q'],[]).append(r)
tw=0
for q,rs in byq.items():
    p='adp2/q%03d.txt'%q; c=open(p,encoding='utf-8').read().split('\n'); o=N.old(q).split('\n')
    for r in rs:
        oi=r['i']-1; line=o[oi]
        if r['surv']:
            j=next(i for i,l in enumerate(c) if l.startswith(line[:45]))
            cur=c[j].rstrip()
            if cur[-1] in ';:': print('!! #%d q%03d строка кончается на %r'%(r['k'],q,cur[-1])); cur=cur[:-1]+'.'
            c[j]=cur+' '+r['ex']; tw+=len(r['ex'].split()); print('#%d q%03d:%d append'%(r['k'],q,j+1))
        else:
            # предыдущая сохранившаяся строка того же раздела
            j=None;k=oi-1
            while k>=0:
                l=o[k]
                if l.strip() and not l.startswith('## '):
                    jj=next((i for i,x in enumerate(c) if x.startswith(l[:45])),None)
                    if jj is not None: j=jj;break
                if l.startswith('## '):
                    h=N.hk(l); j=next(i for i,x in enumerate(c) if x.startswith('## ') and N.hk(x)==h); break
                k-=1
            new=r['pre']+r['ex']
            anchor=c[j]
            isb=lambda s: bool(re.match(r'\s*(-|\d+\.)\s',s))
            # пропустить вставленные ранее строки сразу после якоря
            ins=j+1
            if isb(new) and isb(anchor): c[ins:ins]=[new]
            elif isb(new):
                c[ins:ins]=['',new] if (ins<len(c) and c[ins].strip()=='' ) else ['',new,'']
                # нормализуем ниже
            else: c[ins:ins]=['',new]
            if anchor.rstrip().endswith(':'): print('!! #%d q%03d якорь кончается на «:»'%(r['k'],q))
            tw+=len(new.split()); print('#%d q%03d:%d insert after: %s'%(r['k'],q,j+1,anchor[:70]))
    t='\n'.join(c)
    # пустая строка между абзацем и списком, без тройных
    t=re.sub(r'\n{3,}','\n\n',t)
    open(p,'w',encoding='utf-8').write(t)
print('слов добавлено',tw)
