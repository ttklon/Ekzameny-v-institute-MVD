#!/usr/bin/env python3
"""Этап 1 сбора источников (нормативные правовые акты): по каталогу catalog.txt, привязке map/*.txt и журналам
загрузчика строит в папке «2. Источники» каждой из двух дисциплин:
  — раздел «А. Нормативные правовые акты» в «Реестр источников.md» (между метками NPA-BEGIN / NPA-END);
  — «Нормативные правовые акты по вопросам.md» (под каждым вопросом — все акты, нужные для ответа);
  — «Контрольные суммы SHA-256.txt».
Запуск: python3 build_registry.py [--fix]
  --fix — пересчитать отметки дисциплин в каталоге по привязке и удалить из папок файлы актов, которых нет в каталоге."""
import csv, glob, hashlib, json, os, re, sys
import make_shards as m

csv.field_size_limit(10 ** 9)
TODAY = '27.11.2026'
HERE, ROOT = m.HERE, m.ROOT
PARTS = {'G': ('gai', 15), 'S': ('sb', 13)}
NPA = '2. Источники/1. Нормативные правовые акты'
FIX = '--fix' in sys.argv


def sha(f):
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ---------- привязка вопросов к актам ----------
def questions(d):
    """[(номер раздела, название раздела, [(сквозной номер, текст, [коды])])]"""
    code, nparts = PARTS[d]
    out, n = [], 0
    for p in range(1, nparts + 1):
        mp = {}
        for l in open(os.path.join(HERE, 'map', '%s-%02d.txt' % (code, p)), encoding='utf-8'):
            if l.strip():
                q, _, cs = l.rstrip('\n').partition('\t')
                mp[int(q)] = [c for c in cs.split(', ') if c and c != '—']   # «—» — вопрос без нормативных актов (история)
        name, qs, k = '', [], 0
        for l in open(os.path.join(ROOT, '.github', 'answers', code, 'parts', '%02d.txt' % p), encoding='utf-8'):
            l = l.strip()
            if not l:
                continue
            if l.startswith('#'):
                name = l.lstrip('# ').strip()
                continue
            k += 1
            n += 1
            qs.append((n, l, mp.get(k, [])))
        assert len(mp) == k, (code, p, len(mp), k)
        out.append((p, name, qs))
    return out


QUEST = {d: questions(d) for d in 'GS'}
USED = {}
for d in 'GS':
    for _, _, qs in QUEST[d]:
        for n, _, cs in qs:
            for c in cs:
                USED.setdefault(c, {}).setdefault(d, []).append(n)

rows = m.catalog()
if FIX:
    lines, changed = [], 0
    for l in open(os.path.join(HERE, 'catalog.txt'), encoding='utf-8').read().splitlines():
        if l and not l.startswith('#'):
            f = l.split('|')
            want = ''.join(d for d in 'GS' if d in USED.get(f[0], {}))
            if want and want != f[4]:
                f[4] = want
                changed += 1
                l = '|'.join(f)
        lines.append(l)
    open(os.path.join(HERE, 'catalog.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('отметок дисциплин исправлено:', changed)
    rows = m.catalog()
CAT = {r['code']: r for r in rows}
unknown = sorted(c for c in USED if c not in CAT)
if unknown:
    print('коды привязки, которых нет в каталоге:', ' '.join(unknown))

# ---------- журналы загрузчика: по SHA-256 файла находим, откуда он взят ----------
LOGS = {}
for f in [os.path.join(ROOT, '.github/downloader/log.tsv')] + sorted(glob.glob(os.path.join(ROOT, '.github/downloader/logs/*.tsv'))):
    if not os.path.exists(f):
        continue
    for row in csv.reader(open(f, encoding='utf-8', newline=''), delimiter='\t'):
        if len(row) >= 9 and row[4] == 'ok' and row[8]:
            LOGS[row[8]] = row
CARDS = {}


def card(nd):
    if nd not in CARDS:
        p = os.path.join(ROOT, '.work', 'cards', nd + '.json')
        CARDS[nd] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
    return CARDS[nd]


def describe(f):
    """(источник в виде ссылки, что в файле, замечание для проверки)"""
    link, text, note = describe0(f)
    # отметки сайта на исходной странице: утрата силы, подготовленная будущая редакция
    h = os.path.join(os.path.dirname(f), 'Исходные страницы (HTML)', os.path.basename(f)[:-4] + '.html')
    if os.path.exists(h):
        page = open(h, encoding='utf-8', errors='replace').read()
        if 'Документ утратил силу или отмен' in page:
            note = (note + '; ' if note else '') + 'на сайте отметка: документ утратил силу или отменён'
        if 'с изменениями, не вступившими в силу' in page:
            text += '. На сайте отметка: подготовлена редакция с изменениями, не вступившими в силу (в файл не включены)'
    if LOST.get(os.path.basename(f)):
        note = (note + '; ' if note else '') + LOST[os.path.basename(f)]
    return link, text, note


LOST = {}


def describe0(f):
    row = LOGS.get(sha(f))
    if not row:
        return 'нет записи в журнале загрузчика', 'файл скопирован из папки другой дисциплины; редакция не установлена', 'нет записи в журнале'
    op, url, typ = row[1], row[2], row[7]
    host = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    link = '[%s](%s)' % (host, url)
    day = row[0][:10]
    day = '%s.%s.%s' % (day[8:10], day[5:7], day[:4])
    if op in ('ipsact', 'ips', 'ipswide'):
        nd = re.search(r'nd=(\d+)', url)
        rdk = re.search(r'rdk=(\d+)', url)
        c = card(nd.group(1)) if nd else None
        if not c:
            return link, 'текст государственной системы «Законодательство России», загружен %s; сведений о редакции нет' % day, 'нет карточки'
        note = ''
        if 'тратил' in (c.get('state') or '') or 'действует' in (c.get('state') or '').lower() and 'не действует' in (c.get('state') or '').lower():
            note = 'по карточке: ' + c['state']
        reds = c.get('redactions') or []
        act = [r for r in reds if r.get('actual')]
        if rdk and act and str(act[0]['id']) != rdk.group(1):
            note = (note + '; ' if note else '') + 'загружена не актуальная редакция'
        if not act:
            return link, 'редакция не определена (в карточке нет актуальной редакции), загружен %s' % day, note or 'нет актуальной редакции'
        a = act[0]
        if len(reds) == 1 or not a.get('refadoption'):
            text = 'первоначальный текст, изменений нет'
        else:
            text = 'редакция, действующая с %s' % a['date']
        future = [r for r in reds if r.get('status') == 'не вступившая в силу']
        if future:
            text += '. Ещё не вступили в силу изменения: ' + '; '.join(
                'с %s — %s' % (r['date'], re.sub(r'^.*? от ', 'от ', r.get('refadoption') or '')) for r in future)
        return link, text, note
    if op in ('get', 'pub') and 'publication.pravo.gov.ru' in url:
        return link, 'скан официального опубликования; текст на дату опубликования', ''
    title = ''
    for part in typ.split('; '):
        if re.search(r'\bN\b|ГОСТ|Конвенц|Соглашени|кодекс|План|рекомендац|Письмо', part) and not part.startswith('html sha'):
            title = part
            break
    red = re.search(r'\((ред\. от [\d.]+|с изм\. от [\d.]+|ред\. от [\d.]+, с изм\. от [\d.]+)[^)]*\)', title)
    if red:
        text = 'текст в ' + red.group(1).replace('ред. от', 'редакции от').replace('с изм. от', 'с изменениями от') if red.group(1).startswith('ред') \
            else 'текст ' + red.group(1).replace('с изм. от', 'с изменениями от')
    elif title:
        text = 'текст без отметки о редакции (изменения на сайте не указаны)'
    elif op == 'kontur':
        k = re.search(r'Редакция от ([\d.]+)', typ)
        text = 'текст в редакции от ' + k.group(1) if k else 'текст с сайта, редакция не указана'
    else:
        text = 'текст с сайта, редакция не указана'
    text += '; загружен %s' % day
    return link, text, ''


# ---------- по дисциплинам ----------
def label(r):
    return m.filename(r)[:-4]


summary = {}
for d in 'GS':
    base = os.path.join(ROOT, m.DISC[d], NPA)
    mine = [r for r in rows if d in r['disc']]
    want = {m.path(r, d) for r in mine}
    # лишние файлы (актов нет в каталоге этой дисциплины)
    extra = []
    for f in glob.glob(os.path.join(glob.escape(base), '*', '*.pdf')):
        if os.path.relpath(f, ROOT) not in want:
            extra.append(f)
    for f in extra:
        print('лишний файл:', os.path.relpath(f, base))
        if FIX:
            os.remove(f)
            h = os.path.join(os.path.dirname(f), 'Исходные страницы (HTML)', os.path.basename(f)[:-4] + '.html')
            if os.path.exists(h):
                os.remove(h)
    table, missing, notes, have = [], [], [], {}
    for r in sorted(mine, key=lambda r: (m.FOLD[r['kind'].split(':')[0]], m.filename(r))):
        f = os.path.join(ROOT, m.path(r, d))
        fold = m.FOLD[r['kind'].split(':')[0]]
        if os.path.exists(f) and os.path.getsize(f) > 0:
            link, text, note = describe(f)
            have[r['code']] = True
            table.append('| %s | %s | %s | %s |' % (fold, m.filename(r), link, text))
            if note:
                notes.append('%s — %s' % (label(r), note))
        else:
            missing.append(r)
    nq = sum(len(qs) for _, _, qs in QUEST[d])
    noact = [n for _, _, qs in QUEST[d] for n, _, cs in qs if not cs]
    partial = [n for _, _, qs in QUEST[d] for n, _, cs in qs if any(c not in have for c in cs)]
    summary[d] = dict(total=len(mine), have=len(table), missing=missing, notes=notes, nq=nq, noact=noact, partial=partial)

    # --- реестр ---
    counts = {}
    for t in table:
        counts[t.split(' | ')[0][2:]] = counts.get(t.split(' | ')[0][2:], 0) + 1
    reg = ['<!-- NPA-BEGIN -->', '## А. Нормативные правовые акты (этап 1 сбора источников)', '',
           'Состояние на %s. По перечню из %d вопросов отобрано **%d актов**; тексты получены для **%d**, не получены для %d (список — в разделе А.2).'
           % (TODAY, nq, len(mine), len(table), len(missing)),
           '', 'По папкам: ' + '; '.join('%s — %d' % (k, v) for k, v in sorted(counts.items())) + '.', '',
           'Какие акты нужны для каждого вопроса — файл «Нормативные правовые акты по вопросам.md». Контрольные суммы файлов — «Контрольные суммы SHA-256.txt». '
           'Исходные страницы сайтов, с которых сделаны PDF, лежат в подпапках «Исходные страницы (HTML)» под тем же названием.', '',
           'Откуда взяты тексты и что означает графа «Что в файле»:', '',
           '- **ips.pravo.gov.ru** — государственная система «Законодательство России»: кодексы, законы, указы, акты Правительства РФ. Загружалась редакция, которую система помечает как актуальную; дата в графе — день, с которого эта редакция действует. Изменения, принятые, но ещё не вступившие в силу, в текст не включены и перечислены отдельно.',
           '- **publication.pravo.gov.ru** — скан официального опубликования (Конституция РФ).',
           '- **sudact.ru** и **consultant.ru** — ведомственные акты, международные договоры, стандарты, письма: в «Законодательстве России» их текстов нет. Редакция указана так, как она названа в заголовке документа на сайте; это неофициальные тексты, по официальному опубликованию они не сверены.',
           '- Файлы не читались целиком: проверены реквизиты в заголовке, наличие текста и отметка о редакции. Постатейная сверка — при составлении ответов.', '',
           '### А.1. Файлы', '', '| Папка | Файл | Откуда | Что в файле |', '|---|---|---|---|'] + table + ['', '### А.2. Тексты не получены', '']
    if missing:
        reg += ['| Акт | Нужен для вопросов | Почему нет текста |', '|---|---|---|']
        why = {}
        wf = os.path.join(HERE, 'missing.tsv')
        if os.path.exists(wf):
            for l in open(wf, encoding='utf-8'):
                if l.strip() and not l.startswith('#'):
                    c, w = l.rstrip('\n').split('\t')
                    why[c] = w
        for r in missing:
            qs = USED.get(r['code'], {}).get(d, [])
            reg.append('| %s | %s | %s |' % (label(r), ', '.join(map(str, qs)) or 'общий акт, к отдельным вопросам не привязан', why.get(r['code'], 'не загружен')))
    else:
        reg.append('Таких актов нет.')
    if notes:
        reg += ['', '### А.3. Что проверить в файлах', ''] + ['- ' + n for n in notes]
    extra_md = os.path.join(HERE, 'registry-%s.md' % PARTS[d][0])
    if os.path.exists(extra_md):
        reg += ['', open(extra_md, encoding='utf-8').read().rstrip('\n')]
    reg.append('<!-- NPA-END -->')
    rp = os.path.join(ROOT, m.DISC[d], '2. Источники', 'Реестр источников.md')
    s = open(rp, encoding='utf-8').read()
    block = '\n'.join(reg)
    if '<!-- NPA-BEGIN -->' in s:
        s = re.sub(r'<!-- NPA-BEGIN -->.*?<!-- NPA-END -->', lambda _: block, s, flags=re.S)
    else:
        head, sep, rest = s.partition('\n## ')
        s = head.rstrip('\n') + '\n\n' + block + '\n\n## ' + rest
    open(rp, 'w', encoding='utf-8').write(s)

    # --- акты по вопросам ---
    out = ['# Нормативные правовые акты по вопросам', '',
           'Состояние на %s. Дисциплина — %s, %d вопросов примерного перечня. Этап 1 сбора источников: только нормативные правовые акты '
           '(судебная практика, учебная литература, научные и эмпирические материалы — следующие этапы).' % (TODAY, m.DISC[d][0].lower() + m.DISC[d][1:], nq), '',
           'Всего отобрано %d актов, тексты есть для %d. Папка с файлами — «1. Нормативные правовые акты»; откуда взят каждый файл и в какой редакции — «Реестр источников.md», раздел А.' % (len(mine), len(table)), '',
           '## Как читать этот файл', '',
           '- Под каждым вопросом названы все акты, нормы которых нужны для ответа. Название акта совпадает с названием файла (без «.pdf»); папка указана в скобках номером: 1 — Конституция РФ, 2 — федеральные конституционные законы, 3 — кодексы, 4 — федеральные законы и законы РФ, 5 — указы Президента РФ, 6 — акты Правительства РФ, 7 — приказы МВД России, 8 — акты иных ведомств, международные договоры, стандарты.',
           '- Привязка сделана по формулировке вопроса и по предмету регулирования акта. Тексты актов при этом постатейно не читались: конкретные статьи и пункты подбираются при составлении ответа.',
           '- Пометка «текста в базе нет» означает, что акт для ответа нужен, но получить его текст не удалось (причина — в реестре, раздел А.2).',
           '- Вопросы раздела о судебной практике привязаны к актам, которые применяют суды; сами судебные решения собираются на следующем этапе.', '']
    if summary[d]['partial']:
        out += ['Вопросов, для которых в базе нет текста хотя бы одного акта: %d.' % len(summary[d]['partial']), '']
    if noact:
        out += ['Вопросы, для ответа на которые нормативные акты не нужны (история службы): ' + ', '.join(map(str, noact)) + '.', '']
    for p, name, qs in QUEST[d]:
        out += ['## Раздел %d. %s' % (p, name), '']
        for n, text, cs in qs:
            out.append('**%d. %s**' % (n, text))
            out.append('')
            if not cs:
                out.append('- нормативные акты не нужны (вопрос об истории)')
            for c in cs:
                r = CAT.get(c)
                if not r:
                    out.append('- %s — акт не определён' % c)
                    continue
                fold = m.FOLD[r['kind'].split(':')[0]].split('.')[0]
                out.append('- %s (%s)%s' % (label(r), fold, '' if c in have else ' — текста в базе нет'))
            out.append('')
    free = [r for r in mine if d not in USED.get(r['code'], {})]
    if free:
        out += ['## Акты, не привязанные к отдельным вопросам', '',
                'Эти акты лежат в базе как общие (к ним отсылают другие акты перечня), под вопросами они не названы.', '']
        out += ['- %s (%s)%s' % (label(r), m.FOLD[r['kind'].split(':')[0]].split('.')[0], '' if r['code'] in have else ' — текста в базе нет') for r in free] + ['']
    open(os.path.join(ROOT, m.DISC[d], '2. Источники', 'Нормативные правовые акты по вопросам.md'), 'w', encoding='utf-8').write('\n'.join(out))

    # --- контрольные суммы ---
    src = os.path.join(ROOT, m.DISC[d], '2. Источники')
    sums = []
    for dp, dn, fn in os.walk(src):
        for f in fn:
            if f in ('Контрольные суммы SHA-256.txt', '.gitkeep'):
                continue
            full = os.path.join(dp, f)
            sums.append((os.path.relpath(full, src), sha(full)))
    sums.sort()
    open(os.path.join(src, 'Контрольные суммы SHA-256.txt'), 'w', encoding='utf-8').write(''.join('%s  %s\n' % (h, p) for p, h in sums))
    print('%s: актов %d, с текстом %d, без текста %d (%s); вопросов %d, без актов %d, с неполным набором %d; замечаний %d' % (
        d, len(mine), len(table), len(missing), ' '.join(r['code'] for r in missing), nq, len(noact), len(summary[d]['partial']), len(notes)))
    for x in notes:
        print('   !', x)
