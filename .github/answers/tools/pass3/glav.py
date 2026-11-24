# Запуск: python3 glav.py
import os as _os, tempfile as _tf
ANS=_os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'..','..'))+'/'
REPO=_os.path.normpath(_os.path.join(ANS,'..','..'))+'/'
TMP=_tf.gettempdir()+'/'
# Третий проход: номера статей и пунктов в строке «Главное для запоминания» — есть ли они в тексте ответа выше
import re,glob,sys,os
A=ANS
def nums(s):
    r=set()
    for m in re.finditer(r'(стать\w+|пункт\w*|част\w+)\s+((?:\d+(?:\.\d+)?)(?:\s*(?:,|и|–|—|-)\s*\d+(?:\.\d+)?)*)',s):
        k=m.group(1)[:4].lower(); body=m.group(2)
        xs=re.findall(r'\d+(?:\.\d+)?',body)
        rg=re.findall(r'(\d+)\s*[–—-]\s*(\d+)',body)
        for x in xs: r.add((k,x))
        for a,b in rg:
            if 0<int(b)-int(a)<40:
                for i in range(int(a),int(b)+1): r.add((k,str(i)))
    return r
for s in ('tp','gpp'):
    tot=fl=0
    for f in sorted(glob.glob(A+s+'/q*.txt')):
        L=open(f,encoding='utf-8').read().rstrip('\n').split('\n')
        g=L[-1]; body='\n'.join(L[:-1])
        if not g.startswith('!!'): print('нет Главного',f); continue
        bn=nums(body); 
        for k,x in sorted(nums(g)):
            if k!='стат': continue
            tot+=1
            if (k,x) not in bn and not re.search(r'(?<![\d.])%s(?![\d.])'%re.escape(x),body):
                fl+=1; print('%s %s ст.%s нет выше | %s'%(s,os.path.basename(f)[:4],x,g[:160]))
    print(s,'номеров статей в «Главном»:',tot,'нет в тексте:',fl)
