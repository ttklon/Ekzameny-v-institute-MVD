#!/usr/bin/env python3
"""support.py КОД_ИЛИ_ПАПКА_ОТВЕТОВ ПАПКА_ТЕКСТОВ [-q РЕГ] [-t ДОЛЯ=0.45] [-w ОКНО=70] [-a] [-n] [-x ФАЙЛ…]
Опора каждого предложения ответа на источники (акты, практика, учебники, статьи).

Для предложения берутся значимые слова (по первым пяти буквам) и числа (цифрами и словами — в одном виде).
В текстах ищется место (окно ±ОКНО слов), где собрано больше всего этих слов с учётом их редкости.
Печатается:  ответ:строка  доля слов в лучшем месте | ЧИСЛО — числа, которых нет ни в одном месте,
где есть хотя бы ДОЛЯ слов предложения | СЛОВА — слова, которых нет ни в одном таком месте,
затем предложение и лучший отрывок источника. Без -a печатаются только предложения с пометкой ЧИСЛО
или с долей ниже ДОЛЯ; -n — только ЧИСЛО. Это отбор мест для чтения рядом с источником, а не вывод об ошибке.
Указатель текстов кладётся в ПАПКА_ТЕКСТОВ/_support.npz (строится один раз)."""
import sys,os,re,glob,math,pickle
import numpy as np
A=sys.argv[1:]
def opt(k,d=None,flag=False):
    if k in A:
        i=A.index(k)
        if flag: A.pop(i); return True
        v=A[i+1]; del A[i:i+2]; return v
    return d
QRE=opt('-q'); THR=float(opt('-t','0.45')); W=int(opt('-w','70')); ALL=opt('-a',flag=True); ONLYN=opt('-n',flag=True)
extra=[]
if '-x' in A:
    i=A.index('-x'); extra=A[i+1:]; del A[i:]
ans,src=A[0],A[1]
NUMW={}
def addn(v,*ws):
    for w in ws: NUMW[w]=v
addn(1,'один','одна','одно','одного','одной','одному','одним','одном','одну','одних')
addn(2,'два','две','двух','двум','двумя','двое','двоих','вдвое','дважды')
addn(3,'три','трех','трем','тремя','трое','троих','втрое','трижды')
addn(4,'четыре','четырех','четырем','четырьмя','четверо')
for v,b in [(5,'пят'),(6,'шест'),(7,'сем'),(8,'восьм'),(9,'девят'),(10,'десят'),(20,'двадцат'),(30,'тридцат')]:
    addn(v,b+'ь',b+'и',b+'ью')
addn(8,'восемь'); addn(7,'семью'); addn(8,'восемью')
for v,b in [(11,'одиннадцат'),(12,'двенадцат'),(13,'тринадцат'),(14,'четырнадцат'),(15,'пятнадцат'),(16,'шестнадцат'),(17,'семнадцат'),(18,'восемнадцат'),(19,'девятнадцат')]:
    addn(v,b+'ь',b+'и',b+'ью')
addn(40,'сорок','сорока'); addn(50,'пятьдесят','пятидесяти'); addn(60,'шестьдесят','шестидесяти'); addn(70,'семьдесят','семидесяти'); addn(80,'восемьдесят','восьмидесяти')
addn(90,'девяносто','девяноста'); addn(100,'сто','ста'); addn(200,'двести','двухсот'); addn(300,'триста','трехсот'); addn(400,'четыреста','четырехсот')
addn(500,'пятьсот','пятисот'); addn(600,'шестьсот','шестисот'); addn(700,'семьсот','семисот'); addn(800,'восемьсот','восьмисот'); addn(900,'девятьсот','девятисот')
addn(1000,'тысяча','тысячи','тысяч','тысячу','тысячей'); addn(1000000,'миллион','миллиона','миллионов')
PREF=[('одно',1),('двух',2),('трех',3),('четырех',4),('пяти',5),('шести',6),('семи',7),('восьми',8),('девяти',9),('десяти',10),('двенадцати',12),('пятнадцати',15),('двадцати',20),('тридцати',30),('сорока',40),('шестидесяти',60)]
UNIT=re.compile(r'^(дневн|суточн|месячн|летн|недельн|часов|кратн|процентн|минутн|годичн)')
ORD={}
TOK=re.compile(r'[а-яa-z]+|\d+')
def prep(t):
    t=t.lower().replace('ё','е')
    t=re.sub(r'(?m)^@@.*$',' ',t); t=re.sub(r'[-\u00ad]\s*\n\s*','',t)
    t=re.sub(r'(?<=\d)[ \u00a0](?=\d{3}(?!\d))','',t)
    return t
def toks(word):
    """слово -> список меток (числа '#N', основы)"""
    if word.isdigit(): return ['#'+str(int(word))]
    if word in NUMW: return ['#'+str(NUMW[word])]
    for p,v in PREF:
        if word.startswith(p) and UNIT.match(word[len(p):]): return ['#'+str(v), word[len(p):][:5]]
    if len(word)<4: return []
    return [word[:5] if len(word)>6 else word[:4]]
def build(src):
    cache=os.path.join(src,'_support.pkl')
    if os.path.exists(cache): return pickle.load(open(cache,'rb'))
    files=[f for f in sorted(glob.glob(src+'/*.txt'))]+extra
    voc={}; ids=[]; fstart=[]; pos=0; memo={}
    for f in files:
        t=prep(open(f,encoding='utf-8',errors='ignore').read()); cur=[]
        for w in TOK.findall(t):
            r=memo.get(w)
            if r is None:
                r=[voc.setdefault(x,len(voc)) for x in toks(w)]; memo[w]=r
            if r: cur.extend(r)
            else: cur.append(-1)
        fstart.append(pos); ids.append(np.array(cur,dtype=np.int32)); ids.append(np.full(3*W,-1,dtype=np.int32)); pos+=len(cur)+3*W
    arr=np.concatenate(ids) if ids else np.zeros(0,np.int32)
    order=np.argsort(arr,kind='stable'); sa=arr[order]
    bounds=np.searchsorted(sa,np.arange(len(voc)+1))
    d=dict(files=files,voc=voc,order=order.astype(np.int64),bounds=bounds,fstart=np.array(fstart),n=len(arr))
    pickle.dump(d,open(cache,'wb'),protocol=4); return d
D=build(src); voc=D['voc']; order=D['order']; bounds=D['bounds']; NT=D['n']
def P(tok):
    i=voc.get(tok)
    if i is None: return np.zeros(0,np.int64)
    return order[bounds[i]:bounds[i+1]]
def idf(tok):
    n=len(P(tok)); return math.log((NT+1)/(n+1))
def decomp(n):
    alts=[]
    if n>=1000 and n%1000==0 and n<1000000: alts.append([n//1000,1000])
    elif n>=1000000 and n%1000000==0: alts.append([n//1000000,1000000])
    elif 20<n<100 and n%10: alts.append([n-n%10,n%10])
    elif 100<n<1000 and n%100==0: pass
    elif 1000<n<1000000: alts.append([n//1000,1000,n%1000])
    return alts
_text={}
def window_text(pos):
    fs=D['fstart']; fi=int(np.searchsorted(fs,pos,side='right')-1); f=D['files'][fi]
    if f not in _text:
        t=prep(open(f,encoding='utf-8',errors='ignore').read()); _text[f]=(t,[m.start() for m in TOK.finditer(t)])
        if len(_text)>40: _text.pop(next(iter(_text)))
    t,offs=_text[f]; k=pos-int(fs[fi]); a=offs[max(0,k-W//2)] if offs else 0; b=offs[min(len(offs)-1,k+W//2)] if offs else 0
    return os.path.basename(f)[:52], re.sub(r'\s+',' ',t[a:b])
SKIPNUM=re.compile(r'(?:ст\.|стать[яиейюях]+|п\.|пункт[а-я]*|подп\.|ч\.|част[ьию]+|гл\.|глав[аеыу]+|№|вопрос[а-я]*|ответ[а-я]*|рис\.|табл\.|с\.|стр\.|примечани[а-я]+)\s*$',re.I)
def sentence_items(s):
    """-> (stems dict tok->слово, numbers list of (tok, слово))"""
    s0=re.sub(r'//.*?//',' ',s); s0=re.sub(r'\d{1,2}\.\d{1,2}\.\d{4}',' ',s0); s0=re.sub(r'\(\d{4}\)',' ',s0)
    s0=re.sub(r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4})?',' ',s0)
    s0=re.sub(r'№\s*[\dА-Яа-я./-]+',' ',s0)
    s0=re.sub(r'(?i)\b(?:ст\.|стать[а-я]+|п\.|пункт[а-я]*|подп\.|подпункт[а-я]*|ч\.|част[а-я]+|гл\.|глав[а-я]+|раздел[а-я]*|ответ[а-я]*|вопрос[а-я]*)\s*\d+(?:\.\d+)*(?:\s*(?:,|и|–|—|-|или)\s*\d+(?:\.\d+)*)*',' ',s0)
    t=prep(s0); st={}; nums=[]
    for m in TOK.finditer(t):
        w=m.group(0); r=toks(w)
        for x in r:
            if x[0]=='#':
                if w.isdigit() and (SKIPNUM.search(t[max(0,m.start()-14):m.start()]) or re.match(r'\.\d',t[m.end():m.end()+2]) or t[max(0,m.start()-1):m.start()]=='.'): continue
                if w.isdigit() and 1900<=int(w)<=2030: continue
                nums.append((x,w))
            else: st.setdefault(x,w)
    return st,nums
def check(sent,lead=''):
    st,nums=sentence_items(sent)
    lst,_=sentence_items(lead) if lead else ({},[])
    big=NT*0.002
    wts={k:idf(k) for k in st if 0<len(P(k))<big}
    none=[st[k] for k in st if len(P(k))==0]
    if len(wts)<3: return None
    lw={k:idf(k)*0.5 for k in lst if 0<len(P(k))<big and k not in wts}
    tot=sum(wts.values())
    rare=sorted(wts,key=lambda k:len(P(k)))[:5]
    cand=[P(k)[:40000] for k in rare]
    for x,_w in nums:
        p=P(x)
        if 0<len(p)<=20000: cand.append(p)
    C=np.unique(np.concatenate(cand))
    score=np.zeros(len(C)); pres={}
    def present(tok):
        a=P(tok)
        if not len(a): return np.zeros(len(C),bool)
        a=np.sort(a) if tok not in _sorted else a
        return (np.searchsorted(a,C+W)-np.searchsorted(a,C-W))>0
    for k,wt in wts.items():
        pr=present(k); pres[k]=pr; score+=wt*pr
    main=score.copy()
    for k,wt in lw.items(): score+=wt*present(k)
    bi=int(np.argmax(score)); best=main[bi]/tot
    ok=main>=THR*tot
    if not ok.any(): ok=main>=0.8*main.max()
    badn=[]
    for x,w in nums:
        n=int(x[1:])
        good=(present(x)&ok).any()
        if not good:
            for alt in decomp(n):
                g=ok.copy()
                for a in alt:
                    if a: g&=present('#'+str(a))
                if g.any(): good=True; break
        if not good: badn.append(w)
    badw=[st[k] for k in wts if not (pres[k]&ok).any()]+none
    return best,badn,badw,int(C[bi])
_sorted=set()
# позиции каждой метки уже отсортированы (stable argsort по меткам сохраняет порядок позиций)
class _All:
    def __contains__(self,x): return True
_sorted=_All()
def sentences(path):
    lead=''; 
    for i,l in enumerate(open(path,encoding='utf-8'),1):
        l=l.rstrip('\n')
        if not l.strip() or l.startswith('@@') or l.startswith('#'): 
            if l.startswith('#'): lead=''
            continue
        body=re.sub(r'^\s*(?:[-*>]|\d+\.|!!)\s*','',l)
        is_item=bool(re.match(r'^\s*(?:-|\d+\.)\s',l))
        parts=re.split(r'(?<=[.;!?…])\s+(?=[«*_(]*[А-ЯЁ0-9])',body)
        for p in parts:
            if len(p)>=25: yield i,p,(lead if is_item else '')
        if not is_item: lead=''
        if body.rstrip().endswith(':'): lead=body
if os.path.isdir(ans): files=sorted(glob.glob(ans+'/q*.txt'))
else: files=[ans]
tot=fl=0
for f in files:
    q=os.path.basename(f)[:4]
    if QRE and not re.search(QRE,q): continue
    for i,s,lead in sentences(f):
        r=check(s,lead)
        if r is None: continue
        tot+=1; best,badn,badw,pos=r
        show=ALL or badn or (best<THR and not ONLYN)
        if not show: continue
        fl+=1; name,txt=window_text(pos)
        tag=('ЧИСЛО '+' '.join(badn)+' | ' if badn else '')+('СЛОВА '+' '.join(badw[:12]) if badw else '')
        print('%s:%d  %d%%  %s'%(q,i,round(best*100),tag)); print('   > '+s[:600]); print('   = [%s] %s'%(name,txt[:900])); print()
print('предложений',tot,'показано',fl)
