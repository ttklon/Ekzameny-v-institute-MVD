import re,sys,glob
subj=sys.argv[1]; thr=float(sys.argv[2]) if len(sys.argv)>2 else 0.5
STOP=set('это этот эта эти того тому также либо если когда может могут должен должна должны быть есть был были будет который которая которые которых которого которым ними него неё нее них или что как для при над под без про через между после перед только уже ещё еще так там тут где кто чем все всех всем свой своя свои своих своего себя нужно можно нельзя иной иные иных другой другие других случае случаях том тем те то же ли бы не ни но да на по из от до за со ко об во их его ее её'.split())
def stems(s):
    s=s.lower().replace('ё','е')
    return {w[:5] for w in re.findall(r'[а-я]{4,}',s) if w not in STOP}
def clean(l):
    l=re.sub(r'//\([^)]*\)//',' ',l); l=re.sub(r'\([^)]*(?:стать|пункт|част)[^)]*\)',' ',l)
    return l
tot=0; fl=0
for f in sorted(glob.glob('/tmp/out/%s_*.txt'%subj),key=lambda x:int(re.findall(r'_(\d+)\.txt',x)[0])):
    m=re.search(r'/%s_(\d+)\.txt'%subj,f)
    n=int(m.group(1)); L=open(f,encoding='utf-8').read().split('\n')
    seen={}; cur=None; items=[]
    for l in L:
        m=re.match(r'\[(\d+)\] (.*)',l)
        if m: cur=[int(m.group(1)),m.group(2),[],[]]; items.append(cur); continue
        if cur is None: continue
        s=l.strip()
        if s.startswith('·'):
            lab,_,txt=s[1:].partition(':'); lab=lab.replace('↳','').strip(); seen[lab]=seen.get(lab,'')+' '+txt; cur[2].append(seen[lab]); cur[3].append(lab)
        elif s.startswith('↑'):
            lab=s[1:].replace('↳','').strip(); cur[2].append(seen.get(lab,'')); cur[3].append(lab)
    for ln,txt,norms,labs in items:
        if not norms or txt.startswith(('!!','#')): continue
        a=stems(clean(txt)); 
        if len(a)<4: continue
        b=stems(' '.join(norms)); tot+=1
        c=len(a&b)/len(a)
        if c<thr:
            fl+=1; print('%d:%d %.0f%% [%s] %s\n      нет: %s'%(n,ln,c*100,'; '.join(labs)[:60],txt[:330],' '.join(sorted(a-b))[:200]))
print('строк с нормой:',tot,'ниже порога:',fl)
