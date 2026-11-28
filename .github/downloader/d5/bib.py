# -*- coding: utf-8 -*-
"""Библиографическое описание издания по первым страницам PDF (запись на обороте титульного листа:
«Название : вид издания / авторы. – Город : Издатель, год»)."""
import re
KIND = r'(?:учеб\.\s?[-–]?\s?(?:метод\.|практ\.|нагляд\.)?\s?пособие|учебн[а-яё-]*(?:\s*[-–]\s*[а-яё]+)?\s+(?:пособие|издание)|учебник|монография|курс лекций|лекци[яи]|практикум|сборник[^/]{0,90}|методическ[а-яё]+\s+[а-яё]+|справочн[а-яё]+(?:\s+пособие)?|словарь[^/]{0,30}|альбом[^/]{0,40}|хрестоматия|задачник|научно-практическ[а-яё]+\s+[а-яё]+|материалы[^/]{0,160}|рабочая тетрадь|памятка[^/]{0,40}|аналитическ[а-яё]+\s+[а-яё]+|комментарий[^/]{0,40}|наглядное пособие|пособие|алгоритм[а-яё]*|тезисы[^/]{0,60}|труды[^/]{0,60}|информационно[^/]{0,40}|электронн[а-яё]+ [^/]{0,60})'
PUBS = [('Академи[яи] управления', 'Академия управления МВД'), ('ДГСК|Департамент государственной службы', 'ДГСК МВД'), ('ВИПК|Домодедово|Всероссийск[а-я]+ институт[а-я]* повышения', 'ВИПК МВД'), ('ВНИИ', 'ВНИИ МВД'),
        ('Белгород|Бел ?ЮИ', 'БелЮИ МВД'), ('Ставрополь', 'Ставропольский филиал КрУ МВД'), ('Новороссийск', 'Новороссийский филиал КрУ МВД'), ('Симферополь|Крымск', 'Крымский филиал КрУ МВД'),
        ('Краснодар|КрУ', 'КрУ МВД'), ('Рязан', 'Рязанский филиал МосУ МВД'), ('Омск|ОмА', 'ОмА МВД'), ('Ор[её]л|Орловск|ОрЮИ', 'ОрЮИ МВД'), ('Барнаул|БЮИ', 'БЮИ МВД'), ('Уф[аи]|УЮИ', 'УЮИ МВД'),
        ('Казан|КЮИ', 'КЮИ МВД'), ('Иркутск|Восточно-Сибирск|ВСИ', 'ВСИ МВД'), ('Красноярск|Сибирск|СибЮИ', 'СибЮИ МВД'), ('Воронеж', 'ВИ МВД'), ('Волгоград', 'ВА МВД'),
        ('Калининград', 'Калининградский филиал СПбУ МВД'), ('Санкт-Петербург|СПб', 'СПбУ МВД'), ('Ростов|РЮИ', 'РЮИ МВД'), ('Нижн|Нижегород|НА МВД', 'НА МВД'), ('Хабаровск|Дальневосточн|ДВЮИ', 'ДВЮИ МВД'),
        ('Тюмен|ТИПК', 'ТИПК МВД'), ('Екатеринбург|Уральск|УрЮИ', 'УрЮИ МВД'), ('Москва|Московск|М\\.|Кикот', 'МосУ МВД')]
def pub_short(city, pub):
    s = pub + ' | ' + city
    for rx, name in PUBS:
        if re.search(rx, pub): return name
    for rx, name in PUBS:
        if re.search(rx, city): return name
    return ' '.join(pub.split())[:60]
def people(resp):
    resp = resp.replace('\xa0', ' ')
    role = ''
    if re.search(r'под (общ\. |общей )?ред', resp, re.I): role = 'ред. '
    elif re.search(r'\b(сост|авт\.-сост)', resp, re.I): role = 'сост. '
    names = re.findall(r'(?:[А-ЯЁ]\.\s?){1,2}\s?([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)', resp)
    names = list(dict.fromkeys(names))
    etal = bool(re.search(r'и др', resp))
    if not names: return ''
    if role:
        def nom(x):
            if x.endswith('ого'): return x[:-3] + 'ий'
            if x.endswith('ой'): return x[:-2] + 'а'
            if re.search(r'(ов|ев|ёв|ин|ын|[бвгджзклмнпрстфхцчшщ])а$', x) and not x.endswith(('ова', 'ева', 'ина', 'ына')) or re.search(r'(ов|ев|ёв|ин|ын)а$', x): return x[:-1]
            return x
        names = [nom(x) for x in names]
    if role: return role + ', '.join(names[:2]) + (' и др.' if len(names) > 2 else '')
    if len(names) >= 3 or etal: return names[0] + ' и др.'
    return ', '.join(names)
def _kind(k):
    k = ' '.join(k.split()).lower().strip(' .')
    k = re.sub(r'^учеб\.\s?[-–]?\s?метод\.\s?пособие', 'учебно-методическое пособие', k); k = re.sub(r'^учеб\.\s?[-–]?\s?практ\.\s?пособие', 'учебно-практическое пособие', k)
    k = re.sub(r'^учеб\.\s?[-–]?\s?нагляд\.\s?пособие', 'учебное наглядное пособие', k); k = re.sub(r'^учеб\.\s?пособие', 'учебное пособие', k)
    for a, b in (('учебнометод', 'учебно-метод'), ('учебнопракт', 'учебно-практ'), ('научнопракт', 'научно-практ'), ('учебнонагляд', 'учебно-нагляд'), ('учебно -', 'учебно-'), ('учебно- ', 'учебно-'), ('научно- ', 'научно-')):
        k = k.replace(a, b)
    return k
def _title(head):
    cut = 0
    for mm in re.finditer(r'(?:^|\s)[А-ЯЁA-Z]\s?[-–]?\s?\d{2,3}\s+(?=[А-ЯЁ«"A-Z\d])|ISBN[\s\d–-]+[\dXХ]\s', head):
        cut = max(cut, mm.end())
    title = re.sub(r'^.*©[^,]{3,80},\s*\d{4}\s+', '', head[cut:]).strip(' .–—-')
    if len(title) > 230 or re.search(r'ецензент|УДК|ББК|кандидат|доктор|профессор|доцент|кафедр|обсужден|одобрен|совет', title):
        parts = re.split(r'(?<=[а-яё\)»\d])[.;]\s+(?=[А-ЯЁ«])', title)
        title = parts[-1].strip(' .–—-')
    for rx in (r'[А-ЯЁ][а-яё-]+,\s(?:[А-ЯЁ]\.\s?){1,2}\s*(?=[А-ЯЁ«\d])', r'[А-ЯЁ][а-яё-]+\s(?:[А-ЯЁ]\.\s?){2}\s*(?=[А-ЯЁ«\d])', r'имени\s(?:[А-ЯЁ]\.\s?){1,2}\s?[А-ЯЁ][а-яё]+\s+', r'\(глав[^)]*\)\s*'):
        mm = list(re.finditer(rx, title))
        if mm: title = title[mm[-1].end():].strip()
    return title.strip(' .–—-')
def describe(text):
    """text — текст первых страниц. -> dict(authors, title, kind, pub, year) или None."""
    t = re.sub(r'[\xad\u2010\u2011]\s*', '', text)
    t = re.sub(r'(?<=[а-яё])-\n(?=[а-яё])', '', t)
    flat = re.sub(r'\s+', ' ', t)
    tail = r'\s*[–—-]\s*([А-ЯЁ][А-Яа-яёЁ. -]{1,30}?)\s?:\s*([^:]{3,160}?),\s*((?:19|20)\d\d)\b'
    for m in re.finditer(r'\s?:\s?(' + KIND + r')\s*/\s*(.{3,500}?)' + tail, flat, re.I):
        title = _title(flat[max(0, m.start() - 420):m.start()])
        if len(title) < 6 or len(title) > 260: continue
        return dict(title=title, kind=_kind(m.group(1)), authors=people(m.group(2)), pub=pub_short(m.group(3), m.group(4)), year=m.group(5), how='запись')
    for m in re.finditer(r'\s?[:.]\s?(' + KIND + r')\s?\.?' + tail, flat, re.I):
        head = flat[max(0, m.start() - 420):m.start()]
        title = _title(head)
        if len(title) < 6 or len(title) > 260: continue
        am = re.findall(r'([А-ЯЁ][а-яё-]+),?\s(?:[А-ЯЁ]\.\s?){1,2}', head[:max(0, len(head) - len(title))][-120:])
        return dict(title=title, kind=_kind(m.group(1)), authors=', '.join(am[:1]), pub=pub_short(m.group(2), m.group(3)), year=m.group(4), how='запись без авторов')
    for m in re.finditer(r'\s/\s*((?:[А-ЯЁ]\.\s?){1,2}\s?[А-ЯЁ][а-яё]+.{0,300}?|под .{3,200}?|сост.{3,200}?)' + tail, flat):
        title = _title(flat[max(0, m.start() - 420):m.start()])
        k = re.search(r'\s?:\s?([а-яё][а-яё -]{4,60})$', title)
        kind = _kind(k.group(1)) if k else 'издание'
        if k: title = title[:k.start()].strip()
        if len(title) < 6 or len(title) > 260: continue
        return dict(title=title, kind=kind, authors=people(m.group(1)), pub=pub_short(m.group(2), m.group(3)), year=m.group(4), how='запись (вид не распознан)')
    return None
def title_page(path):
    """Запасной способ: название — самые крупные строки титульного листа; вид и издатель — по словам на первых страницах."""
    import fitz
    doc = fitz.open(path); res = None
    for pno in range(min(3, doc.page_count)):
        spans = []
        for b in doc[pno].get_text('dict')['blocks']:
            for l in b.get('lines', []):
                txt = ' '.join(sp['text'] for sp in l['spans']).strip()
                if txt and l['spans']: spans.append((max(sp['size'] for sp in l['spans']), txt))
        letters = sum(len(x[1]) for x in spans)
        if letters < 60: continue
        big = max(sz for sz, x in spans if len(re.findall('[А-Яа-яЁё]', x)) >= 4) if any(len(re.findall('[А-Яа-яЁё]', x)) >= 4 for sz, x in spans) else 0
        lines = [x for sz, x in spans if sz >= big - 0.6 and len(re.findall('[А-Яа-яЁё]', x)) >= 3]
        title = ' '.join(' '.join(lines).split())
        if 8 <= len(title) <= 260:
            page = ' '.join(x for _, x in spans)
            names = list(dict.fromkeys(re.findall(r'(?:[А-ЯЁ]\.\s?){1,2}\s?([А-ЯЁ][а-яё]{2,})', page)))
            two = ' '.join(doc[i].get_text() for i in range(min(4, doc.page_count)))
            k = re.search(KIND, re.sub(r'\s+', ' ', two), re.I)
            pub = ''
            for rx, name in PUBS[:-1]:
                if re.search(rx, two): pub = name; break
            y = re.findall(r'\b(20[012]\d)\b', page)
            res = dict(title=title, kind=_kind(k.group(0)) if k else 'издание', authors=(names[0] + ' и др.' if len(names) >= 3 else ', '.join(names)), pub=pub, year=y[-1] if y else '', how='титульный лист')
            break
    doc.close()
    return res
def first_pages(path, n=5):
    import fitz
    doc = fitz.open(path); out = []
    for i in range(min(n, doc.page_count)): out.append(doc[i].get_text())
    pages = doc.page_count; doc.close()
    return '\n'.join(out), pages

def suspicious(d):
    t = d['title']
    return (d['how'] != 'запись' or len(t) > 170 or t[:1].islower() or bool(re.search(r'ецензент|ечатается|кафедр|\(глав|УДК|ББК|ISBN|доцент|профессор|полковник', t)) or not d['pub'] or not d['year'])
