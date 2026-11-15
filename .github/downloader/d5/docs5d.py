# -*- coding: utf-8 -*-
"""Реестр источников, «Литература и материалы по вопросам» и контрольные суммы для пяти дисциплин.
Запуск: /tmp/venv/bin/python docs5d.py [коды]. Повторный запуск безопасен: документы строятся заново по содержимому папок."""
import os, re, sys, json, glob, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics, read_list
from sel_art import keys
from actq import act_regex
import fitz
os.chdir(ROOT)
fitz.TOOLS.mupdf_display_errors(False)
DATE = '15.11.2026'
FULL = {'upp': 'Уголовно-процессуальное право', 'up': 'Уголовное право', 'gpp': 'Гражданско-процессуальное право', 'tp': 'Трудовое право', 'tsp': 'Тактико-специальная подготовка'}
MAIN = {'upp': ['upk'], 'up': ['uk'], 'gpp': ['gpk'], 'tp': ['tk'], 'tsp': []}   # основной акт курса — ко всем вопросам
PC = D5 + 'pages_cache.json'
PAGES = json.load(open(PC, encoding='utf-8')) if os.path.exists(PC) else {}
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def pages(p, s=None):
    s = s or sha(p)
    if s not in PAGES:
        try: d = fitz.open(p); PAGES[s] = d.page_count; d.close()
        except Exception: PAGES[s] = 0
    return PAGES[s]
def mb(n): return ('%.1f МБ' % (n / 1048576)).replace('.', ',') if n >= 104858 else '%d КБ' % max(1, round(n / 1024))
def esc(s): return s.replace('|', '¦')
PORD = {'Э': 0, 'З': 1, 'А': 0, 'Б-О': 1, 'Б-С': 2, '': 0, 'Д': 1}
def labsort(l):
    m = re.match(r'^(\D*)(\d+)$', l); return (PORD.get(m.group(1), 9), m.group(1), int(m.group(2)))
def rng(labels):
    """['Э1','Э2','Э3','З5'] -> 'Э1–Э3, З5'"""
    out = []; labels = sorted(set(labels), key=labsort); i = 0
    while i < len(labels):
        j = i
        while j + 1 < len(labels) and labsort(labels[j + 1])[:2] == labsort(labels[j])[:2] and labsort(labels[j + 1])[2] == labsort(labels[j])[2] + 1: j += 1
        out.append(labels[i] if j == i else '%s–%s' % (labels[i], labels[j]) if j > i + 1 else '%s, %s' % (labels[i], labels[j]))
        i = j + 1
    return ', '.join(out)
def match(code, text, tt, tk):
    """Вопросы, с формулировкой которых предмет акта совпадает по ключевым словам."""
    sk = keys(code, text)
    if not sk: return []
    tl = text.lower().replace('ё', 'е'); out = []
    for t in tt:
        ks = tk[t['id']]
        if not ks: continue
        xl = t['text'].lower().replace('ё', 'е')
        a = sum(1 for k in ks if k in tl); b = sum(1 for k in sk if k in xl)
        sh = max(a, b); m = min(len(ks), len(sk))
        if (len(ks) == 1 and a == 1) or (len(sk) == 1 and sk[0] in ks[:2]) or (sh >= 2 and sh * 2 >= m): out.append(t['id'])
    return out
def run(code):
    S = DISC[code]['dir'] + '/2. Источники/'
    tt = topics(code); tk = {t['id']: keys(code, t['text']) for t in tt}; ref = {t['id']: t['refs'] for t in tt}
    allrefs = [r for t in tt for r in t['refs']]
    def qs(ids, general=False, limit=14):
        if general: return 'все'
        labs = [r for i in ids for r in ref.get(i, [])]
        if not labs: return 'общий'
        if len(set(labs)) > limit: return '%s (всего %d)' % (rng(sorted(set(labs), key=labsort)[:limit]), len(set(labs)))
        return rng(labs)
    acts = [m for m in json.load(open(D5 + 'acts_manifest.json', encoding='utf-8')) if m['code'] == code and os.path.exists(S + m['folder'] + m['name'])]
    for m in acts:
        m['pages'] = pages(S + m['folder'] + m['name'])
        m['court'] = m['folder'].startswith('2.')
        m['all'] = m['key'] in MAIN[code]
        subj = m['topic'] if m['court'] else re.sub(r'^.*?№ \S+ ', '', m['name'][:-4])
        subj = re.sub(r'^Постановление (КС|Пленума ВС) РФ от \S+ № \S+ \((.*)\)$', r'\2', subj)
        if m['all']: m['q'] = []
        elif m['court']: m['q'] = match(code, subj, tt, tk)
        else:
            rx = act_regex(code, m['key'], m['name'])
            m['q'] = [t['id'] for t in tt if rx and re.search(rx, t['text'].lower().replace('ё', 'е'))]
        m['subj'] = subj
    man = [m for m in json.load(open(D5 + 'manifest_%s.json' % code, encoding='utf-8')) if os.path.exists(S + m['dst'])]
    books = [m for m in man if m['cat'] == 'book']; sci = [m for m in man if m['cat'] == 'sci']; arts = [m for m in man if m['cat'] == 'art']; emp = [m for m in man if m['cat'] == 'emp']
    na = [m for m in acts if not m['court']]; nc = [m for m in acts if m['court']]
    lists = DISC[code]['lists']
    nq = sum(len(t['refs']) for t in tt)
    R = ['# Реестр источников — %s' % FULL[code], '']
    R.append('Состояние на %s. %s (папка «1. Примерный перечень вопросов»).' % (DATE, 'Вопросов в перечне — %d' % nq if len(lists) == 1 else 'Перечни: ' + '; '.join('«%s» — %s' % (n, {'Э': 'метки Э', 'З': 'метки З', 'А': 'метки А', 'Б': 'метки Б-О (общая часть) и Б-С (особенная часть)'}.get(tag, tag)) for tag, fn, n in lists) + '. Всего вопросов — %d; одинаковые формулировки из двух перечней сведены в одну тему, тем — %d' % (nq, len(tt))))
    if code == 'tsp': R[-1] += ' Вопросы 1–60 — нумерованные; Д1–Д44 — ненумерованные вопросы из второй части перечня (топография, защита от оружия массового поражения и чрезвычайные ситуации, оборона и наступление отделения, наряды ППСП), пронумерованы по порядку.'
    R += ['', '**Источники права — %d:** нормативные акты — %d, акты судебной практики — %d.' % (len(acts), len(na), len(nc)), '']
    old3 = sum(1 for m in books if m.get('old'))
    R += ['**Литература и материалы:** учебные издания — %d (из них до 2023 года — %d); научные издания (монографии, сборники) — %d; статьи 2023–2026 годов — %d (из них в журналах с отметкой ВАК — %d); эмпирические материалы — %d.' % (
        len(books), old3, len(sci), len(arts), sum(1 for m in arts if m.get('vak')), len(emp)), '']
    R += ['Файлы скачивает загрузчик на GitHub Actions (`.github/downloader/`); каждая загрузка записана в журналы `.github/downloader/logs/` (время, адрес, размер, SHA-256). Сведения об актах — в `.github/downloader/d5/acts_manifest.json`, об изданиях и статьях — в `.github/downloader/d5/manifest_%s.json`. Контрольные суммы всех файлов — в «Контрольные суммы SHA-256.txt».' % code, '']
    R += ['**Как назначены вопросы.** У нормативных актов — по предмету регулирования: для каждого акта задан признак (ключевые слова), и акт отнесён к вопросам, в формулировке которых этот признак есть (таблица признаков — `.github/downloader/d5/actq.py`). У остального — автоматически, по совпадению ключевых слов: у судебной практики — предмета акта и формулировки вопроса, у изданий — названия, аннотации и строк оглавления, у статей — названия и аннотации. Полные тексты не читались, поэтому привязка приблизительная: возможны и лишние, и пропущенные вопросы. «все» — источник по всему курсу; «общий» — к конкретному вопросу не привязан.', '']
    R += ['## А. Что в базе', '', '### А.1. Нормативные правовые акты', '', '| Файл | Папка | Откуда | Редакция | Стр. | Вопросы |', '|---|---|---|---|---|---|']
    for m in sorted(na, key=lambda m: (m['folder'], m['name'])):
        R.append('| %s | %s | %s | %s | %s | %s |' % (esc(m['name']), m['folder'].split('/')[1], m['site'], esc(m['edition'] or '—'), m['pages'] or '—', qs(m['q'], m['all'])))
    R += ['', '- Тексты с ips.pravo.gov.ru — государственная система «Законодательство России», действующая редакция на день загрузки (%s); рядом с PDF, в папках «Исходные страницы (HTML)», лежат сохранённые страницы. В столбце «Редакция» — дата действующей редакции и акт, которым внесено последнее изменение, по карточке акта в системе.' % DATE,
          '- Тексты с consultant.ru — справочные, не официальный источник; редакция указана по названию документа на сайте.',
          '- «Из базы …» — файл не скачивался заново, а скопирован из уже собранной базы другой дисциплины (там он скачан и сверен 14–15.11.2026).', '']
    R += ['### А.2. Судебная практика', '', '| Файл | Откуда | Редакция | Стр. | Вопросы |', '|---|---|---|---|---|']
    for m in sorted(nc, key=lambda m: (m['folder'], m['name'][-4:] if False else m['name'])):
        R.append('| %s | %s | %s | %s | %s |' % (esc(m['name']), m['site'], esc(m['edition'] or '—'), m['pages'] or '—', qs(m['q'])))
    R += ['', '- Постановления Конституционного Суда РФ взяты с ips.pravo.gov.ru; постановления Пленума и обзоры Верховного Суда РФ — с consultant.ru (справочный текст; редакция — по названию документа на сайте).', '']
    def lit(title, L, n):
        R.extend(['### А.%d. %s' % (n, title), ''])
        if not L: R.extend(['Нет.', '']); return
        R.extend(['| Файл | Год | Стр. | Размер | Вопросы | Примечание |', '|---|---|---|---|---|---|'])
        for m in sorted(L, key=lambda m: os.path.basename(m['dst']).lower()):
            note = []
            if m.get('how') == 'каталог': note.append('название — по каталогу библиотеки: описание в файле не распознано')
            if m.get('garbled'): note.append('скан без текстового слоя')
            if m.get('old'): note.append('издание %s года — сверить с действующими актами' % m['year'])
            R.append('| %s | %s | %s | %s | %s | %s |' % (esc(os.path.basename(m['dst'])), m.get('year') or '—', m.get('pages') or '—', mb(m['size']), qs(m['q'], m.get('general')), '; '.join(note)))
        R.append('')
    lit('Учебная литература', books, 3)
    R += ['- Издания взяты из открытых каталогов электронной библиотеки lib.eioskuimvd.ru. Имя файла составлено по библиографической записи на обороте титульного листа; где запись не распознана, оставлено название по каталогу библиотеки (отмечено).', '']
    lit('Научные издания (монографии, сборники, материалы конференций)', sci, 4)
    R += ['### А.5. Статьи (2023–2026)', '']
    if arts:
        R += ['| Файл | Журнал | Год | ВАК | Стр. | Вопросы |', '|---|---|---|---|---|---|']
        for m in sorted(arts, key=lambda m: os.path.basename(m['dst']).lower()):
            R.append('| %s | %s | %s | %s | %s | %s |' % (esc(os.path.basename(m['dst'])), esc(m['pub']), m['year'], 'да' if m.get('vak') else '', m['pages'], qs(m['q'], False) + (' (по разделу)' if m.get('wide') else '')))
        R += ['', '- Статьи взяты с cyberleninka.ru (открытый доступ). «ВАК» — отметка сайта о вхождении журнала в перечень ВАК; по самому перечню не проверялась.', '']
    else: R += ['Нет.', '']
    R += ['### А.6. Эмпирические материалы', '']
    if emp:
        R += ['| Файл | Размер | Примечание |', '|---|---|---|']
        for m in sorted(emp, key=lambda m: m['dst']): R.append('| %s | %s | %s |' % (esc(os.path.basename(m['dst'])), mb(m['size']), m.get('note') or ''))
        R.append('')
    else: R += ['Нет.', '']
    # --- Б. чего нет
    cov_art = collections.Counter(i for m in arts for i in m['q']); cov_book = collections.Counter(i for m in books + sci for i in m['q']); cov_act = collections.Counter(i for m in acts for i in m['q'])
    noart = [t['refs'][0] for t in tt if not cov_art[t['id']]]; nobook = [t['refs'][0] for t in tt if not cov_book[t['id']]]
    nothing = [t['refs'][0] for t in tt if not cov_art[t['id']] and not cov_book[t['id']]]
    R += ['## Б. Чего нет и что требует проверки', '']
    dp = D5 + 'acts_dropped.json'
    drop = [d for d in (json.load(open(dp, encoding='utf-8')) if os.path.exists(dp) else []) if code in d['codes']]
    R += ['### Б.1. Акты', '']
    extra = NOTES.get(code, [])
    if drop or extra:
        for d in drop:
            why = 'текст не получен' if d['why'] == 'не получен' else ('по карточке ips.pravo.gov.ru: «%s»; в базу не включён' % d['why'] if re.match(r'[Уу]тратил|[Нн]е действует|[Оо]тмен', d['why']) else d['why'])
            R.append('- %s — %s.' % (d['name'], why) + (' ' + REPL[d['key']] if d['key'] in REPL else ''))
        R += ['- ' + x for x in extra]
    else: R.append('Все запланированные акты получены.')
    R += ['', '### Б.2. Вопросы без материалов', '']
    R.append('- Без статей: %s.' % (rng(noart) if noart else 'нет'))
    R.append('- Без учебных и научных изданий, привязанных по названию или оглавлению (общие учебники по курсу не считаются): %s.' % (rng(nobook) if nobook else 'нет'))
    R.append('- Без статей и без привязанных изданий одновременно: %s.' % (rng(nothing) if nothing else 'нет'))
    R += ['', '### Б.3. Ограничения', '',
          '- Привязка источников к вопросам автоматическая (см. выше); содержание изданий и статей по существу не проверялось.',
          '- Изменения актов, принятые, но не вступившие в силу на %s, в тексты не входят.' % DATE,
          '- Учебные издания до 2023 года могут расходиться с действующим законодательством: сверять с актами из раздела А.1.']
    cat = sum(1 for m in books + sci if m.get('how') == 'каталог')
    if cat: R.append('- У %d изданий имя файла оставлено по каталогу библиотеки (автор, вид и издатель не установлены).' % cat)
    open(S + 'Реестр источников.md', 'w', encoding='utf-8').write('\n'.join(R) + '\n')
    # --- Литература и материалы по вопросам
    L = ['# Литература и материалы по вопросам — %s' % FULL[code], '', 'Состояние на %s. Пути указаны от папки «2. Источники». Привязка к вопросам автоматическая, по ключевым словам (подробнее — в «Реестре источников»).' % DATE, '']
    L += ['## Источники по всему курсу', '']
    for m in na:
        if m['all']: L.append('- %s%s' % (m['folder'], m['name']))
    gen = [m for m in books if m.get('general')]
    for m in sorted(gen, key=lambda m: (-(m.get('year') or 0), m['dst'])): L.append('- %s' % m['dst'])
    for m in arts:
        if m.get('general'): L.append('- %s' % m['dst'])
    if emp: L.append('- Эмпирические материалы: папка «5. Эмпирические материалы (с 2023 года)» (%d файлов).' % len(emp))
    L.append('')
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for m in acts:
        for i in m['q']: by[i]['court' if m['court'] else 'act'].append(m['folder'] + m['name'])
    for m in books + sci:
        for i in m['q']: by[i]['book'].append(m)
    for m in arts:
        for i in m['q']: by[i]['art'].append(m)
    done = {}
    for tag, fn, lname in lists:
        items = read_list(code, tag, fn)
        if len(lists) > 1: L += ['## %s' % lname[:1].upper() + lname[1:] + ' — «%s»' % fn[:-4], '']
        idx = {t['id']: t for t in tt}
        from common import norm
        byk = {norm(t['text']): t for t in tt}
        for lab, text in items:
            t = byk[norm(text)]
            L += ['### %s. %s' % (lab, text), '']
            if t['id'] in done and done[t['id']] != lab: L += ['См. вопрос %s (та же формулировка).' % done[t['id']], '']; continue
            done[t['id']] = lab
            b = by[t['id']]
            if not any(b.values()): L += ['Привязанных источников нет — см. источники по всему курсу.', '']; continue
            if b['act']: L += ['**Акты:**'] + ['- ' + x for x in sorted(b['act'])] + ['']
            if b['court']: L += ['**Судебная практика:**'] + ['- ' + x for x in sorted(b['court'])] + ['']
            if b['book']:
                bb = sorted(b['book'], key=lambda m: (-(m.get('year') or 0), m['dst']))
                L += ['**Учебные и научные издания:**'] + ['- ' + m['dst'] for m in bb[:12]] + (['- …и ещё %d (см. реестр)' % (len(bb) - 12)] if len(bb) > 12 else []) + ['']
            if b['art']:
                aa = sorted(b['art'], key=lambda m: ((m['q'] or [''])[0] != t['id'], not m.get('vak'), -m['year'], m['dst']))
                L += ['**Статьи:**'] + ['- %s%s' % (m['dst'], ' — ВАК' if m.get('vak') else '') for m in aa[:10]] + (['- …и ещё %d (см. реестр, раздел А.5)' % (len(aa) - 10)] if len(aa) > 10 else []) + ['']
    open(S + 'Литература и материалы по вопросам.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    # --- контрольные суммы
    rows = []
    for d, _, fs in os.walk(S):
        for f in fs:
            p = os.path.join(d, f); rel = os.path.relpath(p, S)
            if rel == 'Контрольные суммы SHA-256.txt' or f.startswith('.'): continue
            rows.append('%s  %s' % (sha(p), rel))
    open(S + 'Контрольные суммы SHA-256.txt', 'w', encoding='utf-8').write('\n'.join(sorted(rows, key=lambda r: r[66:])) + '\n')
    json.dump(PAGES, open(PC, 'w', encoding='utf-8'), indent=0)
    res = dict(code=code, acts=len(na), court=len(nc), books=len(books), sci=len(sci), arts=len(arts), vak=sum(1 for m in arts if m.get('vak')), emp=len(emp), sums=len(rows), noart=noart, nobook=nobook, nothing=nothing,
               catalog=cat, drop=[d['name'] for d in drop], topics=len(tt), nq=nq)
    print(code, {k: (v if not isinstance(v, list) else len(v)) for k, v in res.items()})
    return res
REPL = {'p922': 'Заменён постановлением Правительства РФ от 24.04.2025 № 540 (в базе).', 'p749': 'Заменён постановлением Правительства РФ от 16.04.2025 № 501 (в базе).',
        'p522': 'Действующий порядок определения степени тяжести вреда здоровью — приказ Минздрава России от 08.04.2025 № 172н (в базе, папка «5. Ведомственные акты»).',
        'p823': 'Перечни должностей и работ для договоров о полной материальной ответственности утверждены приказом Минтруда России от 16.04.2025 № 251н (в базе, папка «5. Ведомственные акты»).'}
NOTES = {
 'gpp': ['Налоговый кодекс РФ (глава 25.3, государственная пошлина) в базу не включён; по вопросу о судебных расходах в базе — ГПК РФ, постановление Пленума ВС РФ о судебных издержках и учебные издания.'],
 'tsp': ['Ведомственные акты МВД России о действиях при чрезвычайных обстоятельствах, о специальных операциях и о боевой подготовке в открытых источниках не найдены (часть таких актов имеет пометку «для служебного пользования»); в базе их нет. Вопросы о боевых порядках групп, оперативном штабе, решении и боевом приказе обеспечены учебными изданиями и статьями.',
         'Боевой устав Сухопутных войск и руководства по военной топографии в базу не включены: поиск их открытого официального текста не проводился. Вопросы Д34–Д43 (оборона и наступление отделения) обеспечены только учебными изданиями.'],
}
if __name__ == '__main__':
    out = [run(code) for code in ([a for a in sys.argv[1:] if a in DISC] or list(DISC))]
    json.dump(out, open(D5 + 'summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
