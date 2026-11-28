import re,sys,subprocess,difflib
def comp(l):
    def f(m):
        w=m.group(1).split()
        return '«'+(' '.join(w[:4])+' … '+' '.join(w[-2:]) if len(w)>9 else m.group(1))+'»'
    l=re.sub(r'«([^«»]*)»',f,l)
    l=re.sub(r'Федеральн\w+ закон\w* от \d\d\.\d\d\.\d{4} ','ФЗ ',l)
    for a,b in (('Российской Федерации','РФ'),('об административных правонарушениях','об АП'),('административн','адм.'),('общественного порядка','ОП'),('общественной безопасности','ОБ'),('сотрудник','сотр.'),('полиции','пол.'),('органов внутренних дел','ОВД'),('территориальн','терр.'),('правонарушени','ПН')): l=l.replace(a,b)
    return l
def short(s,h=15,t=4):
    w=s.split()
    return s if len(w)<=h+t+3 else ' '.join(w[:h])+' ⋯ '+' '.join(w[-t:])
tot=0
for a in sys.argv[1:]:
    q=int(a); C=[l for l in open('adp2/q%03d.txt'%q,encoding='utf-8').read().split('\n') if l.strip()]
    O=[l for l in subprocess.run(['git','show','30db505:.github/answers/adp2/q%03d.txt'%q],capture_output=True,text=True).stdout.split('\n') if l.strip()]
    sm=difflib.SequenceMatcher(None,O,C,autojunk=False)
    same=[False]*len(C); gap=[0]*(len(C)+1)
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal':
            for j in range(j1,j2): same[j]=True
        elif tag in('delete','replace'):
            gap[j1]+= (i2-i1) - (j2-j1 if tag=='replace' else 0)
    out=[]
    for j,l in enumerate(C):
        g=gap[j]
        isb=l.startswith(('- ','  - ')) or re.match(r'\d+\. ',l)
        if l.startswith('# '): out.append('\n=== '+comp(l)); continue
        s=comp(l)
        if l.startswith('!! '): s=short(s,6,0)
        elif same[j] and isb: s=short(s,6,2)
        elif same[j] and not l.startswith("## "): s=short(s,7,2)
        mark=('[-%d]'%g if g>0 else '')+('' if same[j] else '*')
        if same[j] and isb and g<=0:
            x=' '.join(re.sub(r'^\s*(- |\d+\. )','',comp(l)).split()[:4])
            if out and out[-1].startswith('• '): out[-1]+=' | '+x
            else: out.append('• '+x)
            continue
        out.append(mark+s)
    if gap[len(C)]>0: out.append('[-%d в конце]'%gap[len(C)])
    t='\n'.join(out); tot+=len(t); print(t)
print('\n[chars %d]'%tot)
