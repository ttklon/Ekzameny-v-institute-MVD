import tempfile
import re,glob,sys,os,pickle
subj=sys.argv[1]
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..',subj)
S=pickle.load(open(os.path.join(tempfile.gettempdir(),'pass2_norm_%s.pkl'%subj),'rb'))
from quotes_norm import norm
AUTH=eval(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'auth_%s.txt'%subj),encoding='utf-8').read())
for f in sorted(glob.glob(A+'/q[0-9][0-9][0-9].txt')):
    n=int(os.path.basename(f)[1:4]); last=None
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        cur=[c for a,c in AUTH if re.search(a,l)]
        if re.search(r'[Тт]о же пособие|[Тт]ам же|[Вв] том же пособии',l) and not cur: cur=last or []
        if cur: last=cur
        if not cur: continue
        qs=[q for q in re.findall(r'«([^«»]{4,})»',l)]
        for q in qs:
            k=norm(q)
            if not k: continue
            parts=[norm(x) for x in re.split(r'…|\.\.\.',q) if x.strip()]
            if any(all(p in S.get(c,'') for p in parts) for c in cur): continue
            print('%d:%d [%s] «%s»'%(n,i,','.join(cur),q[:120]))
