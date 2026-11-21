import sys
def sub(p, R):
    t=open(p,encoding='utf-8').read()
    for a,b in R:
        assert t.count(a)==1, (t.count(a), a[:60]); t=t.replace(a,b)
    open(p,'w',encoding='utf-8').write(t); print(p, len(t.split()))
