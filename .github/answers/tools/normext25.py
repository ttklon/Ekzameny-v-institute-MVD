import sys,re,json
sys.path.insert(0,'tools')
import norm25 as N
ABB=('утв','им','т','г','др','см','ст','п','ч','подп','абз','гл','разд','напр','руб','тыс')
def sents(line):
    out=[];start=0
    for m in re.finditer(r'[.!?…][»)]*\s+(?=[«*(]*[А-ЯЁ])', line):
        pre=line[:m.start()]
        if pre.count('//')%2==1: continue
        if pre.count('«')>pre.count('»') and not line[m.start():m.end()].strip().endswith('»'): continue
        w=re.findall(r'[А-Яа-яёЁ]+$',pre)
        if w and w[0] in ABB: continue
        out.append(line[start:m.end()].strip()); start=m.end()
    out.append(line[start:].strip())
    return [s for s in out if s]
def items():
    res=[]
    for n in range(1,150):
        l=N.lost(n)
        if not l: continue
        o=N.old(n).split('\n'); c=N.cur(n)
        ch={N.hk(x) for x in c.split('\n') if x.startswith('## ')}
        sec='';seen=set()
        for i,line in enumerate(o):
            if line.startswith('## '): sec=line
            if line.startswith('!! '): continue
            hit=[a for a in l if N.has(a,line) and a not in seen]
            if not hit: continue
            seen|=set(hit)
            m=re.match(r'(\s*(?:[-–]|\d+\.)\s+)',line); pre=m.group(1) if m else ''
            ss=sents(line[len(pre):])
            ex=[s for s in ss if any(N.has(a,s) for a in hit)]
            surv = line[:45] in c
            res.append(dict(q=n,i=i+1,sec=sec,secok=N.hk(sec) in ch,hit=hit,pre=pre,ex=' '.join(ex),surv=surv,full=len(ss)==len(ex),lw=len(line.split())))
    return res
if __name__=='__main__':
    R=items(); tw=0
    a,b=int(sys.argv[1]),int(sys.argv[2])
    for k,r in enumerate(R):
        tw+=len(r['ex'].split())
        if a<=r['q']<=b:
            print('#%d q%03d:%d %s | %s | %s | %s | %d/%d сл.'%(k,r['q'],r['i'],'' if r['secok'] else 'РАЗДЕЛ УДАЛЁН',r['sec'][:55],'строка есть' if r['surv'] else 'строки нет','вся' if r['full'] else 'часть',len(r['ex'].split()),r['lw']))
            print('   '+repr(r['pre'])+' '+r['ex'][:int(sys.argv[3]) if len(sys.argv)>3 else 700])
    print('всего',len(R),'слов в выдержках',tw)
