import re,sys,glob,os
subj=sys.argv[1]
W={'один':1,'одна':1,'одного':1,'одной':1,'одну':1,'одном':1,'два':2,'две':2,'двух':2,'двум':2,'три':3,'трёх':3,'трех':3,'трем':3,'четыре':4,'четырёх':4,'четырех':4,'пять':5,'пяти':5,'шесть':6,'шести':6,'семь':7,'семи':7,'восемь':8,'восьми':8,'девять':9,'девяти':9,'десять':10,'десяти':10,'одиннадцать':11,'одиннадцати':11,'двенадцать':12,'двенадцати':12,'четырнадцать':14,'четырнадцати':14,'пятнадцать':15,'пятнадцати':15,'шестнадцать':16,'шестнадцати':16,'восемнадцать':18,'восемнадцати':18,'двадцать':20,'двадцати':20,'тридцать':30,'тридцати':30,'сорок':40,'сорока':40,'пятьдесят':50,'пятидесяти':50,'шестьдесят':60,'шестидесяти':60,'сто':100,'ста':100,'полтора':1.5,'полутора':1.5,'полуторн':1.5,'двойн':2,'двукратн':2,'трёхкратн':3,'трехкратн':3,'дважды':2,'трижды':3,'вдвое':2,'втрое':3,'пятикратн':5,'десятикратн':10}
PRE={'одно':1,'двух':2,'трёх':3,'трех':3,'четырёх':4,'четырех':4,'пяти':5,'шести':6,'семи':7,'восьми':8,'девяти':9,'десяти':10,'двенадцати':12,'четырнадцати':14,'пятнадцати':15,'двадцати':20,'тридцати':30,'сорока':40}
ROOT=('дневн','месячн','недельн','летн','часов','годичн','кратн','суточн')
SOLO={'месячн':1,'недельн':1,'годичн':1,'суточн':1,'ежемесячн':None}
def nums(s):
    s=s.lower().replace('ё','е')
    out=set()
    for x in re.findall(r'\d+(?:[.,]\d+)?',s):
        out.add(float(x.replace(',','.')))
    for w in re.findall(r'[а-я]+',s):
        if w in W: out.add(float(W[w])); continue
        hit=False
        for p,v in PRE.items():
            pp=p.replace('ё','е')
            if w.startswith(pp) and w[len(pp):].startswith(ROOT): out.add(float(v)); hit=True; break
        if hit: continue
        for k,v in W.items():
            if len(k)>5 and w.startswith(k.replace('ё','е')) and k.endswith(('н',)): out.add(float(v))
        for r,v in SOLO.items():
            if v and w.startswith(r): out.add(float(v))
    return out
def clean(l):
    l=re.sub(r'//\([^)]*\)//',' ',l)
    l=re.sub(r'\((?:стать|част|пункт|подпункт|абзац)[^)]*\)',' ',l)
    l=re.sub(r'№ ?[\w.\-/]+',' ',l)
    l=re.sub(r'\d{1,2} [а-я]+ \d{4} года',' ',l)
    l=re.sub(r'\d{2}\.\d{2}\.\d{4}',' ',l)
    l=re.sub(r'\(\d{4}\)|, \d{4}\)|\b(?:19|20)\d\d\b',' ',l)
    l=re.sub(r'(?:стать\w+|пункт\w*|подпункт\w*|част\w+|глав\w+|раздел\w*|абзац\w*|с\.|вопрос\w*|ответ\w*|строк\w+) (?:«?[\dа-я.]{1,6}»?(?:, | и |–| — )?)+',' ',l)
    l=re.sub(r'\*\*\d+[.)]\*\*|^\s*-?\s*\d+[.)]',' ',l)
    return l
for f in sorted(glob.glob('/tmp/out/%s_*.txt'%subj),key=lambda x:int(re.findall(r'_(\d+)\.txt',x)[0])):
    n=int(re.findall(r'_(\d+)\.txt',f)[0]); L=open(f,encoding='utf-8').read().split('\n')
    seen={}; cur=None; items=[]
    for l in L:
        m=re.match(r'\[(\d+)\] (.*)',l)
        if m: cur=[int(m.group(1)),m.group(2),[],False]; items.append(cur); continue
        if cur is None: continue
        s=l.strip()
        if s.startswith('·'):
            lab,_,txt=s[1:].partition(':'); lab=lab.replace('↳','').strip(); seen[lab]=seen.get(lab,'')+' '+txt; cur[2].append(seen[lab]); cur[3]=True
        elif s.startswith('↑'):
            lab=s[1:].replace('↳','').strip(); cur[2].append(seen.get(lab,'')); cur[3]=True
    for ln,txt,norms,has in items:
        if not has or txt.startswith('!!') or txt.startswith('#'): continue
        a=nums(clean(txt)); b=nums(' '.join(norms))
        d=sorted(x for x in a-b)
        if d: print('%d:%d %s | %s'%(n,ln,[int(x) if x==int(x) else x for x in d],txt[:170]))
