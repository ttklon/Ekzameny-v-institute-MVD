# -*- coding: utf-8 -*-
"""Первая волна заданий для пяти дисциплин: акты, судебная практика, обход каталогов библиотеки, поиск статей, статистика.
Пишет списки в .github/downloader/shards/ (каждый список выполняется отдельным заданием GitHub Actions)."""
import os, re, csv, sys, urllib.parse, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
import acts
os.chdir(ROOT)
SH = '.github/downloader/shards/'
for f in glob.glob(SH + '*.tsv'): os.remove(f)
def write(name, rows):
    with open(SH + name + '.tsv', 'w', encoding='utf-8') as f:
        for r in rows: f.write('\t'.join(r) + '\n')
    print(name, len(rows))
def ips(req): return 'http://ips.pravo.gov.ru/api/ips/legislation/search.json?query=%s&limit=10&page=1#%s' % (urllib.parse.quote_plus(req), req)
# --- акты
rows = [('ipsact', ips(req), '.work/d5/acts/%s.pdf' % key) for key, req, *_ in acts.IPS]
write('acts1', rows[0::2]); write('acts2', rows[1::2])
# --- Конституционный Суд
write('ks', [('ipsact', ips('Постановление Конституционного Суда Российской Федерации от %s № %s' % (d, n)), '.work/d5/ks/%s_%s.pdf' % (n, d[-4:])) for d, n, *_ in acts.KS])
# --- Пленум: известные номера документов consultant.ru берутся из журнала прежних загрузок
known = {}
for r in csv.reader(open('.github/downloader/log.tsv', encoding='utf-8'), delimiter='\t'):
    if len(r) > 7 and r[1] == 'cons' and r[4] == 'ok':
        m = re.search(r'Постановление Пленума Верховного Суда РФ от (\d\d\.\d\d\.\d{4}) N (\d+)', r[7])
        if m: known[(m.group(1), m.group(2))] = r[2].split('#')[0]
rows = []
for d, n, *_ in acts.PL:
    out = '.work/d5/pl/%s_%s.pdf' % (d[-4:] + d[3:5] + d[:2], n); exp = 'от %s N %s' % (d, n)
    if (d, n) in known: rows.append(('cons', known[(d, n)] + '#' + exp, out))
    else: rows.append(('consauto', 'Постановление Пленума Верховного Суда РФ от %s N %s#%s' % (d, n, exp), out))
rows.sort(key=lambda r: r[0] != 'cons')
print('пленум: известных адресов', sum(1 for r in rows if r[0] == 'cons'), 'поиском', sum(1 for r in rows if r[0] != 'cons'))
for i in range(3): write('pl%d' % (i + 1), rows[i::3])
write('cons', [('consauto', '%s#%s' % (q, exp), '.work/d5/cons/%s.pdf' % key) for key, q, exp, *_ in acts.CONS])
# --- каталоги электронной библиотеки
B = 'http://lib.eioskuimvd.ru/jirbis2/_docs_file/Эл. библ. для учебы/'
LIB = [('Электронные издания ВУЗов МВД России/Уголовное право/', 400), ('Электронные издания ВУЗов МВД России/Гражданский процесс/', 150),
       ('Электронные издания ВУЗов МВД России/Трудовое право/', 150), ('Электронные издания ВУЗов МВД России/Тактико-специальная подготовка/', 300),
       ('Электронные издания ВУЗов МВД России/Личная безопасность/', 150), ('Электронные издания ВУЗов МВД России/Проф. подготовка полицейских/', 150),
       ('Электронные издания ВУЗов МВД России/Дознание/', 100), ('Электронные издания ВУЗов МВД России/Противодействие терроризму/', 100),
       ('Электронные издания ВУЗов МВД России/Гражданское право/', 150), ('Электронные издания ВУЗов МВД России/Судебная система/', 60),
       ('Электронные издания ВУЗов МВД России/Прокурорский надзор/', 60), ('Электронные издания ВУЗов МВД России/Уголовно-исполнительное право/', 80),
       ('Электронная библиотека КЮИ/Уголовное право/', 200), ('Электронная библиотека КЮИ/Гражданский процесс/', 100), ('Электронная библиотека КЮИ/Трудовое право/', 100),
       ('Электронная библиотека КЮИ/Тактико-специальная подготовка/', 150), ('Электронная библиотека КЮИ/Личная безопасность/', 80),
       ('Электронная библиотека КЮИ/Уголовно процессуальное право/', 150), ('Электронная библиотека КЮИ/Гражданское право/', 100),
       ('Электронные учебники ВУЗов МВД России/Уголовное право/', 40), ('Электронные учебники ВУЗов МВД России/Тактико-специальная подготовка/', 40),
       ('Электронные учебники ВУЗов МВД России/Уголовный процесс/', 40), ('Электронные учебники ВУЗов МВД России/Гражданское право/', 40),
       ('Электронные учебные издания КЮИ/Тактико-специальная подготовка/', 40), ('Электронные учебные издания КЮИ/Уг.-пр.право/', 40),
       ('БИБЛИОТЕКА ПОЛИЦЕЙСКОГО/17. Тактико-специальная подготовка/', 40), ('БИБЛИОТЕКА ПОЛИЦЕЙСКОГО/3. Основы уголовного права/', 40),
       ('БИБЛИОТЕКА ПОЛИЦЕЙСКОГО/4. Основы уголовного процесса/', 40), ('БИБЛИОТЕКА ПОЛИЦЕЙСКОГО/1. Базовый учебник ДГСК МВД России/', 40)]
open(D5 + 'lib_crawl.txt', 'w', encoding='utf-8').write(''.join('%s%s#3,%d\n' % (B, p, n) for p, n in LIB))
write('lib', [('crawllist', D5 + 'lib_crawl.txt', D5 + 'lib_files.tsv')])
# --- поиск статей: по одному-два запроса на тему
def query(code, t):
    s = t['text']; ref = t['refs'][0]
    s = re.sub(r'\([^)]*\)', ' ', s)
    first = re.split(r'(?<=[а-яё»])[.:]\s', s)[0]
    special = code == 'up' and (ref.startswith('Б-С') or (ref.startswith('А') and int(ref[1:]) >= 54)) and ref not in ('Б-С1', 'Б-С2', 'Б-С17')
    if special:
        first = re.sub(r'\s*(: )?состав.*$', '', first, flags=re.I).strip(' .,:')
        return [first + ' уголовная ответственность квалификация']
    w = re.sub(r'[«»",;:]', ' ', first).split()
    q = ' '.join(w[:11])
    ctx = {'upp': 'уголовный процесс', 'up': 'уголовное право', 'gpp': 'гражданский процесс', 'tp': 'трудовое право'}.get(code)
    if code == 'tsp':
        if ref.startswith('Д'):
            n = int(ref[1:])
            ctx = 'топографическая подготовка сотрудников полиции' if n <= 18 else ('гражданская оборона чрезвычайные ситуации органы внутренних дел' if n <= 33 else 'тактическая подготовка подразделение')
            if n == 44: ctx = 'органы внутренних дел'
        else:
            n = int(ref)
            ctx = 'топографическая подготовка сотрудников полиции' if n in (20, 23, 25, 42, 44, 45, 46, 48, 49) else 'органы внутренних дел тактика'
    if ctx.split()[0][:6].lower() in q.lower() and code != 'tsp': return [q]
    return [q + ' ' + ctx]
for code in DISC:
    tt = topics(code); lines = []
    for t in tt:
        for q in query(code, t): lines.append('%s\t%s' % (t['id'], ' '.join(q.split())))
    open(D5 + 'cyber_q_%s.txt' % code, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    write('cyber_' + code, [('cybersearch', D5 + 'cyber_q_%s.txt#25' % code, D5 + 'cyber_%s.tsv' % code)])
# --- статистика
ST = [('https://cdep.ru/userimages/Statistika_2023/F2-svod-vse-sudy-2023.xls', 'cdep_f2_2023.xls'), ('https://cdep.ru/userimages/Statistika_2024/F2-svod_vse_sudy-2024.xls', 'cdep_f2_2024.xls'),
      ('https://cdep.ru/userimages/Statistika_2025_all/F2-svod_vse_sudy-2025.xls', 'cdep_f2_2025.xls'),
      ('https://cdep.ru/index.php?id=79&item=8690', 'cdep_item_8690.html'), ('https://cdep.ru/index.php?id=79&item=8809', 'cdep_item_8809.html'),
      ('https://cdep.ru/index.php?id=79&item=9893', 'cdep_item_9893.html'), ('https://cdep.ru/index.php?id=79&item=8946', 'cdep_item_8946.html'),
      ('https://cdep.ru/index.php?id=79', 'cdep_79.html'), ('https://cdep.ru/index.php?id=80', 'cdep_80.html')]
write('stat', [('get', u, '.work/d5/stat/' + f) for u, f in ST])
