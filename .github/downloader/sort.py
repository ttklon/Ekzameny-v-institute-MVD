import json,re,os,subprocess,sys
sys.path.insert(0,'.work'); import libplan
P=libplan.P
S="Административная деятельность полиции/2. Источники/"
D={3:S+'3. Учебная литература/',4:S+'4. Научные материалы (с 2023 года)/',5:S+'5. Эмпирические материалы (с 2023 года)/'}
QFIX={'178':'100-102,124-126','188':'45,46,49,100-102','046':'52,87-90','006':'41,142-144','078':'91-96,118,136','104':'87-90,117','132':'87-90,117,59-66','120':'136,148,149','251':'142-144','222':'2,13,91,109,119,148','238':'2,13,91,109,119,148','169':'7,8','170':'7,8','035':'50,131-133','150':'103,104,107,108','155':'50,103-108','157':'103,104','156':'50,103-108','073':'131-133'}
def clip(name,lim=225):
    if len(name.encode())<=lim: return name
    stem=name[:-4]
    # режем название (первую длинную часть) по словам
    parts=stem.split('. ')
    i=max(range(len(parts)),key=lambda j:len(parts[j]))
    for _ in range(400):
        if len(('. '.join(parts)+'.pdf').encode())<=lim: break
        w=parts[i].rstrip('…')
        w=w.rsplit(' ',1)[0] if ' ' in w else w[:-3]
        parts[i]=w.rstrip(' ,(-—')+'…'
    return '. '.join(parts)+'.pdf'
man=[]
for k,p in P.items():
    if k in QFIX: p['q']=QFIX[k]; p['qn']=libplan.expand(p['q'])
    a=p['authors']
    if p['cat']==4 and re.search(r'сборник|материалы',p['kind']): a=''
    a=re.sub(r'^ред\. ','',a) + (' (ред.)' if a.startswith('ред.') else '')
    t=libplan.short(p['title'],400).replace('российской федерации','РФ')
    kind=p['kind'].replace('учебно-практиче-ское','учебно-практическое')
    if k=='191': t='Вопросы совершенствования деятельности полиции по охране ОП. Сборник научных трудов № 30'; kind=''
    ps=libplan.PUBS.get(p['pub'],p['pub'])
    name=(a.rstrip('.')+'. ' if a else '')+t+'. '+((kind[0].upper()+kind[1:]+'. ') if kind else '')+ps+', '+p['year']+'.pdf'
    for x,y in ((':',' —'),('/','-'),('«',''),('»',''),('"',''),('?',''),('  ',' ')): name=name.replace(x,y)
    name=clip(name)
    p.update(name=name,dst=D[p['cat']]+name,authors=a,kind=kind or 'сборник научных трудов',type='book')
    man.append(p)
# статистика
ST=[('.work/stat/giac_2024.pdf','ГИАЦ МВД России. Состояние преступности в России за январь–декабрь 2024 года.pdf','ФКУ «ГИАЦ МВД России»','Состояние преступности в России за январь–декабрь 2024 года','статистический сборник','2025','2,13,91,109,119,148','https://portal.tpu.ru/SHARED/n/NIKOLAENKOVS/student/risk_management/Sbornik_UOS_2024.pdf'),
('.work/stat/giac_2025.pdf','ГИАЦ МВД России. Состояние преступности в России за январь–декабрь 2025 года.pdf','ФКУ «ГИАЦ МВД России»','Состояние преступности в России за январь–декабрь 2025 года','статистический сборник','2026','2,13,91,109,119,148','https://portal.tpu.ru/SHARED/n/NIKOLAENKOVS/student/risk_management/Sbornik_dlya_UOS.pdf'),
('.work/stat/ka_sibli.pdf','Комплексный анализ состояния преступности в РФ по итогам 2025 года и ожидаемые тенденции ее развития. Аналитический обзор. ВНИИ МВД, 2026.pdf','ВНИИ МВД России','Комплексный анализ состояния преступности в Российской Федерации по итогам 2025 года и ожидаемые тенденции ее развития','аналитический обзор','2026','2,13,91,109,119,148','lib.sibli.ru'),
('.work/stat/cdep_1AP_2024.xls','Судебный департамент при ВС РФ. Форма № 1-АП. Отчет о работе судов общей юрисдикции по рассмотрению дел об АП за 2024 год.xls','Судебный департамент при Верховном Суде РФ','Форма № 1-АП «Отчет о работе судов общей юрисдикции по рассмотрению дел об административных правонарушениях» за 12 месяцев 2024 года','судебная статистика (xls)','2025','28,59-66,116-141,147','https://cdep.ru/userimages/Statistika_2024/F2-svod_vse_sudy-2024.xls')]
for src,name,pub,title,kind,year,q,url in ST:
    man.append(dict(key=os.path.basename(src),cat=5,authors='',title=title,kind=kind,pub=pub,year=year,pages=0,size=os.path.getsize(src),q=q,qn=libplan.expand(q),name=name,src=src,dst=D[5]+name,type='stat',url=url))
# статьи
C=json.load(open('/tmp/cyber_chk.json'))
FIX=[('российской федерации','Российской Федерации'),('россии','России'),(' мвд',' МВД'),('коап','КоАП'),(' рф',' РФ'),(' овд',' ОВД'),('гибдд','ГИБДД'),('росгвард','Росгвард'),('снг','СНГ')]
def ini(full):
    out=[]
    for x in full.split(';'):
        w=[i.capitalize() if i.isupper() else i for i in x.strip().split()]
        if not w: continue
        if len(w)>=3 and re.fullmatch(r'[А-ЯЁ]\.',w[0]): w=[w[-1]]+w[:-1]
        if len(w)>=3 and re.search(r'(вич|вна|ична|ьич|оглы|кызы)$',w[1]) and not re.search(r'(вич|вна|ична|ьич|оглы|кызы)$',w[2]): w=[w[2],w[0],w[1]]
        out.append(w[0]+(' '+''.join(i[0].upper()+'.' for i in w[1:3]) if len(w)>1 else ''))
    return out
def jshort(j):
    j=re.sub(r'\s+',' ',j).strip()
    j=re.sub(r' имени [А-ЯЁ]\. ?[А-ЯЁ]\. ?[А-ЯЁа-яё]+| им\. [А-ЯЁ]\. ?[А-ЯЁ]\. ?[А-ЯЁа-яё]+','',j)
    j=re.sub(r'\. Серия.*$','',j)
    for x,y in (('юридического института','ЮИ'),('Юридического института','ЮИ'),('университета','ун-та'),('Министерства внутренних дел','МВД'),('государственного','гос.'),('Российской Федерации','РФ')): j=j.replace(x,y)
    return j
os.makedirs(D[4]+'Статьи',exist_ok=True)
seen=set()
for a in C:
    if a['n']==83 or 'pages' not in a: continue
    t=' '.join(a['t'].split())
    if sum(c.isupper() for c in t)>len(t)*0.5:
        t=t.lower(); t=t[0].upper()+t[1:]
        for x,y in FIX: t=t.replace(x,y)
    a['a']={8:'Кононов А. М.',10:'Бурчикаускас В. А.; Кот Е. А.',58:'Кудряшов А. В.'}.get(a['n'],a['a'])
    au=ini(a['a']); aus=', '.join(au) ; sh=(au[0].split()[0]+(' и др.' if len(au)>2 else (', '+au[1].split()[0] if len(au)==2 else ''))) if au else ''
    j=jshort(a['j'])
    name=(sh.rstrip('.')+'. ' if sh else '')+t.rstrip('.')+'. '+j+', '+a['year']+'.pdf'
    for x,y in ((':',' —'),('/','-'),('«',''),('»',''),('"',''),('?',''),('  ',' '),('\\','-'),('*','')): name=name.replace(x,y)
    name=clip(name,236)
    while name in seen: name=name[:-4]+' (2).pdf'
    seen.add(name)
    q=','.join(a['tags'])
    man.append(dict(key='c%03d'%a['n'],cat=4,authors=aus,title=t,kind='статья'+(' (журнал из перечня ВАК)' if a['vak'] else ''),pub=j,year=a['year'],pages=a['pages'],size=a['size'],q=q,qn=libplan.expand(q),name=name,src='.work/cyber/%03d.pdf'%a['n'],dst=D[4]+'Статьи/'+name,type='article',url='https://cyberleninka.ru'+a['link'],garbled=a['hit'].startswith('0/')))
json.dump(man,open('.work/manifest.json','w'),ensure_ascii=False,indent=0)
if '--do' in sys.argv:
    for m in man:
        os.makedirs(os.path.dirname(m['dst']),exist_ok=True)
        os.replace(m['src'],m['dst'])
import collections
print(collections.Counter((m['cat'],m['type']) for m in man), sum(m['size'] for m in man)//2**20,'MB', max(len(m['name'].encode()) for m in man))
cov=collections.defaultdict(lambda:[0,0,0])
for m in man:
    for q in m['qn']: cov[q][m['cat']-3]+=1
print('без учебной:',[q for q in range(1,150) if not cov[q][0]]); print('без научной:',[q for q in range(1,150) if not cov[q][1]]); print('без эмпирики:',[q for q in range(1,150) if not cov[q][2]])
for m in man:
    if m['type']=='article' and ('…' in m['name'] or not m['authors'] or len(m['name'].encode())>225): print(len(m['name'].encode()),m['name'],'|',m['authors'][:40])
print([ (m['key'],len(m['name'].encode())) for m in man if len(m['name'].encode())>236])
