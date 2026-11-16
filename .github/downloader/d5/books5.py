# -*- coding: utf-8 -*-
"""Описание скачанных изданий библиотеки: .work/d5/<код>/lib/<номер>.pdf -> books_<код>.json.
Описание берётся с первых страниц PDF (bib.py) и сверяется с названием каталога библиотеки; запускать: /tmp/venv/bin/python books5.py [коды]."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
import bib, fitz
from sel_art import keys, stem
os.chdir(ROOT)
fitz.TOOLS.mupdf_display_errors(False)
GEN = {'upp': r'^(уголовн(ый|о-процессуальное) (процесс|право)|уголовно-процессуальное право|уголовный процесс)( российской федерации| россии| \(уголовный процесс\))?(\. (общая|особенная) часть)?(\. часть \d)?$|основы уголовного процесса',
       'up': r'^уголовное право( российской федерации| россии)?(\. (общая|особенная) часть)?(\. часть \d)?$|основы уголовного права|^(общая|особенная) часть уголовного права',
       'gpp': r'^граждански[йо] (процесс|процессуальное право)( российской федерации| россии)?$|^гражданское процессуальное право',
       'tp': r'^трудовое право( российской федерации| россии)?$',
       'tsp': r'^тактико-специальная подготовка( сотрудников (органов внутренних дел|полиции))?$|^тактико-специальная подготовка'}
COMP = set('уголовно научно учебно оперативно гражданско административно социально организационно тактико военно нормативно служебно частно публично следственно судебно экспертно информационно материально физико морально медико огневой профессионально историко теоретико общественно государственно финансово экономико политико практико методико психолого педагогико культурно воспитательно розыскно контрольно технико криминалистическо информационно-телекоммуникационно конституционно международно процессуально'.split())
KW = r'(?:учебн[а-яё]*[\s-]*(?:методическ[а-яё]+|практическ[а-яё]+|наглядн[а-яё]+)?\s*(?:пособие|издание)|учеб\.[\s-]*(?:метод\.|практ\.|нагляд\.)?\s*пособие|учебник|монография|курс лекций|практикум|сборник [а-яё ]+|хрестоматия|задачник|методическ[а-яё]+ рекомендаци[ия]|практическ[а-яё]+ пособие|научно-практическ[а-яё]+ (?:пособие|комментарий)|альбом схем|рабочая тетрадь|лекци[яи]|словарь|справочник|памятка|аналитическ[а-яё]+ обзор|материалы [а-яё\s-]+|тезисы [а-яё ]+|краткий курс|конспект лекций)'
def dehyph(t):
    def f(m):
        return m.group(1) + '-' + m.group(2) if m.group(1).lower() in COMP else m.group(1) + m.group(2)
    return re.sub(r'([А-Яа-яЁё]+)-\s+([а-яё]+)', f, t)
def tclean(t):
    """Убрать из начала названия авторский знак, фамилию из заголовка записи, инициалы."""
    t = ' '.join(t.split()).strip(' .«»"')
    t = re.sub(r'^[А-ЯЁ]\s?\d{1,3}\s+', '', t)
    t = re.sub(r'^[А-ЯЁ][а-яё-]+,\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\.\s+', '', t)
    t = re.sub(r'^[А-ЯЁ][а-яё-]+,?\s(?:[А-ЯЁ]\.\s?){1,2}\s*', '', t)
    t = re.sub(r'^(?:[А-ЯЁ]\.\s?){1,2}\s?[А-ЯЁ][а-яё-]+(?:,\s+[а-яё ]+ наук)?\s+(?=[А-ЯЁ])', '', t)
    m = re.match(r'^([А-ЯЁ][а-яё-]+)\s+([А-ЯЁ][а-яё]+\s.*)$', t)
    if m and not re.match(r'Российск|Особенн|Общ|Уголовн|Гражданск|Конституц|Верховн|Трудов|Федерал|Министер|Европейск|Следственн|Международн', m.group(1)) and re.search(r'(ов|ев|ёв|ин|ын|ова|ева|ина|ая|ий|ко|ук|юк|ян|ич|ец)$', m.group(1)): t = m.group(2)
    return t.strip(' .«»"')
def rec2(text):
    """Запись «[знак] [Фамилия И.О.] Название : вид / авторы. – Город : Издатель, год» — более терпимый разбор."""
    t = dehyph(' '.join(text.replace('\xa0', ' ').split()))
    for m in re.finditer(r'(?:[А-ЯЁ]\s?[-–]?\s?\d{1,3}\s+)(?P<head>[^/]{8,420}?)\s?/\s?(?P<resp>[^–—]{3,400}?)\.?\s?[–—]\s?(?P<city>[А-ЯЁ][А-Яа-яё.\- ]{0,30}?)\s?:\s?(?P<pub>[^,]{3,140}?)[,.]\s?(?P<year>(?:19|20)\d\d)', t):
        head = m.group('head').strip()
        if re.search(r'ISBN|УДК|ББК|Рецензент', head): continue
        head = re.sub(r'^[А-ЯЁ][а-яё-]+,?\s(?:[А-ЯЁ]\.\s?){1,2}\s*', '', head)
        km = re.search(r'\s?:\s?(' + KW + r')(.*)$', head, re.I)
        if km: title, kind, rest = head[:km.start()], km.group(1), km.group(2)
        else: title, kind, rest = head, '', ''
        pm = re.search(r'(Часть\s+\d+|Ч\.\s?\d+|Том\s+\d+|Т\.\s?\d+|Вып(?:уск|\.)\s?\d+)', rest)
        title = tclean(title) + ('. ' + pm.group(1) if pm else '')
        if len(title) < 6: continue
        return dict(title=title, kind=' '.join(kind.lower().split()), authors=bib.people(m.group('resp')), pub=bib.pub_short(m.group('city'), m.group('pub')), year=m.group('year'), how='запись')
    return None
def tp_clean(d):
    """Титульный лист одной строкой: убрать шапку ведомства, автора, вид, город и год."""
    t = ' '.join(d['title'].split())
    parts = re.split(r'(?:ФЕДЕРАЦИИ|Федерации|РОССИИ|России|ИНСТИТУТ|институт|УНИВЕРСИТЕТ|университет|АКАДЕМИЯ|академия|Кикотя|филиал[а-яё]*)[»)\s]*(?=\s)', t)
    t = parts[-1].strip() if len(parts) > 1 and len(parts[-1].strip()) > 8 else t
    t = re.sub(r'\s+[А-ЯЁ][а-яё-]+(?:-на-Дону)?\s*[-–]?\s*(?:19|20)\d\d\s*$', '', t)
    t = re.sub(r'\s+(' + KW + r')\s*$', '', t, flags=re.I)
    while True:
        t2 = re.sub(r'^(?:[А-ЯЁ]\.\s?){1,2}\s?[А-ЯЁ][а-яёА-ЯЁ-]+,?\s+', '', t)
        if t2 == t: break
        t = t2
    d = dict(d); d['title'] = tclean(t); return d
REL = {'upp': r'уг[. -]|угол|упп|упц|упк|процесс|следств|следоват|дознан|доказ|суд|прокур|защитник|обвин|задерж|пресеч|реабилит|возбужд|междунар|проц[. ]|предв|арест|опознан|имуществ|уд$|уд |оуп ',
       'up': r'уг[. -]|угол|ук рф|преступ|прест[. ]|наказ|квалиф|ответственн|оборон|соучаст|хищен|убийств|взят|корруп|экстрем|террор|наркот|мошен|краж|вымог|посягат|судим|невменя|деян|состав|вин[аы] |освобожд|рецидив|множеств|неосторож|умыс|злоуп|незаконн|полномоч|предпринимат|легализ|контрабанд|хулиган|похищ|насил|побо|вред здоров|бандит|вандал|разбо|грабе|присво|растрат|угон|подкуп|халатн|превышен|подлог|фальсиф',
       'gpp': r'процесс|проц[. ]|судопроиз|судебн|арбитраж|(?<![а-я])иск[а-я]* |доказ|исполнит|нотар|медиац|третейск|представит|споры|гпк|гпп',
       'tp': r'труд|работ|увольн|служб|занятост|отпуск|заработн|дисциплин',
       'tsp': r'такти|тсп|топограф|спец|операц|чрезвыч|безопасн|задержан|массов|заложн|защит|выжив|экстрем|боев|оборон|террор|в усл|местност|карт|наряд|профподготов|профессиональн\w+ подготовк|оружи\w+ массов|гражданск\w+ оборон|особых условиях'}
NREL = {'up': r'досудебн|дознан|допрос|деятельность следовател|^(особенности |методика |организация )?расследовани|методика расследован|организация расследован|раскрыти|опер-роз|прок\.|производств[оа] по|уголовн\w+ судопроизв|процессуальные действия|уголовно-процессуальных мер|экспертно-крим|организация руководителями',
        'gpp': r'упк|уголовн|принудительные меры медицинск', 'tp': r'уголовн', 'tsp': r'радиосвяз|технич\w* средств\w* обеспеч|взрывч|высотн'}
def prefixes(short):
    """Сокращённое название каталога («Уг.проц.компетенция») -> начала слов."""
    return [w.lower().replace('ё', 'е')[:4] for w in re.findall(r'[А-Яа-яЁё]{3,}', short) if w.lower() not in ('для', 'при', 'учеб', 'пособ', 'пособие', 'часть', 'ред', 'под')]
def agree(short, title):
    ps = prefixes(short)
    if not ps: return None
    t = title.lower().replace('ё', 'е')
    ws = re.findall(r'[а-я]+', t)
    hit = sum(1 for p in ps if any(w.startswith(p[:3]) for w in ws))
    return hit / len(ps)
def run(code):
    L = json.load(open(D5 + 'lib_%s_list.json' % code, encoding='utf-8'))
    P = D5 + 'books_%s.json' % code
    old = {b['n']: b for b in (json.load(open(P, encoding='utf-8')) if os.path.exists(P) else [])}
    tt = topics(code); tk = {t['id']: keys(code, t['text']) for t in tt}
    out = []; st = {'запись': 0, 'титул': 0, 'каталог': 0, 'нет файла': 0, 'не pdf': 0}
    for o in L:
        p = '.work/d5/%s/lib/%s.pdf' % (code, o['n'])
        if o['n'] in old and old[o['n']].get('done'): out.append(old[o['n']]); continue
        if not os.path.exists(p): st['нет файла'] += 1; continue
        b = dict(n=o['n'], url=o['url'], lib=o['rel'], lyear=o['year'], short=o['short'], size=os.path.getsize(p), done=True)
        try:
            text, pages = bib.first_pages(p, 6)
        except Exception as e:
            b.update(bad='не открывается: %s' % str(e)[:60]); out.append(b); st['не pdf'] += 1; continue
        b['pages'] = pages; b['textlayer'] = len(text.strip()) > 300
        d = None
        try: d = bib.describe(text)
        except Exception: d = None
        how = d and d.get('how')
        ok = bool(d) and not bib.suspicious(d)
        if ok and o['short']:
            a = agree(o['short'], d['title'])
            if a is not None and a < 0.34: ok = False
        if ok and o['year'] and d.get('year') and abs(int(d['year']) - o['year']) > 1: ok = False
        def good(x):
            if not x or len(x['title']) < 6 or len(x['title']) > 260: return False
            if re.search(r'МИНИСТЕРСТВО|ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ|ISBN|УДК|Печатается|Рецензент|редакционно-издательск|[Рр]екомендовано|©|[Оо]добрен|кандидат|доктор [а-я]+ наук|профессор', x['title']): return False
            a = agree(o['short'], x['title']) if o['short'] else None
            if a is not None and a < 0.34: return False
            if o['year'] and x.get('year') and abs(int(x['year']) - o['year']) > 1: return False
            return True
        if ok: d = dict(d); d['title'] = tclean(d['title']); ok = good(d)
        if not ok:
            try: d2 = rec2(text)
            except Exception: d2 = None
            if good(d2): d = d2; ok = True
        if not ok:
            try: d2 = bib.title_page(p)
            except Exception: d2 = None
            if d2:
                d2 = tp_clean(d2)
                if good(d2) and (not o['short'] or (agree(o['short'], d2['title']) or 0) >= 0.5) and not re.search(r'[а-яё] [А-ЯЁ]\.\s?[А-ЯЁ]\.', d2['title']):
                    if 'электронное издание' in (d2.get('kind') or ''): d2['kind'] = ''
                    if d2.get('authors') == 'Кикотя': d2['authors'] = ''
                    d = d2; ok = True
        if ok:
            b.update(title=d['title'], kind=d.get('kind') or '', authors=d.get('authors') or '', pub=d.get('pub') or '', year=int(d.get('year') or o['year'] or 0), how=d['how'])
            st['запись' if d['how'].startswith('запись') else 'титул'] += 1
        else:
            base = os.path.splitext(os.path.basename(o['rel']))[0]
            name = o['short'] or re.sub(r'^\d{4}\s*', '', base)
            if len(base) > len(name) + 8 and not re.match(r'^[\dA-Za-zЭР_.\- ]+$', base): name = re.sub(r'^\d{4}\s*', '', base)
            yr = o['year'] or 0
            if not yr:
                ys = [int(y) for y in re.findall(r'(?<!\d)(20[012]\d)(?!\d)', text[:3000]) if int(y) <= 2026]
                yr = max(ys) if ys else 0
            b.update(title=' '.join(name.replace('_', ' ').split()), kind='', authors='', pub='', year=yr, how='каталог'); st['каталог'] += 1
        # вопросы: по названию и по тексту первых страниц (аннотация, оглавление)
        tl = (b['title'] + ' ' + b.get('short', '')).lower().replace('ё', 'е'); xl = ' '.join(text.lower().replace('ё', 'е').split())
        q = []
        for t in tt:
            ks = tk[t['id']]
            if not ks: continue
            ht = sum(1 for k in ks if k in tl)
            if ht >= (1 if len(ks) <= 2 else 2) and ht * 2 >= len(ks): q.append(t['id'])
            elif len(ks) >= 3 and ht >= 1 and sum(1 for k in ks if k in xl) >= max(3, (len(ks) * 3 + 3) // 4): q.append(t['id'])
        b['q'] = q
        ts = (b['title'] + ' ' + b.get('short', '')).lower().replace('ё', 'е')
        b['off'] = False if o.get('force') else (not re.search(REL[code], ts) or bool(NREL.get(code) and re.search(NREL[code], ts)))
        b['general'] = bool(re.search(GEN[code], ' '.join(b['title'].lower().replace('ё', 'е').split()).strip(' .')))
        out.append(b)
    got = {b['n'] for b in out}; out += [b for n, b in old.items() if n not in got]   # записи, добавленные вне списка (rebooks.py), сохраняются
    json.dump(out, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(code, 'описано:', len(out), st, 'без вопросов и не общие:', sum(1 for b in out if not b.get('q') and not b.get('general') and not b.get('bad')))
    return out
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in DISC] or list(DISC):
        out = run(code)
        if '--show' in sys.argv:
            for b in out: print(b['n'], b.get('how'), '|', b.get('authors'), '|', (b.get('title') or '')[:70], '|', b.get('kind'), '|', b.get('pub'), b.get('year'), '| кат:', b['short'][:30], '| q', len(b.get('q', [])), 'G' if b.get('general') else '')
