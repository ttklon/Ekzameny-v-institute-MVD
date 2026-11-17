#!/tmp/venv/bin/python
# добавляет сокращения к строкам cuts.txt: ввод «N: spec» построчно из stdin
import sys,re
p='/tmp/w/cuts.txt'; L=open(p,encoding='utf-8').read().split('\n')
ns=[]
for row in sys.stdin:
    row=row.strip()
    if not row: continue
    n,ex=row.split(':',1); n=n.strip(); ex=ex.strip()
    idx=[i for i,l in enumerate(L) if l.startswith(n+':')]
    assert len(idx)==1,(n,idx)
    i=idx[0]; head,sep,tail=L[i].partition(' | ')
    spec=head.split(':',1)[1].strip()
    L[i]=n+': '+(spec+','+ex if spec else ex)+(sep+tail if sep else '')
    ns.append(n)
open(p,'w',encoding='utf-8').write('\n'.join(L))
print(' '.join(ns))
