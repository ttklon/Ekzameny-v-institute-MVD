#!/usr/bin/env python3
"""dates26.py ПАПКА_ОТВЕТОВ ПАПКА_ТЕКСТОВ… — каждая пара «от ДД.ММ.ГГГГ № N» из ответов ищется в именах файлов источников и в их текстах; печатает пары, которых нет нигде."""
import re,os,sys,glob,collections
ANS=sys.argv[1]; SRC=sys.argv[2:]  # папки текстов
MON='января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split()
names=[]; big=[]
for d in SRC:
    for f in os.listdir(d):
        names.append(f)
NM=' ‖ '.join(names)
pairs=collections.OrderedDict()
for f in sorted(glob.glob(ANS+'/q*.txt')):
    t=open(f,encoding='utf-8').read()
    for m in re.finditer(r'от (\d{2})\.(\d{2})\.(\d{4})\s+№\s?([0-9][0-9А-Яа-яA-Za-z/.\-]*)',t):
        num=m.group(4).rstrip('.,;-/')
        pairs.setdefault((m.group(1),m.group(2),m.group(3),num),[]).append('%s:%d'%(os.path.basename(f)[:-4],t.count('\n',0,m.start())+1))
print('пар дата+номер:',len(pairs))
# 1) по именам файлов
left=[]
for (d,mo,y,num),locs in pairs.items():
    date='%s.%s.%s'%(d,mo,y)
    if re.search(re.escape(date)+r'[^‖]{0,12}№ ?'+re.escape(num)+r'(?![\d-])',NM): continue
    left.append((d,mo,y,num,locs))
print('нет в именах файлов:',len(left))
# 2) по текстам
texts=None
def load():
    global texts
    if texts is None:
        texts=[]
        for dd in SRC:
            for f in os.listdir(dd):
                try: texts.append((f,re.sub(r'\s+',' ',open(os.path.join(dd,f),encoding='utf-8',errors='ignore').read())))
                except: pass
    return texts
for d,mo,y,num,locs in left:
    date='%s.%s.%s'%(d,mo,y); dl='%d %s %s'%(int(d),MON[int(mo)-1],y)
    rx=re.compile(r'(?:'+re.escape(date)+r'|'+dl+r')(?: ?г(?:ода|\.)?)?,? ?(?:N|№) ?'+re.escape(num)+r'(?![\d-])',re.I)
    hit=None
    for f,t in load():
        if rx.search(t): hit=f; break
    if hit: continue
    # тот же номер с другой датой
    rx2=re.compile(r'(\d{1,2}[. ](?:\d{2}|[а-я]+)[. ]\d{4})(?: ?г(?:ода|\.)?)?,? ?(?:N|№) ?'+re.escape(num)+r'(?![\d-])',re.I)
    alt=collections.Counter()
    for f,t in load():
        for m in rx2.finditer(t): alt[m.group(1)]+=1
    print('НЕ НАЙДЕНО: от %s № %s  [%s]  другие даты при этом номере: %s'%(date,num,', '.join(locs[:4]),alt.most_common(4)))
