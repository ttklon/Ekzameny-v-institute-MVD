import os
import re,sys,glob,collections
subj,src=sys.argv[1],sys.argv[2]
MON={m:i+1 for i,m in enumerate('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split())}
def pairs(t):
    out=[]
    for m in re.finditer(r'(\d{1,2})[  ]([а-я]+)[  ](\d{4})[  ]?(?:г\.|года)?[^№\n]{0,160}?№[  ]?([\dА-Яа-я][\w\-/.]*)',t):
        if m.group(2) in MON: out.append(('%02d.%02d.%s'%(int(m.group(1)),MON[m.group(2)],m.group(3)),m.group(4).rstrip('.,;)'),m.start()))
    for m in re.finditer(r'(\d{2}\.\d{2}\.\d{4})[^№\n]{0,160}?№[  ]?([\dА-Яа-я][\w\-/.]*)',t):
        out.append((m.group(1),m.group(2).rstrip('.,;)'),m.start()))
    return out
S=collections.defaultdict(set)
for f in glob.glob(src+'/*'):
    t=re.sub(r'\s+',' ',open(f,encoding='utf-8',errors='ignore').read())
    for d,n,_ in pairs(t): S[n.lower()].add(d)
    for d,n,_ in pairs(f): S[n.lower()].add(d)
seen=set(); bad=0; tot=0
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..',subj,'q0*.txt'))):
    t=open(f,encoding='utf-8').read()
    for d,n,pos in pairs(t):
        tot+=1
        ds=S.get(n.lower(),set())
        if d not in ds:
            bad+=1; ln=t[:pos].count('\n')+1
            print(f[-8:-4],ln,d,'№',n,'| в источниках:',sorted(ds)[:4],'|',t[pos:pos+110].replace('\n',' '))
print('пар дата+номер:',tot,'не подтверждено:',bad)
