# Запуск: python docxchk.py   (нужен python-docx)
import os as _os, tempfile as _tf
ANS=_os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'..','..'))+'/'
REPO=_os.path.normpath(_os.path.join(ANS,'..','..'))+'/'
TMP=_tf.gettempdir()+'/'
# Третий проход: каждый ли абзац ответа (.txt) стоит в собранном docx
import re,glob,sys,os
from docx import Document
R=REPO
D={'tp':'Трудовое право','gpp':'Гражданско-процессуальное право'}
def norm(s): return re.sub(r'[^0-9A-Za-zА-Яа-яЁё]','',s).lower()
for s,name in D.items():
    files=sorted(glob.glob(R+name+'/3. Ответы на вопросы/Вариант 1*/*.docx'))
    txt={}
    for f in files:
        d=Document(f); parts=[p.text for p in d.paragraphs]
        for tb in d.tables:
            for row in tb.rows:
                for c in row.cells: parts.append(c.text)
        txt[f]=norm(' '.join(parts))
    tot=miss=0
    for q in sorted(glob.glob(R+'.github/answers/%s/q*.txt'%s)):
        n=int(os.path.basename(q)[1:4])
        f=[x for x in files if (lambda m:int(m.group(1))<=n<=int(m.group(2)))(re.search(r'(\d{3})–(\d{3})\.docx$',x))]
        if len(f)!=1: print('нет файла для',s,n,len(f)); continue
        for i,l in enumerate(open(q,encoding='utf-8').read().split('\n'),1):
            k=norm(re.sub(r'^(#+|>|!!|-|\d+\.)\s*','',l))
            if len(k)<8: continue
            tot+=1
            if k not in txt[f[0]]:
                miss+=1; print('%s q%03d:%d нет в docx | %s'%(s,n,i,l[:120]))
    print(s,'файлов',len(files),'строк',tot,'нет в docx',miss)
