# Третий проход. Отметки «О несоответствии Конституции…» в тексте кодекса и строки ответов, которые ссылаются на ту же статью.
# Запуск: python3 ks.py tp|gpp ПАПКА_С_ТЕКСТАМИ ИД_КОДЕКСА [номера статей…]
# Печатает норму с отметкой, строки «цит.» (ссылка на статью) и «НАЗВАНО» (постановление названо в ответе).
import os as _os, tempfile as _tf
ANS=_os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'..','..'))+'/'
REPO=_os.path.normpath(_os.path.join(ANS,'..','..'))+'/'
TMP=_tf.gettempdir()+'/'
import re,glob,sys,os
subj,d,cid=sys.argv[1],sys.argv[2],sys.argv[3]; only=sys.argv[4:] 
A=ANS+subj
t=open(glob.glob(d+'/%s*'%cid)[0],encoding='utf-8').read().replace('\xad','')
t=re.sub(r'@@ \d+ \|[^\n]*','',t); t=re.sub(r'Стр\. \d+ из \d+','',t); t=re.sub(r'\s+',' ',t)
arts=[(m.start(),m.group(1)) for m in re.finditer(r'Статья (\d+)\. [А-Я]',t)]
MON='января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split()
for m in re.finditer(r'\((О несоответствии Конституции[^)]*?Конституционного Суда Российской Федерации от (\d\d)\.(\d\d)\.(\d{4}) № ?(\d+-П))\s*\)',t):
    a=[x for p,x in arts if p<m.start()][-1]
    if only and a not in only: continue
    dd,mm,yy,num=m.group(2),m.group(3),m.group(4),m.group(5)
    print('\n#### ст.%s — %s.%s.%s № %s'%(a,dd,mm,yy,num)); print('   НОРМА: …'+t[max(0,m.start()-520):m.end()])
    pats=[r'%s\.%s\.%s № ?%s'%(dd,mm,yy,num), r'%d %s %s года № ?%s'%(int(dd),MON[int(mm)-1],yy,num)]
    for f in sorted(glob.glob(A+'/q*.txt')):
        for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
            if any(re.search(p,l) for p in pats): print('   НАЗВАНО %s:%d %s'%(os.path.basename(f)[:4],i,l[:260]))
            elif re.search(r'стать\w+ (\d+[–, и]+)*%s(?![\d.])'%a,l): print('   цит. %s:%d %s'%(os.path.basename(f)[:4],i,l[:260]))
