#!/usr/bin/env python3
"""koapline26.py SRC ФАЙЛ… [-t ПОРОГ] — строки ответа по АДП против текста КоАП РФ.
Для каждой строки со ссылкой на статью КоАП (//ч. 2 ст. 20.1//, //ст. 27.2 КоАП РФ//) берётся текст названной части (или всей статьи),
считается доля слов строки, которые есть в норме. Печатаются строки ниже ПОРОГА (по умолчанию 45 %) и строки со ссылкой на часть,
которой в статье нет; под строкой — отрезок нормы с наибольшим совпадением. Пометка не означает ошибку — строка читается глазами.
Строки-перечни из одних ссылок (меньше шести слов без ссылок) и блок «Главное для запоминания» пропускаются.
    python3 tools/koapline26.py /tmp/src adp2/q139.txt adp2/q140.txt
"""
import sys,re,glob,os,importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
argv=sys.argv[:]; THR=45
if '-t' in argv: i=argv.index('-t'); THR=int(argv[i+1]); del argv[i:i+2]
sys.argv=argv[:2]            # sanpart26 при импорте читает только SRC
spec=importlib.util.spec_from_file_location('sp',os.path.join(HERE,'sanpart26.py')); sp=importlib.util.module_from_spec(spec)
import io,contextlib
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(sp)
def nz(s): return s.lower().replace('ё','е')
def toks(s): return set(w[:5] for w in re.findall(r'[а-яё]{4,}',nz(s)))
OTHER=r'/* ?(?:Уголовного|УК|Закона|УПК|Конституции|Правил|Федерального|Положения|Инструкции|Наставления|Порядка|Пленума|КАС|ГК|НК|Устава|Указа|№)'
REF=re.compile(r'(?:[Чч]\. ?([\d\.]+(?:(?:[–,]| и ) ?[\d\.]+)*),? )?[Сс]т\. (\d+\.\d+(?:\.\d+)?)|(?<![\w.])[Чч]\. ?([\d\.]+(?:(?:[–,]| и ) ?[\d\.]+)*)(?! ст\.)')
def plist(x):
    out=[]
    for y in re.split(r'[, и]+',x or ''):
        y=y.rstrip('.')
        if '–' in y:
            a,b=y.split('–')[:2]
            try:
                fa,fb=float(a),float(b); out+=[a,b]
            except ValueError: out.append(a)
        elif y: out.append(y)
    return out
W=40; n=bad=0
for f in argv[2:]:
    head=None; q=os.path.basename(f)[:-4]
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        if l.startswith('#'):
            m=re.search(r'[Сс]т(?:атья|\.) (\d+\.\d+(?:\.\d+)?)',l); head=m.group(1) if m else None; continue
        if l.startswith('!!') or not l.strip(): continue
        body=re.sub(r'//[^/]*//','',l); lt=toks(body)
        if len(re.findall(r'[а-яё]{4,}',nz(body)))<6: continue
        got=[]; last=head
        for m in REF.finditer(l):
            if re.match(OTHER,l[m.end():m.end()+40]): continue
            if m.group(2): a=m.group(2); ps=plist(m.group(1)); last=a
            else:
                a=last; ps=plist(m.group(3))
                if not a: continue
            d=sp.P(a)
            if not d: continue
            if ps:
                for p in ps: got.append(('ч. %s ст. %s'%(p,a), d.get(p)))
            else: got.append(('ст. %s'%a,' '.join(v for k,v in d.items() if not (k=='1' and ('загл' in d or '—' in d)))))
        if not got: continue
        n+=1
        allv=' '.join(t or '' for _,t in got); cov=100*len(lt&toks(allv))//max(1,len(lt))
        none=[k for k,t in got if t is None]
        if cov>=THR and not none: continue
        bad+=1
        print('%s:%d ~%d%%%s %s'%(q,i,cov,(' НЕТ '+'; '.join(none)) if none else '',l[:520]))
        for k,t in got:
            if not t: continue
            ws=t.split(); bi=0
            if len(ws)>W:
                sc=[1 if nz(w).strip('.,;:()«»"')[:5] in lt else 0 for w in ws]; c=sum(sc[:W]); b=c
                for j in range(1,len(ws)-W+1):
                    c+=sc[j+W-1]-sc[j-1]
                    if c>b: b=c;bi=j
            print('      [%s] %s%s'%(k,'…' if bi else '',' '.join(ws[bi:bi+W])))
print('строк со ссылкой на КоАП: %d, к чтению: %d'%(n,bad))
