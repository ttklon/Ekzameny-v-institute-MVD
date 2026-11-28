# a.py ФАЙЛ(koap|pol|upk|gpk|tk|uk или путь) "Статья N." [ЗНАКОВ] [ПОДСТРОКА]
import sys,re,os
f=sys.argv[1]; f=f if os.path.exists(f) else '/tmp/%s.txt'%f
t=open(f,encoding='utf-8').read(); head=sys.argv[2]; n=int(sys.argv[3]) if len(sys.argv)>3 else 1200; sub=sys.argv[4] if len(sys.argv)>4 else ''
ms=[m.start() for m in re.finditer(re.escape(head),t)]
if not ms: print('НЕТ',head); sys.exit()
s=t[ms[-1]:ms[-1]+60000]
if sub:
    a=s.find(sub); s=s[a:] if a>=0 else 'НЕТ ПОДСТРОКИ '+sub+' | '+s
print(s[:n])
