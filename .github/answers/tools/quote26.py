import re,glob,sys,os
def norm(s):
    s=s.lower().replace('ё','е')
    s=re.sub(r'[-\u00ad]\s*\n\s*','',s)
    s=re.sub(r'\(\s*(в редакции|дополнение|часть в редакции|пункт в редакции|абзац)[^()]*\)','',s)
    s=re.sub(r'стр\. \d+ из \d+','',s)
    s=re.sub(r'[^a-zа-я0-9]+','',s)
    return s
srcdir=sys.argv[1]; ansglob=sys.argv[2]
big=[]
for f in glob.glob(srcdir+'/*.txt'):
    try: big.append(norm(open(f,encoding='utf-8',errors='ignore').read()))
    except: pass
BIG='\n'.join(big)
miss=0;tot=0
for f in sorted(glob.glob(ansglob)):
    for i,l in enumerate(open(f,encoding='utf-8'),1):
        for q in re.findall(r'«([^«»]{25,})»',l):
            if len(q.split())<5: continue
            # split on ellipsis
            for part in re.split(r'…|\.\.\.',q):
                if len(part.split())<5: continue
                tot+=1
                n=norm(part)
                if n not in BIG:
                    # try halves to localise
                    w=part.split(); h=len(w)//2
                    a=norm(' '.join(w[:h])) in BIG; b=norm(' '.join(w[h:])) in BIG
                    miss+=1
                    print('%s:%d [%s%s] «%s»'%(os.path.basename(f)[:-4],i,'+' if a else '-','+' if b else '-',part[:230]))
print('цитат',tot,'не найдено',miss)
