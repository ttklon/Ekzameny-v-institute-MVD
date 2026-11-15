# -*- coding: utf-8 -*-
"""Раскладка актов и судебной практики из .work/d5 по папкам дисциплин; запись сведений в acts_manifest.json.
Повторный запуск безопасен: уже разложенные файлы не трогаются, сведения о них сохраняются."""
import os, re, sys, csv, json, glob, shutil, hashlib, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5
import acts
os.chdir(ROOT)
N = '1. Нормативные правовые акты/'; C = '2. Судебная практика/'
FOLD = {1: N + '1. Конституция РФ/', 2: N + '2. Кодексы/', 3: N + '3. Федеральные законы/', 4: N + '4. Указы Президента РФ и постановления Правительства РФ/',
        5: N + '5. Ведомственные акты/', 6: N + '6. Международные договоры/', 'ks': C + '1. Конституционный Суд РФ/', 'pl': C + '2. Пленум Верховного Суда РФ/', 's3': C + '3. Обзоры Верховного Суда РФ/'}
H = 'Исходные страницы (HTML)/'
def S(code): return DISC[code]['dir'] + '/2. Источники/'
def fit(name, cap=221):
    name = ' '.join(name.replace('/', '-').replace(':', ' —').replace('"', '').replace('?', '').split())
    if len(name.encode('utf-8')) <= cap: return name
    par = ''
    m = re.match(r'^(.*?)(\s\([^()]*)\)$', name)
    words = name.split()
    while len((' '.join(words) + '…').encode('utf-8')) > cap - (1 if m else 0): words.pop()
    out = ' '.join(words).rstrip(',;—- ') + '…'
    return out + (')' if m and '(' in out and ')' not in out else '')
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
LOG = {}
for f in sorted(glob.glob('.github/downloader/logs/*.tsv')):
    for r in csv.reader(open(f, encoding='utf-8'), delimiter='\t'):
        if len(r) >= 9 and r[4] == 'ok': LOG[r[3]] = r
MP = D5 + 'acts_manifest.json'
MAN = {(m['code'], m['key']): m for m in (json.load(open(MP, encoding='utf-8')) if os.path.exists(MP) else []) if '№ 736 (действующая редакция)' not in m['name']}
DROP = []
def card(url):
    m = re.search(r'nd=(\d+)', url)
    p = '.work/cards/%s.json' % (m.group(1) if m else '')
    if not m or not os.path.exists(p): return None
    return json.load(open(p, encoding='utf-8'))
SUPER = {'mz194n': 'в базу не включён: на странице документа consultant.ru стоит отметка «Документ утратил силу или отменен»; по предмету действует приказ Минздрава России от 08.04.2025 № 172н (в базе)',
         'mt85': 'в базу не включён: на странице документа consultant.ru стоит отметка «Документ утратил силу или отменен»; по предмету действует приказ Минтруда России от 16.04.2025 № 251н (в базе)'}
LOST = 'Документ утратил силу или отменен'   # отметка на странице документа consultant.ru (в названии её может не быть)
GONE = {}
def lost(path):
    return os.path.exists(path) and LOST in re.sub(r'<[^>]+>', ' ', open(path, encoding='utf-8', errors='replace').read()[:200000])
def put(grp, key, folder, name, codes, topic, kind):
    if key in SUPER: DROP.append(dict(key=key, name=name, why=SUPER[key], codes=codes)); return
    if key in GONE: DROP.append(dict(GONE[key], codes=codes)); return
    src = '.work/d5/%s/%s.pdf' % (grp, key); hsrc = '.work/d5/%s/%s%s.html' % (grp, H, key)
    if grp == 'cons' and not os.path.exists(src): src = src.replace('/cons/', '/cons2/'); hsrc = hsrc.replace('/cons/', '/cons2/')
    row = LOG.get(src)
    if not os.path.exists(src):
        if not any((c, key) in MAN for c in codes): DROP.append(dict(key=key, name=name, why='не получен', codes=codes))
        return
    edition = state = ''; site = 'ips.pravo.gov.ru' if kind == 'ips' else 'consultant.ru'
    if kind == 'ips':
        cd = card(row[2])
        state = (cd or {}).get('state') or row[7].split('; ')[-1]
        act = [x for x in (cd or {}).get('redactions') or [] if x.get('actual')]
        if act:
            a = act[0]
            edition = 'редакция на %s' % a['date'] + (' (изм. — %s)' % a['refadoption'] if a.get('refadoption') else ' (первоначальная)' if len(cd['redactions']) == 1 else '')
        if re.search(r'[Уу]тратил|[Нн]е действует|[Оо]тмен', state):
            DROP.append(dict(key=key, name=name, why=state, codes=codes)); return
    else:
        title = row[7].split('; ')[2] if len(row[7].split('; ')) > 2 else ''
        m = re.search(r'\((?:ред|с изм)\. (?:и доп\. )?от (\d\d\.\d\d\.\d{4})', title)
        edition = 'редакция от %s' % m.group(1) if m else 'изменений в названии документа на сайте не указано'
        state = 'утратил силу' if re.search(r'утратил', title, re.I) else ''
        if state: DROP.append(dict(key=key, name=name, why='по названию документа на consultant.ru — утратил силу', codes=codes)); return
        if lost(hsrc): DROP.append(dict(key=key, name=name, why='на странице документа consultant.ru стоит отметка «Документ утратил силу или отменен»; в базу не включён', codes=codes)); return
    name = fit(name)
    for code in codes:
        d = S(code) + FOLD[folder]
        os.makedirs(d + H, exist_ok=True)
        dst = d + name + '.pdf'
        if not os.path.exists(dst): shutil.copyfile(src, dst)
        if os.path.exists(hsrc) and not os.path.exists(d + H + name + '.html'): shutil.copyfile(hsrc, d + H + name + '.html')
        MAN[(code, key)] = dict(code=code, key=key, grp=grp, folder=FOLD[folder], name=name + '.pdf', site=site, url=row[2], edition=edition, state=state,
                                checked=row[0][8:10] + '.' + row[0][5:7] + '.' + row[0][:4], sha=sha(dst), topic=topic, html=os.path.exists(hsrc))
for (code, key), m in list(MAN.items()):
    if m.get('site') == 'consultant.ru' and lost(S(code) + m['folder'] + H + m['name'][:-4] + '.html'):
        for f in (S(code) + m['folder'] + m['name'], S(code) + m['folder'] + H + m['name'][:-4] + '.html'):
            if os.path.exists(f): os.remove(f)
        GONE[key] = dict(key=key, name=m['name'][:-4], why='на странице документа consultant.ru стоит отметка «Документ утратил силу или отменен»; из базы убран', codes=[code])
        del MAN[(code, key)]; print('  убран (утратил силу):', code, m['name'][:90])
for key, req, folder, name, codes in acts.IPS: put('acts', key, folder, name, codes.split(), req, 'ips')
for d, n, topic, codes in acts.KS: put('ks', '%s_%s' % (n, d[-4:]), 'ks', 'Постановление КС РФ от %s № %s (%s)' % (d, n, topic), codes.split(), topic, 'ips')
for d, n, topic, codes in acts.PL: put('pl', '%s_%s' % (d[-4:] + d[3:5] + d[:2], n), 'pl', 'Постановление Пленума ВС РФ от %s № %s (%s)' % (d, n, topic), codes.split(), topic, 'cons')
for key, q, exp, folder, name, codes in acts.CONS: put('cons', key, folder, name, codes.split(), name, 'cons')
# --- копии из собранных баз (акты там скачаны и сверены 14–15.11.2026)
A = 'Административная деятельность полиции/2. Источники/1. Нормативные правовые акты/'; K = 'Криминалистика/2. Источники/1. Нормативные правовые акты/'
COPY = [(c, K + '1. Конституция РФ/Конституция РФ*.pdf', 1, 'Криминалистика', 'официальный текст с изменениями, опубликован 06.10.2022 (publication.pravo.gov.ru); скан без текстового слоя') for c in DISC]
COPY += [('upp', K + '5. Ведомственные акты/Приказ МВД России № 776 и др. от 27.09.2013*.pdf', 5, 'Криминалистика', 'действует, изменений нет (consultant.ru, 15.11.2026)'),
         ('tsp', A + '7. Приказы МВД России/*28.06.2021 № 495 Наставление ППСП*.pdf', 5, 'АДП', 'действует с изм. от 14.08.2024; текст изменений в открытых источниках не найден'),
         ('tsp', A + '7. Приказы МВД России/*25.11.2019 № 879 Наставление*.pdf', 5, 'АДП', 'действие по открытым источникам не подтверждено'),
         ('tsp', A + '7. Приказы МВД России/*01.04.2021 № 191 *.pdf', 5, 'АДП', 'действие по открытым источникам не подтверждено'),
         ('tsp', A + '7. Приказы МВД России/*27.09.2024 № 575 *.pdf', 5, 'АДП', 'действие по открытым источникам не подтверждено'),
         ('tsp', A + '7. Приказы МВД России/*17.11.2015 № 1092 *.pdf', 5, 'АДП', ''), ('tsp', A + '7. Приказы МВД России/*02.02.2024 № 44 *.pdf', 5, 'АДП', ''),
         ('tsp', A + '8. Акты иных ведомств/Приказ МВД России № 652, Росгвардии № 360*.pdf', 5, 'АДП', ''), ('tsp', A + '8. Акты иных ведомств/Приказ Росгвардии № 216, МВД России № 440*.pdf', 5, 'АДП', '')]
for code, pat, folder, base, note in COPY:
    for src in sorted(glob.glob(pat)):
        name = os.path.basename(src); d = S(code) + FOLD[folder]; os.makedirs(d, exist_ok=True)
        if not os.path.exists(d + name): shutil.copyfile(src, d + name)
        h = os.path.dirname(src) + '/' + H + name[:-4] + '.html'
        if os.path.exists(h):
            os.makedirs(d + H, exist_ok=True)
            if not os.path.exists(d + H + name[:-4] + '.html'): shutil.copyfile(h, d + H + name[:-4] + '.html')
        MAN[(code, 'copy:' + name)] = dict(code=code, key='copy:' + name, grp='copy', folder=FOLD[folder], name=name, site='из базы «%s»' % base, url='', edition=note, state='', checked='15.11.2026',
                                           sha=sha(d + name), topic='', html=os.path.exists(h), base=base)
json.dump(sorted(MAN.values(), key=lambda m: (m['code'], m['folder'], m['name'])), open(MP, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
DP = D5 + 'acts_dropped.json'   # исходные файлы после раскладки удаляются; причина, записанная раньше, сохраняется
OLD = {d['key']: d for d in (json.load(open(DP, encoding='utf-8')) if os.path.exists(DP) else [])}
for d in DROP:
    if d['why'] == 'не получен' and d['key'] in OLD: d['why'] = OLD[d['key']]['why']
if DROP: json.dump(DROP, open(DP, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
import collections
print('записей:', len(MAN), dict(collections.Counter(m['code'] for m in MAN.values())))
for d in DROP: print('  не взят:', d['key'], '|', d['why'], '|', d['name'][:70])
print('макс. длина имени, байт:', max(len(m['name'].encode()) for m in MAN.values()))
