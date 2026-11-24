#!/usr/bin/env python3
"""numcmp.py ФАЙЛ_RECENT ПАПКА_ТЕКСТОВ КОД_АКТА ['regex ссылки']

Числа в предложениях, которые ссылаются на изменённую часть статьи, против текста этой статьи.
Берёт вывод recent.py, для каждого предложения со ссылкой на конкретную часть или пункт выписывает числа
(цифрами и словами) и печатает те предложения, чьих чисел нет в тексте всей статьи (отметки о редакции
из статьи убраны). Ложные пометки: число относится к другой ссылке в том же предложении; год и номер
изменяющего закона; «четырнадцати лет» при «четырнадцатилетнего возраста» в норме.
"""
import sys,glob,re,os
if len(sys.argv)<4: sys.exit(__doc__)
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import lawtext as L
rec,k,fid=sys.argv[1:4]; pat=sys.argv[4] if len(sys.argv)>4 else r'(ч|п) [^,]* ст [\d.]+'
p=(glob.glob(os.path.join(k,'*%s*'%fid)) or glob.glob('/tmp/s_%s/*%s*'%(k,fid)))[0]
U={'ноль':0,'один':1,'одн':1,'дв':2,'три':3,'тре':3,'четыр':4,'пят':5,'шест':6,'сем':7,'восьм':8,'восем':8,'девят':9,'десят':10,
'одиннадцат':11,'двенадцат':12,'тринадцат':13,'четырнадцат':14,'пятнадцат':15,'шестнадцат':16,'семнадцат':17,'восемнадцат':18,'девятнадцат':19,
'двадцат':20,'тридцат':30,'сорок':40,'сорока':40,'пятидесят':50,'пятьдесят':50,'шестидесят':60,'шестьдесят':60,'семидесят':70,'семьдесят':70,'восьмидесят':80,'восемьдесят':80,'девяност':90,
'сто':100,'ста':100,'двухсот':200,'двести':200,'двумстам':200,'трехсот':300,'триста':300,'четырехсот':400,'четыреста':400,'пятисот':500,'пятьсот':500,'шестисот':600,'шестьсот':600,'семисот':700,'семьсот':700,'восьмисот':800,'восемьсот':800,'девятисот':900,'девятьсот':900,
'полутор':1.5}
keys=sorted(U,key=len,reverse=True)
def tok(w):
    w=w.lower().replace('ё','е')
    if w.startswith('тысяч'): return 'K'
    if w.startswith('миллион'): return 'M'
    for kk in keys:
        if w==kk or (w.startswith(kk) and len(w)-len(kk)<=3 and kk not in ('сто','ста','три','сем','дв','одн','пят','шест','тре')): return U[kk]
    for kk in ('сто','ста','три','сем'):
        if w==kk: return U[kk]
    if re.fullmatch(r'дв(а|е|ух|ум|умя)',w): return 2
    if re.fullmatch(r'одн(а|ой|у|ого|ому|им|ом|и|их)',w): return 1
    if re.fullmatch(r'пят(ь|и|ью)',w): return 5
    if re.fullmatch(r'шест(ь|и|ью)',w): return 6
    if re.fullmatch(r'тр(ех|ем|и|емя)',w): return 3
    if re.fullmatch(r'сем(ь|и|ью)',w): return 7
    return None
def wnums(t):
    out=set(); cur=0; tot=0; act=False
    for w in re.findall(r'[А-Яа-яёЁ]+|\d[\d ]*\d|\d|[^\sА-Яа-яёЁ\d]+',t):
        v=tok(w) if re.match(r'[А-Яа-яёЁ]',w) else None
        if v is None:
            if act: out.add(tot+cur)
            cur=tot=0; act=False
            if re.match(r'\d',w): 
                try: out.add(float(w.replace(' ','')))
                except: pass
            continue
        act=True
        if v=='K': tot+=(cur or 1)*1000; cur=0
        elif v=='M': tot+=(cur or 1)*1000000; cur=0
        else: cur+=v
    if act: out.add(tot+cur)
    return {float(x) for x in out}
def snums(s):
    s=re.sub(r'//.*?//','',s)       # ссылки
    s=re.sub(r'\b(ч|п|ст|гл|№)\.? ?[\d., и–-]+','',s)
    out=set()
    for m in re.finditer(r'(?<![\d.])(\d{1,3}(?:[  ]\d{3})+|\d+)(?![\d.]|[  ]?(?:год[ауе]? (?:№|\d)|-ФЗ))( млн| тыс)?',s):
        v=float(re.sub(r'[  ]','',m.group(1)))
        if m.group(2): v*=1000000 if 'млн' in m.group(2) else 1000
        if 1900<v<2100: continue
        out.add(v)
    return out|{x for x in wnums(s) if x>=2}
t=open(rec,encoding='utf-8').read(); seen=set(); n=bad=0
for b in re.split(r'\n\s*\n',t):
    m=re.match(r'\S+/(\S+:\d+)\s+\[(.*?)\]',b)
    if not m or not re.fullmatch(pat,m.group(2)): continue
    ls=b.split('\n'); sent=ls[1].strip(); key=(m.group(1),sent[:60])
    if key in seen: continue
    seen.add(key); n+=1
    art=re.search(r'ст ([\d.]+)',m.group(2)).group(1)
    body=re.sub(r'\s+',' ',L.articles(p).get(art,''))
    body=re.sub(r'\((?:В редакции|Дополнение|Утратил|Статья в редакции|Часть|Пункт)[^()]*\)','',body)
    nn=wnums(body)
    miss=sorted(x for x in snums(sent) if x not in nn and x>=2)
    if miss:
        bad+=1; print(m.group(1),'['+m.group(2)+']',[int(x) if x==int(x) else x for x in miss],'|',sent[:330])
print('-- предложений:',n,'с числами вне статьи:',bad)
