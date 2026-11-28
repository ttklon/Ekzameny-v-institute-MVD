# Третий проход. Ссылки ответов на статьи основного акта: есть ли статья в тексте и не утратила ли она силу.
# Запуск: python3 lost.py tp|gpp ПАПКА_С_ТЕКСТАМИ ИД_КОДЕКСА
# «НЕТ В ТЕКСТЕ» чаще всего значит, что заголовок статьи не разобран; такую строку смотрят в тексте кодекса.
import os as _os, tempfile as _tf
ANS=_os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'..','..'))+'/'
REPO=_os.path.normpath(_os.path.join(ANS,'..','..'))+'/'
TMP=_tf.gettempdir()+'/'
import re,glob,sys,os
subj,d,cid=sys.argv[1],sys.argv[2],sys.argv[3]
A=ANS+subj
t=open(glob.glob(d+'/%s*'%cid)[0],encoding='utf-8').read().replace('\xad','')
t=re.sub(r'@@ \d+ \|[^\n]*','',t); t=re.sub(r'Стр\. \d+ из \d+','',t); t=re.sub(r'\s+',' ',t)
lost=set(); exist=set()
for m in re.finditer(r'Статья (\d+(?: \d+)?)\s*\.?\s*(.{0,80})',t):
    n=m.group(1).replace(' ','.')
    if re.match(r'\(?\s*(Утратила силу|Статья утратила силу)',m.group(2)) or 'тратила силу' in m.group(2)[:40]: lost.add(n)
    elif re.match(r'[А-Я]',m.group(2)): exist.add(n)
# статьи вида 3797 = 379.7 в тексте без точки
print('утратили силу:',len(lost),'есть:',len(exist))
OTHER=r'(закон|кодекс|ГК|КоАП|Конституци|конвенци|устав|положени|правил|постановлен|приказ|Основ|указ|342-ФЗ|этого|этой|того же)'
tot=fl=0
for f in sorted(glob.glob(A+'/q*.txt')):
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        for c in re.findall(r'//\((.*?)\)//',l):
            if re.search(OTHER,c,re.I): continue
            for m in re.finditer(r'стать\w+ ([\d., –и]+)',c):
                nums=re.findall(r'\d+(?:\.\d+)?',m.group(1))
                rng=re.search(r'(\d+)–(\d+)',m.group(1))
                for n in nums:
                    tot+=1
                    k=n; alt=n.replace('.','')
                    if n in lost or (alt in lost and n not in exist):
                        fl+=1; print('УТРАТИЛА %s:%d ст.%s | %s'%(os.path.basename(f)[:4],i,n,l[:200]))
                    elif n not in exist and alt not in exist:
                        fl+=1; print('НЕТ В ТЕКСТЕ %s:%d ст.%s | %s'%(os.path.basename(f)[:4],i,n,l[:200]))
print('ссылок на статьи основного акта:',tot,'вопросов:',fl)
