import tempfile
import re,glob,sys,os,pickle
subj=sys.argv[1]; src=sys.argv[2]
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..',subj)
def norm(s):
    s=s.lower().replace('ё','е')
    s=re.sub(r'@@ \d+ \|',' ',s)
    s=re.sub(r'(?<=[а-яa-z])[-­]\s+(?=[а-яa-z])','',s)
    s=re.sub(r'[^0-9a-zа-я]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()
pk=os.path.join(tempfile.gettempdir(),'pass2_norm_%s.pkl'%subj)
if os.path.exists(pk): S=pickle.load(open(pk,'rb'))
else:
    S={}
    for f in glob.glob(src+'/*'):
        if f.endswith('.tsv'): continue
        try: S[os.path.basename(f)[:6]]=norm(open(f,encoding='utf-8',errors='ignore').read())
        except Exception as e: pass
    pickle.dump(S,open(pk,'wb'))
big=' \n '.join(S.values())
tot=miss=0
for f in sorted(glob.glob(A+'/q[0-9][0-9][0-9].txt')):
    n=int(os.path.basename(f)[1:4])
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        for q in re.findall(r'«([^«»]{12,})»',l):
            if len(q.split())<3: continue
            tot+=1
            k=norm(q)
            if k in big: continue
            # try pieces split by ellipsis
            parts=[norm(x) for x in re.split(r'…|\.\.\.',q) if len(x.split())>=2]
            if parts and all(p in big for p in parts): continue
            miss+=1; print('%d:%d «%s» || %s'%(n,i,q,l[:90]))
print('цитат',tot,'не найдено',miss)
