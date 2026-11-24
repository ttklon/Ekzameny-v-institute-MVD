import re,sys
t=open(sys.argv[1],encoding='utf-8').read().split('\n\n'); pat=sys.argv[2]; a=int(sys.argv[3]); b=int(sys.argv[4]); W=int(sys.argv[5]) if len(sys.argv)>5 else 230
n=0
for blk in t:
    ls=blk.split('\n')
    if not re.match(r'^\w+/q\d+:',ls[0]) or not re.search(pat,ls[0]): continue
    n+=1
    if not (a<=n-1<b): continue
    hd=ls[0].split('  [')[0]; hd=re.sub(r'^\w+/','',hd); hd=re.sub(r' ← (\w{6})[^;|]*',r'←\1',hd)[:70]
    ref=re.search(r'\[(.*)\]',ls[0]); ref=re.sub(r' ← (\w{6}) [^;]*',r'←\1',ref.group(1))[:70] if ref else ''
    print(hd,'|',ref,'|',ls[1].strip()[:W] if len(ls)>1 else '')
print(n)
