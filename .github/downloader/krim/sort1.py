# -*- coding: utf-8 -*-
"""Криминалистика, первая загрузка: имена файлов, перенос из .work/krim в папки базы, manifest.json.
Без аргументов — показать; с --do — выполнить (один раз, после переноса повторно не запускать)."""
import sys, os, re, json, subprocess, urllib.parse
ROOT = '/home/user/Ekzameny-v-institute-MVD'; os.chdir(ROOT)
K = '.github/downloader/krim/'; sys.path.insert(0, K)
from books_meta import B, DROP
S = 'Криминалистика/2. Источники/'
D3 = S + '3. Учебная литература/'; D4 = S + '4. Научные материалы (с 2023 года)/'
D4OLD = D4 + 'Издания до 2023 года (сверить с действующими актами)/'; D4A = D4 + 'Статьи/'
DO = '--do' in sys.argv
used = set()
def clean(s):
    s = s.replace(':', ' —').replace('?', '').replace('"', '').replace('/', '-').replace('\\', '-').replace('*', '').replace('|', '-').replace('<', '').replace('>', '').replace('«', '').replace('»', '')
    return ' '.join(s.split())
def cut(title, room):
    title = clean(title)
    if len(title) <= room: return title
    out = []
    for x in title.split():
        if len(' '.join(out + [x])) + 1 > room and len(out) >= 3: break
        out.append(x)
    while len(out) > 3 and out[-1].lower().strip(',;—-') in ('и','в','на','по','с','к','о','об','при','за','для','как','от','из','их','а','или','не','—','-','со','во','у'):
        out.pop()
    return ' '.join(out).rstrip(',;—- ') + '…'
def fit(build, title, cap=130):
    room = len(clean(title))
    while True:
        name = build(cut(title, room))
        if (len(name) <= cap and len(name.encode('utf-8')) <= 225) or room <= 24: return name
        room -= 4
def uniq(name):
    base = name[:-4]; n = name; k = 2
    while n.lower() in used:
        n = '%s (%d).pdf' % (base, k); k += 1
    used.add(n.lower()); return n
def rng(q):
    q = sorted(set(q)); out = []; i = 0
    while i < len(q):
        j = i
        while j + 1 < len(q) and q[j + 1] == q[j] + 1: j += 1
        out.append(str(q[i]) if i == j else ('%d-%d' % (q[i], q[j]) if j > i + 1 else '%d,%d' % (q[i], q[j]))); i = j + 1
    return ','.join(out)
# ---------- книги
lst = {o['n']: o for o in json.load(open(K + 'lib1_list.json', encoding='utf-8'))}
top = json.load(open('.work/krim/lib_topics.json', encoding='utf-8'))
TQ = {'общ': [1,2,3,4,5], 'осмотр': [6,7,8,10,11], 'одор': [9], 'освид': [12], 'задерж': [13,14], 'допрос': [15,17,18,19,20,22], 'очн': [16],
      'опозн': [23,24,25,26,27], 'обыск': [28,29,30,31,32,33], 'экспер': [34,35,36], 'ппм': [37,38,39,40], 'кзп': [41,42,43,44]}
QFIX = {'078': [13, 14], '013': [15, 17, 18, 19], '071': [13, 14, 31], '106': [42, 43], '089': [10, 29], '080': [9, 10], '099': [10, 22, 27, 33, 40], '088': [5], '058': [18, 19], '085': [5, 13, 14], '103': [11, 28], '068': [11], '097': [11],
        '012': [10, 11], '014': [10, 22, 27, 33, 40], '011': [10, 22, 27, 33, 40], '035': [10, 22, 27, 33, 40, 44], '056': [10], '101': [7, 8, 9, 10], '087': [7, 9], '098': [7, 9],
        '067': [15, 16, 22, 23, 27], '033': [7, 8, 9, 10, 29, 35], '018': [7, 8, 9, 12, 29, 35], '032': [7, 8, 9, 29, 35]}
WORD = ('осмотр', 'задерж', 'допрос', 'опозн', 'обыск')
def bookq(n):
    """Вопросы издания — по числу упоминаний темы в тексте (пороги зависят от объёма издания)."""
    t = top[n]; c = t['c']; pg = min(t['pages'], 170); q = []; got = []
    for k, qq in TQ.items():
        thr = 40 if k == 'общ' else (max(25, 0.35 * pg) if k in WORD else max(12, 0.12 * pg))
        if c[k] >= thr: q += qq; got.append(k)
    if 'допрос' in got and c['несов'] >= 15: q.append(21)
    return sorted(set(q)), len(got)
ops = []; man = []
for n in sorted(B):
    au, title, kind, pub, year, cat = B[n]
    src = '.work/krim/lib/%s.pdf' % n
    kcap = kind[0].upper() + kind[1:]
    name = uniq(fit(lambda t: '%s%s. %s. %s, %s.pdf' % ((au.rstrip('.') + '. ') if au else '', t, kcap, pub, year), title, cap=127))
    dst = {3: D3, 4: D4, '4old': D4OLD}[cat] + name
    q, ntop = bookq(n)
    general = (cat == 4) or ntop >= 8
    if n in QFIX and not general: q = QFIX[n]
    man.append(dict(key='b' + n, cat=3 if cat == 3 else 4, old=(cat == '4old'), authors=au, title=title, kind=kind, pub=pub, year=year, pages=top[n]['pages'],
                    size=os.path.getsize(src) if os.path.exists(src) else 0, qn=q, q=rng(q), general=general, collection=(cat == 4), name=name, dst=dst, type='book',
                    url=urllib.parse.quote(lst[n]['url'], safe=':/'), lib=lst[n]['rel'], topics=top[n]['c'], garbled=False))
    ops.append(('mv', src, dst))
for n, why in sorted(DROP.items()):
    ops.append(('rm', '.work/krim/lib/%s.pdf' % n, why))
# ---------- статьи
PATR = re.compile(r'(ович|евич|ьич|ич|овна|евна|ична|инична|оглы|кызы)$', re.I)
def author(a):
    a = ' '.join(a.replace('.', '. ').split()); t = a.split()
    ini = [x for x in t if re.fullmatch(r'[А-ЯЁA-Z]\.', x)]
    if ini: return ' '.join(x for x in t if not re.fullmatch(r'[А-ЯЁA-Z]\.', x)), ''.join(ini)
    if len(t) == 3:
        if PATR.search(t[2]): return t[0], t[1][0] + '.' + t[2][0] + '.'
        if PATR.search(t[1]): return t[2], t[0][0] + '.' + t[1][0] + '.'
        return t[0], t[1][0] + '.' + t[2][0] + '.'
    if len(t) == 2: return t[0], t[1][0] + '.'
    return a, ''
KEEP = ['МВД','ОВД','РФ','УПК','УК','ДТП','ИВС','СМИ','ОРД','ОПГ','IT','КоАП','РСФСР','3D']
PROPER = [('российской федерации','Российской Федерации'),('российская федерация','Российская Федерация'),('россии','России'),('россия','Россия'),('российск','российск'),
          ('министерств','Министерств'),('конституционного суда','Конституционного Суда'),('интернет','Интернет'),('даркнет','Даркнет')]
def sentence(t):
    t = ' '.join(t.split()); letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        t = t.lower(); t = t[0].upper() + t[1:]
        for a, b in PROPER: t = re.sub(a, b, t)
        for k in KEEP: t = re.sub(r'(?<![а-яёa-z])%s(?![а-яёa-z])' % k.lower(), k, t)
        t = re.sub(r'([.?!]\s+)([а-яё])', lambda m: m.group(1) + m.group(2).upper(), t)
    return t
DROP_A = json.load(open(K + 'cyber1_dropped.json', encoding='utf-8'))
ainfo = json.load(open('.work/krim/art_info.json', encoding='utf-8'))
sel = json.load(open(K + 'cyber1_selected.json', encoding='utf-8'))
for c in sel:
    n = c['n']; f = '.work/krim/cyber/%s.pdf' % n
    if n in DROP_A:
        if os.path.exists(f): ops.append(('rm', f, DROP_A[n]))
        continue
    au = [author(x) for x in c['authors'].split(';') if x.strip()]
    afull = ', '.join(('%s %s' % a).strip() for a in au)
    ash = au[0][0] + ' и др.' if len(au) >= 3 else ', '.join(a[0] for a in au)
    title = sentence(c['title'])
    jr = clean(c['journal']).replace('Министерства внутренних дел Российской Федерации', 'МВД РФ').replace('Министерства внутренних дел России', 'МВД России')
    if len(jr) > 75: jr = jr.split('. ')[0]
    if len(jr) > 75: jr = cut(jr, 75)
    name = fit(lambda t: '%s. %s. %s, %s.pdf' % (ash.rstrip('.'), t, jr, c['year']), title, cap=127)
    if len(name.encode('utf-8')) > 225 or len(name) > 135:
        jr = cut(jr.split('. ')[0], 45); ash = cut(ash, 40) if len(ash) > 40 else ash
        name = fit(lambda t: '%s. %s. %s, %s.pdf' % (ash.rstrip('.'), t, jr, c['year']), title, cap=127)
    name = uniq(name)
    i = ainfo[n]
    man.append(dict(key=n, cat=4, old=False, authors=afull, title=title, kind='статья (журнал из перечня ВАК)' if c['vak'] else 'статья', pub=c['journal'], year=c['year'],
                    pages=i['pages'], size=i['size'], qn=[q for q in c['q'] if q], q=rng([q for q in c['q'] if q]), general=(c['q'] == [0]), collection=False, name=name, dst=D4A + name,
                    type='article', url='https://cyberleninka.ru' + c['slug'], garbled=i['garbled']))
    ops.append(('mv', f, D4A + name))
print('перенос:', sum(1 for o in ops if o[0] == 'mv'), 'удаление:', sum(1 for o in ops if o[0] == 'rm'))
if not DO:
    for m in man:
        if m['type'] == 'book': print(m['key'], '|', m['q'] or '-', '| общ' if m['general'] else '', '|', m['name'])
    for m in man[79:92]: print(m['key'], m['q'], m['name'])
    print('макс. длина имени, байт:', max(len(m['name'].encode()) for m in man))
    sys.exit()
for d in (D3, D4, D4OLD, D4A): os.makedirs(d, exist_ok=True)
for op, a, b in ops:
    if op == 'mv': subprocess.run(['git', 'mv', a, b], check=True)
    else: subprocess.run(['git', 'rm', '-q', a], check=True)
json.dump(man, open(K + 'manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
json.dump([dict(file=a, why=b) for op, a, b in ops if op == 'rm'], open(K + 'removed1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('готово, записей в manifest.json:', len(man))
