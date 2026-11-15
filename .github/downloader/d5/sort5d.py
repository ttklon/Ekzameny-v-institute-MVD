# -*- coding: utf-8 -*-
"""Раскладка изданий, статей и эмпирических материалов пяти дисциплин из .work/d5 по папкам «2. Источники»;
сведения — в manifest_<код>.json. Повторный запуск безопасен: уже разложенное не трогается.
Запуск: /tmp/venv/bin/python sort5d.py [коды]."""
import os, re, sys, json, glob, shutil, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
import fitz
os.chdir(ROOT)
fitz.TOOLS.mupdf_display_errors(False)
D3 = '3. Учебная литература/'; D4 = '4. Научные материалы (с 2023 года)/'; D4OLD = D4 + 'Издания до 2023 года (сверить с действующими актами)/'; D4A = D4 + 'Статьи/'
D5E = '5. Эмпирические материалы (с 2023 года)/'
PATR = re.compile(r'(ович|евич|ьич|ич|овна|евна|ична|инична|оглы|кызы)$', re.I)
KEEP = ['МВД', 'ОВД', 'РФ', 'УПК', 'УК', 'ДТП', 'ИВС', 'СМИ', 'ОРД', 'ОПГ', 'IT', 'КоАП', 'РСФСР', 'ГПК', 'ТК', 'АПК', 'КАС', 'ГК', 'ЧС', 'ЧО', 'ВС', 'КС', 'ФСИН', 'МЧС', 'ООН', 'МОТ', 'ЕАЭС', 'СНГ', 'ИИ', 'ВКС']
PROPER = [('российской федерации', 'Российской Федерации'), ('российская федерация', 'Российская Федерация'), ('россии', 'России'), ('россия', 'Россия'), ('россию', 'Россию'), ('россией', 'Россией'),
          ('верховного суда', 'Верховного Суда'), ('верховный суд', 'Верховный Суд'), ('конституционного суда', 'Конституционного Суда'), ('конституционный суд', 'Конституционный Суд'),
          ('уголовного кодекса', 'Уголовного кодекса'), ('трудового кодекса', 'Трудового кодекса'), ('трудовой кодекс', 'Трудовой кодекс'), ('уголовный кодекс', 'Уголовный кодекс'), ('москв', 'Москв'), ('пленума', 'Пленума')]
def clean(s):
    s = s.replace(':', ' —').replace('?', '').replace('"', '').replace('/', '-').replace('\\', '-').replace('*', '').replace('|', '-').replace('<', '').replace('>', '').replace('«', '').replace('»', '')
    return ' '.join(s.split()).strip(' .')
def cut(title, room):
    title = clean(title)
    if len(title) <= room: return title
    out = []
    for x in title.split():
        if len(' '.join(out + [x])) + 1 > room and len(out) >= 3: break
        out.append(x)
    while len(out) > 3 and out[-1].lower().strip(',;—-') in ('и', 'в', 'на', 'по', 'с', 'к', 'о', 'об', 'при', 'за', 'для', 'как', 'от', 'из', 'их', 'а', 'или', 'не', '—', '-', 'со', 'во', 'у'): out.pop()
    return ' '.join(out).rstrip(',;—- ') + '…'
def fit(build, title, cap=130):
    room = len(clean(title))
    while True:
        name = build(cut(title, room))
        if (len(name) <= cap and len(name.encode('utf-8')) <= 225) or room <= 24: break
        room -= 4
    while len(name.encode('utf-8')) > 225:   # крайний случай: слишком длинные авторы или журнал
        base, ext = os.path.splitext(name); name = base[:-2].rstrip(' .,') + ext
    return name
def author(a):
    a = ' '.join(a.replace('.', '. ').split()); t = a.split()
    ini = [x for x in t if re.fullmatch(r'[А-ЯЁA-Z]\.', x)]
    if ini: return ' '.join(x for x in t if not re.fullmatch(r'[А-ЯЁA-Z]\.', x))
    if len(t) == 3:
        if PATR.search(t[2]): return t[0]
        if PATR.search(t[1]): return t[2]
        return t[0]
    if len(t) == 2: return t[0]
    return t[0] if t else a
def sentence(t):
    t = ' '.join(t.split()); letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        t = t.lower(); t = t[0].upper() + t[1:]
        for a, b in PROPER: t = re.sub(a, b, t)
        for k in KEEP: t = re.sub(r'(?<![а-яёa-z])%s(?![а-яёa-z])' % k.lower(), k, t)
        t = re.sub(r'([.?!]\s+)([а-яё])', lambda m: m.group(1) + m.group(2).upper(), t)
    return t
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def pdf_ok(p):
    try:
        if open(p, 'rb').read(5)[:4] != b'%PDF': return 0
        d = fitz.open(p); n = d.page_count; d.close(); return n
    except Exception: return 0
SCI = ('монограф', 'сборник', 'материал', 'научн', 'труды', 'аналитич', 'диссерт', 'автореф')
A_E = 'Административная деятельность полиции/2. Источники/5. Эмпирические материалы (с 2023 года)/'; K_E = 'Криминалистика/2. Источники/5. Эмпирические материалы (с 2023 года)/'
SD = 'Судебный департамент при ВС РФ. '
CDEP = {'f3_': 'Форма № 2. Гражданские и административные дела, первая инстанция, %s год', 'f6_': 'Форма № 6. Уголовные дела, апелляция, %s год',
        'f7_': 'Форма № 7. Гражданские и административные дела, апелляция, %s год', 'f8_': 'Форма № 8. Уголовные дела, кассация, %s год',
        'f9_': 'Форма № 9. Гражданские и административные дела, кассация, %s год', 'f8n_': 'Форма № 8-н. Уголовные дела, надзор (Верховный Суд РФ), %s год',
        'f9n_': 'Форма № 9-н. Гражданские и административные дела, надзор (Верховный Суд РФ), %s год',
        'k3_': 'Судимость. Число осужденных по всем составам преступлений УК РФ, %s год', 'k4_': 'Судимость. Привлеченные к уголовной ответственности и виды наказания, %s год',
        'k52_': 'Судимость. Характеристика преступления, его рецидива и повторности, %s год', 'k1_': 'Судимость. Несовершеннолетние осужденные, %s год',
        'k6_': 'Судимость. Особенности рассмотрения уголовных дел и основания их прекращения, %s год'}
EMP = {'upp': dict(copy=['ГИАЦ', 'Комплексный анализ', 'Обзор судебной статистики', 'Форма № 1.'], cdep=['f6_', 'f8_', 'f8n_']),
       'up': dict(copy=['ГИАЦ', 'Комплексный анализ', 'Обзор судебной статистики'], cdep=['k3_', 'k4_', 'k52_', 'k1_', 'k6_']),
       'gpp': dict(copy=['Обзор судебной статистики'], cdep=['f3_', 'f7_', 'f9_', 'f9n_']),
       'tp': dict(copy=['Обзор судебной статистики'], cdep=['f3_']),
       'tsp': dict(copy=['ГИАЦ', 'Комплексный анализ'], cdep=[])}
def run(code):
    S = DISC[code]['dir'] + '/2. Источники/'
    MP = D5 + 'manifest_%s.json' % code
    man = {m['key']: m for m in (json.load(open(MP, encoding='utf-8')) if os.path.exists(MP) else [])}
    man = {k: m for k, m in man.items() if os.path.exists(S + m['dst'])}
    used = {os.path.basename(m['dst']).lower() for m in man.values()}
    def uniq(name):
        base, ext = os.path.splitext(name); n = name; k = 2
        while n.lower() in used: n = '%s (%d)%s' % (base, k, ext); k += 1
        used.add(n.lower()); return n
    def save(): json.dump(sorted(man.values(), key=lambda m: (m['cat'], m['dst'])), open(MP, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    import atexit; atexit.register(save)
    tt = topics(code); ref = {t['id']: t['refs'] for t in tt}
    stat = {'книг': 0, 'статей': 0, 'эмпир': 0, 'брак': 0, 'не по теме': 0}
    # --- издания библиотеки
    BP = D5 + 'books_%s.json' % code
    for b in (json.load(open(BP, encoding='utf-8')) if os.path.exists(BP) else []):
        src = '.work/d5/%s/lib/%s.pdf' % (code, b['n'])
        if b['n'] in man or not os.path.exists(src): continue
        if b.get('bad') or b.get('off') or not pdf_ok(src): stat['брак' if not b.get('off') else 'не по теме'] += 1; os.remove(src); continue
        title = re.sub(r'^[А-ЯЁ]\s?\d{1,3}\s+', '', sentence(b['title'])); kind = (b.get('kind') or '').strip(); year = b.get('year') or 0
        kindc = kind[:1].upper() + kind[1:] if kind else ''
        tail = '. '.join(x for x in [kindc, ', '.join(x for x in [b.get('pub') or '', str(year) if year else ''] if x)] if x)
        au = clean(b.get('authors') or '')
        name = uniq(fit(lambda t: '. '.join(x for x in [au, t if not t.endswith('…') else t, tail] if x).replace('…. ', '…. ') + '.pdf', title, cap=150))
        sci = any(k in kind.lower() for k in SCI) or (not kind and re.search(r'сборник (научн|стат|материал)|материалы .*конференц|монограф', title, re.I))
        old = bool(year and year < 2023)
        folder = (D4OLD if old else D4) if sci else D3
        os.makedirs(S + folder, exist_ok=True); shutil.move(src, S + folder + name)
        man[b['n']] = dict(key=b['n'], cat='sci' if sci else 'book', authors=au, title=title, kind=kind, pub=b.get('pub') or '', year=year, pages=b.get('pages') or 0, size=b['size'],
                           q=b.get('q') or [], general=bool(b.get('general')), dst=folder + name, url=b['url'], how=b.get('how'), old=old, garbled=not b.get('textlayer', True), lib=b.get('lib'))
        stat['книг'] += 1
    # --- статьи
    arts = []
    for f in [D5 + 'cyber_%s_selected.json' % code, D5 + 'cyber_%s2_selected.json' % code]:
        if os.path.exists(f): arts += json.load(open(f, encoding='utf-8'))
    for c in arts:
        src = '.work/d5/%s/art/%s.pdf' % (code, c['n'])
        if c['n'] in man:
            man[c['n']]['q'] = c['t']; continue
        if not os.path.exists(src): continue
        n = pdf_ok(src)
        if not n: stat['брак'] += 1; os.remove(src); continue
        al = [author(a) for a in re.split(r'[,;]\s*', c['authors']) if a.strip()]
        au = ', '.join(al[:2]) + (' и др.' if len(al) > 2 else '')
        title = sentence(c['title']); j = clean(c['journal'])
        if len(j) > 70: j = cut(j, 60).rstrip('…')
        if len(au) > 60: au = al[0] + ' и др.'
        name = uniq(fit(lambda t: '%s. %s. %s, %s.pdf' % (clean(au), t, j, c['year']), title, cap=150).replace('…..', '….'))
        os.makedirs(S + D4A, exist_ok=True); shutil.move(src, S + D4A + name)
        man[c['n']] = dict(key=c['n'], cat='art', authors=au, title=title, kind='статья', pub=c['journal'], year=int(c['year']), pages=n, size=os.path.getsize(S + D4A + name), q=c['t'], general=bool(c.get('general')), wide=bool(c.get('wide')),
                           dst=D4A + name, url='https://cyberleninka.ru' + c['slug'], vak=c['vak'])
        stat['статей'] += 1
    # --- эмпирические материалы
    os.makedirs(S + D5E, exist_ok=True)
    for pat in EMP[code]['copy']:
        for src in sorted(glob.glob(K_E + '*') + glob.glob(A_E + '*')):
            name = os.path.basename(src)
            if pat not in name or 'emp:' + name in man or not os.path.isfile(src): continue
            if not os.path.exists(S + D5E + name): shutil.copyfile(src, S + D5E + name)
            man['emp:' + name] = dict(key='emp:' + name, cat='emp', title=name, dst=D5E + name, size=os.path.getsize(src), url='', pages=pdf_ok(src) if name.endswith('.pdf') else 0, q=[], general=True, year=0,
                                      note='из базы «%s»' % src.split('/')[0]); stat['эмпир'] += 1
    for pre in EMP[code]['cdep']:
        for src in sorted(glob.glob('.work/d5/stat/cdep_%s*.xls' % pre)):
            year = re.search(r'(\d{4})[a-e]?\.xls$', src).group(1); name = SD + CDEP[pre] % year + '.xls'
            assert len(name.encode('utf-8')) <= 225, name
            if 'emp:' + name in man: continue
            if open(src, 'rb').read(4) != b'\xd0\xcf\x11\xe0': continue
            shutil.copyfile(src, S + D5E + name)
            man['emp:' + name] = dict(key='emp:' + name, cat='emp', title=name, dst=D5E + name, size=os.path.getsize(src), url='cdep.ru', pages=0, q=[], general=True, year=int(year), note=''); stat['эмпир'] += 1
    save()
    import collections
    print(code, stat, 'в базе:', dict(collections.Counter(m['cat'] for m in man.values())), 'макс. имя, байт:', max([len(os.path.basename(m['dst']).encode()) for m in man.values()] or [0]))
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in DISC] or list(DISC): run(code)
