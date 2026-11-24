import re,sys
src,pref,dst=sys.argv[1],sys.argv[2],sys.argv[3]
skip=set()
if len(sys.argv)>4:
    for l in open(sys.argv[4],encoding='utf-8'): skip.add(l.strip())
t=open(src,encoding='utf-8').read(); out=[]; keys=[]
for b in re.split(r'\n(?=%s/q)'%pref,t):
    ls=b.split('\n')
    if not ls[0].startswith(pref): continue
    h=ls[0]; r=re.search(r'\[(.*?) ←\s*(.{0,22})',h)
    o=[l for l in ls if l.startswith('  О')]; n=[l for l in ls if l.startswith('  Н')]
    ot=o[0][5:] if o else ''
    k=re.sub(r'\W+','',ot)[:160]; keys.append(k)
    if k in skip: continue
    out.append(h.split(' {')[0][len(pref)+1:]+' ['+(r.group(1)+'|'+r.group(2) if r else '')+'] '+ot[:290]+'\n   Н: '+(n[0][5:255] if n else ''))
open(dst,'w',encoding='utf-8').write('\n'.join(out)); open(dst+'.keys','w',encoding='utf-8').write('\n'.join(keys)); print(len(out),len('\n'.join(out)))
