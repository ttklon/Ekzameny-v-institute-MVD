# -*- coding: utf-8 -*-
"""Этап 3: раскладка отобранных изданий (sel.json) по папкам «3. Учебная литература» двух дисциплин,
описание новых изданий по титульному листу, проверка года издания по тексту файла, реестр и контрольные суммы."""
import os, re, sys, json, glob, hashlib, shutil, collections
HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.dirname(HERE); ROOT = os.path.dirname(os.path.dirname(DL))
sys.path.insert(0, os.path.join(DL, 'd5'))
import fitz, bib
import lit
from lit import DISC, LIT, TODAY, UCH, dehyph, cls
STAGE = os.path.join(ROOT, '.work', 'lit3')
MAN = os.path.join(HERE, 'manifest_lit3.json')
SUB = {2: '1. Профильные издания', 1: '2. Смежные издания'}
ABBR = 'МВД ОВД РФ КоАП УК УПК ГИБДД ДПС ДТП ОРД ОРМ ГАИ БДД ПДД ТС КЮИ СМИ ЭВМ IT KIA'.split()
PROPER = {'россии': 'России', 'российской федерации': 'Российской Федерации', 'российской': 'Российской', 'федерации': 'Федерации', 'госавтоинспекции': 'Госавтоинспекции',
          'госавтоинспекция': 'Госавтоинспекция', 'интернет': 'Интернет', 'кодекса': 'Кодекса', 'кодексом': 'Кодексом', 'республики казахстан': 'Республики Казахстан'}

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def sentence(t):
    t = ' '.join(t.split())
    letters = re.findall('[А-Яа-яЁё]', t)
    if not letters or sum(1 for c in letters if c.isupper()) < 0.6 * len(letters): return t
    out = []
    for w in t.split():
        core = re.sub(r'[^А-Яа-яЁёA-Za-z]', '', w)
        out.append(w if core in ABBR else w.lower())
    s = ' '.join(out); s = s[:1].upper() + s[1:]
    for a, b in PROPER.items(): s = re.sub(r'\b%s\b' % a, b, s)
    return s
def tclean(t):
    t = ' '.join(dehyph(t).split()).strip(' .«»"')
    t = re.sub(r'\s*\[Электронный ресурс\]', '', t)
    t = re.sub(r'^[А-ЯЁ]\s?-?\s?\d{1,3}\s+(к\s+)?', '', t)
    t = re.sub(r'^[А-ЯЁ][а-яё-]+,\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\.?\s+', '', t)
    t = re.sub(r'^(?:(?:[А-ЯЁ]\.\s?){1,2}\s?[А-ЯЁ][а-яё-]+,?\s+)+(?=[А-ЯЁ«])', '', t)
    t = re.sub(r'\s*:\s*(учебн\w+[- ]?\w*\s*пособие|учебник|практикум|методические рекомендации|курс лекций).*$', '', t, flags=re.I)
    t = re.sub(r'\s+(Учебн\w+(-\w+)? пособие|Учебник|Методические (рекомендации|материалы)|Курс лекций|Практикум|Научно-практическ\w+ комментарий).*$', '', t)
    return sentence(t).strip(' .«»"')
BAD = r'МИНИСТЕРСТВО|ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ|ISBN|УДК|Печатается|Рецензент|редакционно-издательск|[Рр]екомендовано|©|[Оо]добрено|кафедр|Уважаемые|Учреждение образования|^Академия|^Министерство'
def good(d): return bool(d) and 6 <= len(d['title']) <= 260 and not re.search(BAD, d['title'])
def describe(path, e):
    text, pages = bib.first_pages(path, 6)
    flat = ' '.join(text.split())
    d = None; how = ''
    try: d = bib.describe(text)
    except Exception: d = None
    if d and not bib.suspicious(d): d = dict(d); d['title'] = tclean(d['title'])
    else: d = None
    if not good(d):
        try:
            d = bib.title_page(path)
            if d: d = dict(d); d['title'] = tclean(d['title'])
        except Exception: d = None
        if not good(d) or re.search(r'[а-яё] [А-ЯЁ]\.\s?[А-ЯЁ]\.', d['title']): d = None
    ys = [int(y) for y in re.findall(r'(?<!\d)(20[012]\d)(?!\d)', flat[:3500]) if int(y) <= 2026]
    if d:
        kind = dehyph(d.get('kind') or '')
        if kind in ('издание', 'электронное издание', ''): kind = e['kind'] if e['kind'] in UCH else ''
        for name, rx in lit.KINDS:
            if re.search(rx, kind, re.I): kind = name; break
        au = d.get('authors') or ''
        if au in ('Кикотя', 'Путилина'): au = ''
        r = dict(title=d['title'], kind=kind, authors=au, pub=d.get('pub') or '', year=int(d.get('year') or 0) or (max(ys) if ys else 0), how=d['how'])
    else:
        t = tclean(e['title'])
        pub = ''
        for rx, name in bib.PUBS[:-1]:
            if re.search(rx, flat[:1500]): pub = name; break
        r = dict(title=t if not re.search(BAD, t) else sentence(e['short']), kind=e['kind'], authors='', pub=pub, year=max(ys) if ys else 0, how='первые страницы (запись об издании не распознана)')
    r['pages'] = pages
    r['textlayer'] = len(flat) > 300
    r['dsp'] = bool(re.search(r'служебного\s+пользования|\bДСП\b|[Сс]екретно\b', ' '.join(text.split())[:2500]))
    r['years_seen'] = sorted(set(ys))
    return r
def clean(s):
    for a, b in ((':', ' —'), ('?', ''), ('"', ''), ('/', '-'), ('\\', '-'), ('*', ''), ('|', '-'), ('<', ''), ('>', ''), ('«', ''), ('»', '')): s = s.replace(a, b)
    return ' '.join(s.split()).strip(' .')
def cut(title, room):
    title = clean(title)
    if len(title) <= room: return title
    out = []
    for x in title.split():
        if len(' '.join(out + [x])) + 1 > room and len(out) >= 3: break
        out.append(x)
    while len(out) > 3 and out[-1].lower().strip(',;—-') in ('и', 'в', 'на', 'по', 'с', 'к', 'о', 'об', 'при', 'за', 'для', 'как', 'от', 'из', 'их', 'а', 'или', 'не', '—', '-', 'со'): out.pop()
    return ' '.join(out).rstrip(',;—- ') + '…'
def make_name(r, taken):
    kind = r['kind'][:1].upper() + r['kind'][1:] if r['kind'] else ''
    tail = '. '.join(x for x in [kind, ', '.join(x for x in [r['pub'], str(r['year']) if r['year'] else ''] if x)] if x)
    au = clean(r['authors'])
    room = 110
    while True:
        name = '. '.join(x for x in [au, cut(r['title'], room), tail] if x) + '.pdf'
        if len(name.encode('utf-8')) <= 230 or room < 30: break
        room -= 8
    base, i = name, 2
    while name.lower() in taken:
        name = base[:-4] + ' (%d).pdf' % i; i += 1
    taken.add(name.lower()); return name

# ---------- правки после просмотра описаний глазами (титульный лист каждого издания сверен по тексту файла) ----------
FIX = {
 'b5b0b6d': dict(authors='Новикова', title='Предупреждение коррупции в органах внутренних дел и формирование антикоррупционного поведения среди сотрудников и работников органов внутренних дел'),
 'b13f581': dict(authors='Новикова, Шевцова'),
 'b03a936': dict(authors='Полякова, Можаева', title='Государственная служба в органах внутренних дел'),
 'be64883': dict(authors='Прокудин'), 'b036fc2': dict(authors='Прокудин'),
 'b5959eb': dict(authors='Абдулганеев, Кузнецов'),
 'b2de812': dict(authors='Полякова, Семенихина'), 'baf4dc0': dict(authors='Полякова, Красноруцкая'),
 'b452d84': dict(authors='Рябчиков', kind='научно-практическое пособие'),
 'bcf3f3b': dict(authors='Плотникова'), 'bf90abb': dict(authors='Плотникова'),
 'b0197eb': dict(authors='Кулакова, Лазарев'),
 'bde5ec7': dict(authors='Еникеева, Рябцева'),
 'b6f6dde': dict(authors='Белоусова'), 'b12f352': dict(authors='Белоусова'), 'bafd8d8': dict(authors='Белоусова, Шевцова'),
 'ba50f63': dict(authors='Комлев', title='Кейс-стади в психологии конфликта'),
 'bf6d8af': dict(authors='Лисихина и др.', pub='СибЮИ МВД'),
 'bb97b33': dict(authors='Халметов и др.', pub='КЮИ МВД'),
 'b0ffaa0': dict(pub='СФ КрУ МВД', authors='сост. Ефимов, Трусов', title='Разработка научно обоснованных условий допуска к участию в дорожном движении пользователей электросамокатов, моноколёс и иных средств индивидуальной мобильности'),
 'b8696f5': dict(authors='Алиуллов и др.', title='Особенности реализации прав и обязанностей сотрудников дежурной части территориального органа МВД России после доставления лиц, находящихся в состоянии опьянения'),
 'bc8f5f5': dict(authors='Кузнецова, Шелковникова', pub='НЦ БДД МВД', kind='методические материалы'),
 'b20f917': dict(authors='Амелин и др.', pub='НЦ БДД МВД', title='Практический экзамен на право управления транспортными средствами категории В'),
 'b1b5a64': dict(authors='Баканов и др.', pub='НЦ БДД МВД', title='Зарубежный опыт противодействия основным факторам риска в дорожном движении'),
 'b50fe75': dict(authors='Барышников и др.', pub='ЭКЦ МВД'),
 'b74041e': dict(authors='', title='Административное право', kind='учебник', pub='СПбУ МВД'),
 'b8d7b51': dict(authors='Валькова и др.', title='Предварительное расследование в органах внутренних дел', kind='учебное пособие', pub='СПбУ МВД'),
 'b823b90': dict(authors='Рунаев и др.', title='Профессиональная мораль и профессиональная этика сотрудников органов внутренних дел', pub='ВА МВД'),
 'b074887': dict(authors='Вологина и др.', title='Правоохранительные органы — задачи и тестовые задания', kind='практикум', pub='ВА МВД'),
 'bf96df0': dict(authors='Искалиев и др.', kind='учебно-методическое пособие', pub='Академия управления МВД',
                 title='Организация межведомственного взаимодействия подразделений экономической безопасности и противодействия коррупции системы МВД России в сфере противодействия преступлениям, совершаемым с использованием информационно-телекоммуникационных технологий'),
 'bebb4c3': dict(authors='Гречаный и др.', pub='ВИ МВД', title='Разработка подходов к использованию информационных технологий для совершенствования организации взаимодействия дежурных частей различных федеральных органов исполнительной власти'),
 'b46e094': dict(authors='Яблонский, Харитонов', title='Проблемы типологизации государственной службы и государственных служащих в Российской Федерации', kind='учебное пособие', pub='КрУ МВД'),
 'b365209': dict(authors='Колосович', title='Нормативная регламентация и порядок противодействия коррупционным правонарушениям в органах внутренних дел', pub='ВА МВД'),
 'b91682f': dict(authors='Колосович', title='Предупреждение коррупции в органах внутренних дел и формирование антикоррупционного поведения сотрудников и работников органов внутренних дел', kind='курс лекций', pub='ВА МВД'),
 'b0f6731': dict(authors='Кириченко и др.', pub='Университетская книга (Курск)'),
 'b290ea5': dict(authors='Кириченко и др.', pub='Университетская книга (Курск)'),
 'b7964e3': dict(authors='Курбатова, Сакулина', pub='МосУ МВД'),
 'be891ec': dict(authors='Авдеев', title='Процессуальные аспекты производства следственных действий в ходе проверки сообщений о преступлениях', kind='научно-практическое пособие', pub='Калининградский филиал СПбУ МВД'),
 'babc131': dict(authors='Несмеянов и др.'),
 'b5af4b1': dict(authors='Евтихов и др.'),
 'b2b2892': dict(authors='Иващенко, Кучмезов', title='Техника выполнения сотрудниками полиции наиболее эффективных приёмов сковывания наручниками, связывания и наружного досмотра', pub='РЮИ МВД'),
 'b772370': dict(authors='Вакуленко, Морозов', title='Криминология', pub='РЮИ МВД'),
 'b7bdf82': dict(pub='РЮИ МВД'), 'b185ed5': dict(pub='РЮИ МВД'), 'b32cc33': dict(pub='РЮИ МВД'),
 'b08d543': dict(pub='РЮИ МВД', title='Нравственно-этические основы службы в органах внутренних дел Российской Федерации'),
 'b91dee1': dict(title='Психология служебной деятельности в особых условиях'),
 'bb10385': dict(pub='Москва — Ростов-на-Дону', title='Профилактика восприятия деструктивной информации, распространяемой с использованием сети Интернет'),
 'bd8f978': dict(pub='Москва — Ростов-на-Дону', title='Организация индивидуальной профилактической работы с лицами, подверженными идеологическому воздействию деструктивных течений'),
}
# уровень отношения к дисциплине, изменённый после просмотра: (G, S); None — не менять
LEVEL = {'e8a80cc': (1, None), 'e2e7be5': (1, None), 'ec6beac': (0, None), 'e91b64e': (1, None), 'bd746e2': (1, None), 'be50178': (1, None),
         'bd8f978': (None, 1), 'bb10385': (None, 1), 'bff689a': (None, 1), 'e69dac4': (None, 1), 'b5af4b1': (0, 1), 'bf96df0': (None, 1), 'b46e094': (None, 1), 'b439f54': (None, 1), 'b996d3c': (None, 1), 'b7726aa': (1, None), 'e112c22': (None, 1), 'bac5e43': (1, None)}
DROP_N = {
 'b1849d2': 'методические рекомендации о заявлениях по преступлениям в сфере ЖКХ — к дисциплинам не относятся; на первой странице сопроводительное письмо',
 'bb06f7c': 'издание Академии МВД Республики Беларусь — белорусское законодательство',
 'b74041e': 'дубль: учебник «Административное право» (ред. Каплунов), СПбУ МВД, 2024 уже взят из базы другой дисциплины',
}
DROP_T = [(r'Стрелковое огнестрельное оружие', 'судебная баллистика — к дисциплинам не относится')]
def title_fix(t):
    t = re.sub(r'дорожнотранспортн', 'дорожно-транспортн', t)
    t = re.sub(r'информационнотелекоммуникац', 'информационно-телекоммуникац', t)
    t = re.sub(r'(?<!категории) В (?=[а-яё])', ' в ', t)
    t = re.sub(r'^(?:[А-ЯЁ][а-яё-]+ [А-ЯЁ]\.\s?[А-ЯЁ]\.\s+)+', '', t)
    return t
def authors_fix(a):
    m = re.match(r'^((?:ред|сост)\. )?(.*)$', a); pre, rest = m.group(1) or '', m.group(2)
    tail = ' и др.' if rest.endswith(' и др.') else ''
    names = [x.strip() for x in rest[:len(rest) - len(tail)].split(',') if x.strip()]
    seen = []
    for x in names:
        if x not in seen: seen.append(x)
    return pre + ', '.join(seen) + tail
def review(man, rej, st):
    """Ручные правки, исключения и снятие дублей; имена файлов новых изданий пересчитываются."""
    out = []; seen = {}
    for m in man:
        if m['n'] in DROP_N: rej.append((m, DROP_N[m['n']])); st['исключено при просмотре'] += 1; continue
        why = next((w for rx, w in DROP_T if re.search(rx, m['title'])), None)
        if why: rej.append((m, why)); st['исключено при просмотре'] += 1; continue
        if m['n'][0] == 'b':
            f = FIX.get(m['n'], {})
            for k, v in f.items(): m[k] = v
            m['title'] = title_fix(m['title']); m['authors'] = authors_fix(m['authors'] or '')
            if f: m['how'] = 'титульный лист и запись об издании, сверено вручную'
        if m['n'] in LEVEL:
            g, s = LEVEL[m['n']]
            if g is not None: m['g'] = g
            if s is not None: m['s'] = s
            if not m['g'] and not m['s']: rej.append((m, 'при просмотре признано не относящимся к дисциплинам')); st['исключено при просмотре'] += 1; continue
        p = stage_file(m['n']) if m['n'][0] == 'b' else os.path.join(ROOT, m['src'])
        if 'sha' not in m: m['sha'] = sha(p)
        key2 = (re.sub(r'[^а-яёa-z0-9]', '', m['title'].lower().replace('ё', 'е')), str(m['year']), m['pages'])
        dup = seen.get(m['sha']) or seen.get(key2)
        if dup:
            dup['g'] = max(dup['g'], m['g']); dup['s'] = max(dup['s'], m['s'])
            rej.append((m, 'дубль издания «%s»' % dup['name'][:80])); st['дубли сняты'] += 1; continue
        seen[m['sha']] = m; seen[key2] = m
        out.append(m)
    taken = {m['name'].lower() for m in out if m['n'][0] == 'e'}
    for m in out:
        if m['n'][0] == 'b': m['name'] = make_name(m, taken)
    return out

TMP = '/tmp/lit3-stage'
def stage_file(n):
    """Загруженный файл берётся прямо из хранилища git (каталог .work/lit3 в рабочее дерево не выгружается — мало места на диске)."""
    import subprocess
    p = os.path.join(STAGE, n + '.pdf')
    if os.path.exists(p): return p
    os.makedirs(TMP, exist_ok=True); t = os.path.join(TMP, n + '.pdf')
    if os.path.exists(t) and os.path.getsize(t) > 0: return t
    for rev in ('HEAD', 'r46-downloads'):
        with open(t, 'wb') as f:
            r = subprocess.run(['git', '-C', ROOT, 'cat-file', 'blob', '%s:.work/lit3/%s.pdf' % (rev, n)], stdout=f, stderr=subprocess.DEVNULL)
        if r.returncode == 0 and os.path.getsize(t) > 0: return t
    os.remove(t); return None
def run():
    rp = os.path.join(HERE, 'rejected.tsv')
    prev = [l for l in open(rp, encoding='utf-8').read().split('\n') if l and not l.startswith('#') and 'не загружен' not in l] if os.path.exists(rp) else []
    sel = json.load(open(os.path.join(HERE, 'sel.json'), encoding='utf-8'))
    old = {m['n']: m for m in (json.load(open(MAN, encoding='utf-8')) if os.path.exists(MAN) else [])}
    man = []; rej = []; st = collections.Counter(); taken = {m['name'].lower() for m in old.values()}
    for e in sel:
        if e['n'] in old: man.append(old[e['n']]); continue
        if e['n'][0] == 'e':
            src = os.path.join(ROOT, e['src'])
            m = dict(n=e['n'], url=e['url'], origin=e['origin'], title=e['title'], kind=e['kind'], authors=e['authors'], pub=e['pub'], year=e['year'], pages=e['pages'],
                     size=e['size'], g=e['g'], s=e['s'], name=e['name'], how='описание взято из базы другой дисциплины', src=e['src'])
            try:
                doc = fitz.open(src); m['pages'] = doc.page_count
                flat = ' '.join(' '.join(doc[i].get_text() for i in range(min(6, doc.page_count))).split()); doc.close()
                m['year_seen'] = str(e['year']) in flat[:6000]
            except Exception as x:
                rej.append((e, 'файл не открывается: %s' % str(x)[:50])); st['имеющиеся: не открылись'] += 1; continue
            if m['name'].lower() in taken: m['name'] = m['name'][:-4] + ' (2).pdf'
            taken.add(m['name'].lower())
        else:
            src = stage_file(e['n'])
            if not src: rej.append((e, 'файл не загружен')); st['новые: не загружены'] += 1; continue
            try: r = describe(src, e)
            except Exception as x:
                rej.append((e, 'файл не открывается: %s' % str(x)[:50])); st['новые: не открылись'] += 1; continue
            if r['dsp']: rej.append((e, 'на первых страницах пометка об ограничении доступа')); st['новые: ограничение доступа'] += 1; continue
            if not r['textlayer']: rej.append((e, 'нет текстового слоя')); st['новые: нет текста'] += 1; continue
            if not r['year'] or r['year'] < 2023: rej.append((e, 'год издания по тексту файла — %s' % (r['year'] or 'не найден'))); st['новые: год старше 2023 или не найден'] += 1; continue
            g, s = cls(r['title'] + ' | ' + e['short'])
            g, s = max(g, e['g']) if g else (e['g'] if not r['how'].startswith('запись') else 0), max(s, e['s']) if s else (e['s'] if not r['how'].startswith('запись') else 0)
            if not g and not s: rej.append((e, 'по уточнённому названию не относится к дисциплинам: «%s»' % r['title'][:90])); st['новые: не относятся по уточнённому названию'] += 1; continue
            m = dict(n=e['n'], url=e['url'], origin='электронная библиотека lib.eioskuimvd.ru', title=r['title'], kind=r['kind'], authors=r['authors'], pub=r['pub'], year=r['year'],
                     pages=r['pages'], size=os.path.getsize(src), g=g, s=s, how=r['how'], year_seen=True, src='.work/lit3/%s.pdf' % e['n'], years_seen=r['years_seen'])
            m['name'] = make_name(r, taken)
        man.append(m); st['описано: ' + ('из базы' if e['n'][0] == 'e' else 'новое')] += 1
    man = review(man, rej, st)
    json.dump(man, open(MAN, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    with open(os.path.join(HERE, 'rejected.tsv'), 'w', encoding='utf-8') as f:
        lines = list(prev)
        for e, why in rej:
            l = '\t'.join((why, e['title'][:160], e.get('url') or e.get('src', '')))
            if l not in lines: lines.append(l)
        f.write('# отобранные издания, не попавшие в базу после проверки файла\n# причина\tназвание\tадрес\n' + '\n'.join(lines) + '\n')
    # раскладка
    for d, key in (('G', 'g'), ('S', 's')):
        base = os.path.join(ROOT, DISC[d], LIT)
        want = {}
        for m in man:
            if m[key]: want[os.path.join(SUB[m[key]], m['name'])] = m
        for dp, dn, fn in os.walk(base):
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), base)
                if f.endswith('.pdf') and rel not in want: os.remove(os.path.join(dp, f)); st[d + ': убрано лишних'] += 1
        for rel, m in want.items():
            dst = os.path.join(base, rel)
            if os.path.exists(dst) and os.path.getsize(dst) == m['size']: continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            src = stage_file(m['n']) if m['n'][0] == 'b' else os.path.join(ROOT, m['src'])
            if os.path.exists(dst): os.remove(dst)
            try: os.link(src, dst)          # жёсткая ссылка: одинаковые файлы не занимают место на диске дважды
            except OSError: shutil.copy2(src, dst)
            st[d + ': разложено'] += 1
        st[d + ': всего'] = len(want); st[d + ': профильных'] = sum(1 for m in want.values() if m[key] == 2)
        st[d + ': МБ'] = round(sum(m['size'] for m in want.values()) / 1e6)
    for k, v in sorted(st.items()): print('  %s: %s' % (k, v))
    return man

# ---------- разделы перечня вопросов ----------
PARTS = {
 'G': [('01', 'Госавтоинспекция в системе обеспечения безопасности дорожного движения', r'Госавтоинспекц|ГИБДД|инспекци\w+ безопасности|государственн\w+ контрол|зарубежн\w+ опыт|портфель'),
       ('02', 'Организация дорожно-патрульной службы', r'дорожно-патрульн|\bДПС\b|наряд'),
       ('03', 'Надзор за дорожным движением: наблюдение, регулирование, остановка, проверка', r'надзор|досмотр|остановк|контрольно-надзорн'),
       ('04', 'Производство по делам об административных правонарушениях', r'производств\w+ по делам|административн\w+ (юрисдикц|процесс)|административно-процессуальн|юрисдикционн'),
       ('05', 'Меры обеспечения производства', r'мер\w* обеспечения|опьянени|освидетельств|задержан|доставлен|мер\w* (государственного |административного )?принужден'),
       ('06', 'Отдельные административные правонарушения', r'административн\w+ ответственност|квалификаци\w+ (отдельных )?(видов )?административн|состав\w+ административных|нарушени\w+ правил дорожного|административно-деликтн'),
       ('07', 'Правила дорожного движения, требования к транспортным средствам и перевозкам', r'правил\w* дорожного движения|техническ\w+ состояни|управлени\w+ (транспортн|полноприводн)|подготовк\w+ водител|экзамен|самокат|индивидуальн\w+ мобильност|световых'),
       ('08', 'Дорожно-транспортные происшествия', r'дорожно-?\s?транспортн\w+ (происшеств|ситуаци|травматизм)|\bДТП|наезд|столкновени|перв\w+ помощ|следов (шин|транспорт)|следами транспорт'),
       ('09', 'Преступления в сфере дорожного движения и участие Госавтоинспекции в уголовном процессе', r'уголовн|преступлен|расследован|264|угон|дознани|экспертиз|экспертн|криминалистическ|осмотр\w* места|особенная часть'),
       ('10', 'Применение мер принуждения, личная безопасность и профессиональное общение', r'физическ\w+ сил|специальн\w+ средств|огнестрельн|личн\w+ безопасност|конфликт|общени|наручник|мер\w* (государственного )?принужден|перв\w+ помощ'),
       ('11', 'Организация дорожного движения и дорожный надзор', r'организаци\w+ дорожного движения|дорожн\w+ надзор|факторам риска'),
       ('12', 'Технический надзор, регистрационная и экзаменационная деятельность', r'техническ\w+ (надзор|осмотр|состояни)|регистрационн|идентификаци|маркировочн|экзамен|подготовк\w+ водител|допуск\w* к'),
       ('13', 'Исполнение административного законодательства, автоматическая фиксация, розыск', r'исполнени|автоматическ\w+ фиксац|розыск|угон|специальн\w+ учет'),
       ('14', 'Законодательство о безопасности дорожного движения', r'законодательств|правов\w+ (основ|регулирован)|административное право|зарубежн|сравнительн')],
 'S': [('01', 'Собственная безопасность органов внутренних дел: понятие, правовые основы, система', r'собственн\w+ безопасност|правоохранительн\w+ орган|организация полиции|государственн\w+ служб|управлен'),
       ('02', 'Предотвращение проникновения в органы внутренних дел лиц, преследующих противоправные цели', r'кадров|отбор|полиграф|профайлинг|прохождени\w+ службы|государственн\w+ служб|допуск'),
       ('03', 'Противодействие коррупции в органах внутренних дел', r'коррупц|взят|конфликт\w* интерес'),
       ('04', 'Оперативно-розыскная деятельность подразделений собственной безопасности', r'оперативно-р[оа]зыскн|\bОРД\b|\bОРМ\b|специальн\w+ техник'),
       ('05', 'Преступления и иные правонарушения сотрудников: квалификация', r'должностн|злоупотреблен|превышени|уголовн\w+ прав|квалификаци|ответственност\w+ сотрудник|коррупционн\w+ (преступ|правонаруш)|особенная часть|честь и достоинство'),
       ('06', 'Уголовно-процессуальные вопросы', r'уголовн\w+ процесс|уголовно-процессуальн|уголовном судопроизводстве|досудебн|возбужден|предварительн|дознани|следственн|доказ|задержан|процессуальн|результат\w+ (ОРД|оперативно)'),
       ('07', 'Служебная дисциплина, служебные проверки и ответственность сотрудников', r'служебн\w+ (дисциплин|провер)|дисциплинарн|ответственност\w+ сотрудник|увольнен|прохождени\w+ службы|государственн\w+ служб\w+ в'),
       ('08', 'Профилактика правонарушений и контроль за деятельностью сотрудников', r'профилактик|предупреждени|воспитательн|морально-психологическ|психологи|этик|нравственн|мораль|деструктивн|работ\w+ с личным составом|криминолог|прокурор|контрол'),
       ('09', 'Государственная защита сотрудников и обеспечение их безопасности', r'государственн\w+ защит|безопасност\w+ участников|личн\w+ безопасност|физическ\w+ сил|специальн\w+ средств|огнестрельн'),
       ('10', 'Защита информации и предотвращение утечки сведений', r'защит\w+ (конфиденциальной )?информац|информационн\w+ безопасност|кибербезопасност|государственн\w+ тайн|секретн|утечк|делопроизводств|деструктивн\w+ (контент|информац)'),
       ('11', 'Работа с обращениями граждан и взаимодействие с обществом', r'обращени\w+ граждан|общественн|средствами массовой информации|прав\w* человека|приему, регистрации'),
       ('12', 'Тактика действий и документальное оформление', r'документ|делопроизводств|процессуальн\w+ (документ|акт)|образцы|тактик|специальн\w+ техник')]}
GENERAL = {'G': r'^административн\w+ деятельность полиции|^административное право$|^административно-процессуальное право$|^основы административно-процессуального права',
           'S': r'^оперативно-розыскная деятельность|^правоохранительные органы|^уголовный процесс$|^уголовное право'}
def parts_of(d, m):
    t = m['title']
    p = [n for n, _, rx in PARTS[d] if re.search(rx, t, re.I)]
    return p
def mb(n): return ('%.1f МБ' % (n / 1e6)).replace('.', ',')
def why_short(w):
    if w.startswith('дубль'): return 'то же издание уже взято из базы другой дисциплины'
    if w.startswith('год издания'): return 'год издания по тексту файла старше 2023'
    if 'Беларусь' in w: return 'издание Республики Беларусь'
    if 'не относ' in w: return 'по содержанию не относится к дисциплинам'
    return re.sub(r' — .*|:.*', '', w)
def note(m):
    x = []
    if m['how'].startswith('первые страницы') or m['how'] == 'титульный лист': x.append('название и выходные данные взяты с титульного листа без записи об издании — сверить')
    elif 'сверено вручную' in m['how']: x.append('описание исправлено вручную по титульному листу')
    elif 'без авторов' in m['how'] or 'не распознан' in m['how']: x.append('запись об издании разобрана не полностью — сверить авторов и вид')
    if m.get('year_seen') is False: x.append('год %s в тексте первых страниц не найден — сверить' % m['year'])
    if m.get('textlayer') is False: x.append('нет текстового слоя')
    return '; '.join(x)
def registry():
    man = json.load(open(MAN, encoding='utf-8'))
    rej = [l.rstrip('\n').split('\t') for l in open(os.path.join(HERE, 'rejected.tsv'), encoding='utf-8') if not l.startswith('#')]
    skipped = [l.rstrip('\n').split('\t') for l in open(os.path.join(HERE, 'skipped.tsv'), encoding='utf-8') if not l.startswith('#')]
    nxt = [l.rstrip('\n').split('\t') for l in open(os.path.join(HERE, 'next_stages.tsv'), encoding='utf-8') if not l.startswith('#')]
    for d, key in (('G', 'g'), ('S', 's')):
        mine = sorted([m for m in man if m[key]], key=lambda m: (-m[key], m['name'].lower()))
        base = os.path.join(ROOT, DISC[d], LIT)
        missing = [m for m in mine if not os.path.exists(os.path.join(base, SUB[m[key]], m['name']))]
        if missing: print('НЕТ ФАЙЛОВ:', d, [m['name'][:50] for m in missing])
        prof = [m for m in mine if m[key] == 2]; rel = [m for m in mine if m[key] == 1]
        years = collections.Counter(m['year'] for m in mine)
        fromlib = sum(1 for m in mine if m['n'][0] == 'b')
        kinds = collections.Counter(m['kind'] or 'вид не определён' for m in mine)
        out = ['<!-- LIT-BEGIN -->', '## Учебная литература (этап 3 сбора источников)', '']
        out.append('Состояние на %s. В папке `3. Учебная литература` — **%d изданий %d–%d годов** (%s): %d профильных (папка `%s`) и %d смежных (папка `%s`). По годам: %s. Издания старше 2023 года на этом этапе не брались.'
                   % (TODAY, len(mine), min(years), max(years), mb(sum(m['size'] for m in mine)), len(prof), SUB[2], len(rel), SUB[1], ', '.join('%d — %d' % (y, years[y]) for y in sorted(years))))
        out.append('')
        out.append('Профильные — издания, в названии которых прямо назван предмет дисциплины. Смежные — общие учебники и пособия по дисциплинам, на которые опираются вопросы перечня. '
                   'Отбор сделан по названию издания и, для новых изданий, по оглавлению; содержание изданий целиком не читалось. К каким разделам перечня относится издание, показано в файле `Литература по разделам перечня.md` в той же папке.')
        out.append('')
        out.append('Откуда взято: %d изданий загружено %s из открытых каталогов электронной библиотеки lib.eioskuimvd.ru (ссылка — в столбце «Источник»), %d скопировано из баз других дисциплин этого хранилища, куда они ранее были загружены из той же библиотеки. '
                   'Год издания у новых изданий проверен по тексту первых страниц файла: год в названии каталога библиотеки — это год поступления, и он расходился с годом издания.' % (fromlib, TODAY, len(mine) - fromlib))
        out.append('')
        out.append('По видам: ' + ', '.join('%s — %d' % (k, v) for k, v in kinds.most_common()) + '.')
        for title, lst, num in (('Профильные издания', prof, 1), ('Смежные издания', rel, 2)):
            out += ['', '### УЛ.%d. %s' % (num, title), '', '| Файл | Вид | Год | Стр. | Размер | Источник | Примечание |', '|---|---|---|---|---|---|---|']
            for m in lst:
                src = '[библиотека](%s)' % m['url'].replace(' ', '%20').replace('(', '%28').replace(')', '%29') if m.get('url', '').startswith('http') else ''
                if m['n'][0] == 'e': src = (src + '; ' if src else '') + m['origin'].replace('база дисциплины ', 'из базы ')
                out.append('| %s | %s | %s | %s | %s | %s | %s |' % (m['name'].replace('|', '-'), m['kind'], m['year'], m['pages'], mb(m['size']), src, note(m)))
        out += ['', '### УЛ.3. Чего в базе нет', '']
        out.append('- Издания старше 2023 года — не брались по условию этапа. В библиотеке просмотрено 1213 файлов из каталогов с пометкой 2023 года и новее и из раздела «Библиотека полицейского»; у 341 из них год издания по тексту оказался старше 2023.')
        out.append('- Издания с пометкой об ограничении доступа («для служебного пользования») — не брались: %d при просмотре и %d после загрузки. Среди них пособия о государственной тайне и режиме секретности.'
                   % (sum(1 for r in skipped if 'ограничени' in r[0]), sum(1 for r in rej if 'ограничени' in r[0])))
        out.append('- Научные и аналитические издания библиотеки 2023 года и новее (монографии, сборники конференций, журналы, обзоры) — %d изданий, относящихся к двум дисциплинам, были отложены и разобраны на этапах 4 и 5 (разделы «Научные материалы» и «Эмпирические материалы» ниже); список — `.github/downloader/books/next_stages.tsv`.' % len(nxt))
        out.append('- Учебники коммерческих издательств (Юрайт, Проспект, Норма, Юнити-Дана и другие) — в открытом доступе их нет, в базу не входят.')
        out.append('- Издания, которых нет в открытых каталогах lib.eioskuimvd.ru, — не искались: другие библиотеки вузов МВД России на этом этапе не просматривались.')
        if d == 'G':
            out.append('- Отдельных учебных изданий 2023 года и новее по автоматической фиксации нарушений, розыску транспортных средств, дорожному надзору, перевозкам тяжеловесных и опасных грузов, техническому осмотру в просмотренных каталогах не найдено.')
        else:
            out.append('- Отдельных учебных изданий 2023 года и новее именно по деятельности подразделений собственной безопасности, по служебной дисциплине и по государственной защите сотрудников в открытых каталогах почти нет: по служебным проверкам — одно издание, по государственной защите — одно.')
        nr = [r for r in rej if 'ограничени' not in r[0]]
        if nr:
            out.append('- Отобраны при просмотре, но не вошли после проверки файла — %d: %s. Список — `.github/downloader/books/rejected.tsv`.'
                       % (len(nr), '; '.join('%s — %d' % (k, v) for k, v in collections.Counter(why_short(r[0]) for r in nr).most_common())))
        out += ['', '### УЛ.4. Что проверить и какие оговорки нужны', '']
        out.append('- Относимость изданий определена по названию и оглавлению. Смежные издания (общие курсы административного права, уголовного права, уголовного процесса, криминологии, психологии) покрывают вопросы перечня только частично.')
        out.append('- Соответствие изданий действующему законодательству не проверялось: пособия 2023–2024 годов могут не учитывать изменения 2025–2026 годов — нормы сверять по файлам папки `1. Нормативные правовые акты`.')
        bad = [m for m in mine if 'сверить' in note(m)]; hand = sum(1 for m in mine if 'вручную' in m['how'])
        out.append('- Название, авторы, вид и издатель определены программно по записи об издании на обороте титульного листа. У %d изданий запись распознана не полностью или год в тексте не найден — они отмечены в столбце «Примечание».' % len(bad))
        out.append('- У изданий, скопированных из баз других дисциплин, описание взято из тех баз; год издания перепроверен поиском года в тексте первых шести страниц.')
        out.append('- Описание %d изданий исправлено вручную по тексту титульного листа: программа приняла за название строку с наименованием вуза или фамилии авторов.' % hand)
        out.append('- Повторы убирались по совпадению контрольной суммы файла либо названия, года и числа страниц; разные издания одного названия (разных вузов и лет) оставлены.')
        nolink = sum(1 for m in mine if not m.get('url', '').startswith('http'))
        if nolink: out.append('- У %d изданий, скопированных из баз других дисциплин, ссылка на источник в прежних базах не сохранена.' % nolink)
        out += ['', '<!-- LIT-END -->']
        rp = os.path.join(ROOT, DISC[d], '2. Источники', 'Реестр источников.md')
        txt = open(rp, encoding='utf-8').read()
        block = '\n'.join(out)
        if '<!-- LIT-BEGIN -->' in txt: txt = re.sub(r'<!-- LIT-BEGIN -->.*?<!-- LIT-END -->', lambda _: block, txt, flags=re.S)
        else: txt = txt.replace('<!-- SP-END -->', '<!-- SP-END -->\n\n' + block, 1)
        open(rp, 'w', encoding='utf-8').write(txt)
        # --- литература по разделам перечня
        o = ['# Литература по разделам перечня вопросов — ' + DISC[d], '',
             'Состояние на %s. Издания папки `3. Учебная литература` (%d, все 2023 года и новее) разнесены по разделам перечня вопросов по словам в названии. Одно издание может стоять в нескольких разделах. '
             'Привязка сделана к разделам, а не к отдельным вопросам, и по названию, а не по содержанию: перед ссылкой на издание в ответе нужную главу надо найти по оглавлению.' % (TODAY, len(mine)), '']
        used = set()
        gen = [m for m in mine if re.search(GENERAL[d], m['title'].lower())]
        for n, title, rx in PARTS[d]:
            lst = [m for m in mine if n in parts_of(d, m)]
            o += ['## Раздел %s. %s' % (n, title), '']
            if not lst: o += ['Изданий с этим предметом в названии нет — см. общие курсы в конце файла.', '']; continue
            for m in lst:
                used.add(m['n']); o.append('- %s`%s/%s`' % ('' if m[key] == 2 else '(смежное) ', SUB[m[key]], m['name']))
            o.append('')
        o += ['## Раздел %s. Судебная практика' % ('15' if d == 'G' else '13'), '', 'Учебные издания к этому разделу не подбирались: источник — акты папки `2. Судебная практика`.', '']
        o += ['## Общие курсы (ко всем разделам)', ''] + ['- `%s/%s`' % (SUB[m[key]], m['name']) for m in gen] + ['']
        rest = [m for m in mine if m['n'] not in used and m not in gen]
        if rest: o += ['## Издания, не отнесённые к разделам по названию', ''] + ['- `%s/%s`' % (SUB[m[key]], m['name']) for m in rest] + ['']
        open(os.path.join(base, 'Литература по разделам перечня.md'), 'w', encoding='utf-8').write('\n'.join(o))
        # --- контрольные суммы
        src = os.path.join(ROOT, DISC[d], '2. Источники'); sums = []
        for dp, dn, fn in os.walk(src):
            for f in fn:
                if f in ('Контрольные суммы SHA-256.txt', '.gitkeep'): continue
                full = os.path.join(dp, f); sums.append((os.path.relpath(full, src), sha(full)))
        sums.sort()
        open(os.path.join(src, 'Контрольные суммы SHA-256.txt'), 'w', encoding='utf-8').write(''.join('%s  %s\n' % (h, p) for p, h in sums))
        print('%s: изданий %d (профильных %d, смежных %d), %s; из библиотеки %d; с примечанием %d; без раздела %d; файлов в контрольных суммах %d'
              % (d, len(mine), len(prof), len(rel), mb(sum(m['size'] for m in mine)), fromlib, len(bad), len(rest), len(sums)))
