#!/usr/bin/env python3
"""Судебная практика (этап 2): по каталогу catalog.txt и привязке map.tsv собирает
  — раздел «Судебная практика» в «Реестр источников.md» (между метками SP-BEGIN / SP-END, сразу после раздела актов);
  — «2. Судебная практика/Судебная практика по вопросам.md» (вступление и позиции — из positions-<gai|sb>.md);
  — «Контрольные суммы SHA-256.txt».
Запуск: python3 build.py"""
import os, re, csv, glob, hashlib, sys
from pypdf import PdfReader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make as m

TODAY = '28.11.2026'
ROOT, HERE = m.ROOT, m.HERE
PARTS = {'G': 'gai', 'S': 'sb'}
KINDS = [('КП', ('постановление Конституционного Суда РФ', 'постановления Конституционного Суда РФ', 'постановлений Конституционного Суда РФ')),
         ('КО', ('определение Конституционного Суда РФ', 'определения Конституционного Суда РФ', 'определений Конституционного Суда РФ')),
         ('ПЛ', ('постановление Пленума Верховного Суда РФ', 'постановления Пленума Верховного Суда РФ', 'постановлений Пленума Верховного Суда РФ')),
         ('ОН', ('обзор судебной практики Верховного Суда РФ', 'обзора судебной практики Верховного Суда РФ', 'обзоров судебной практики Верховного Суда РФ')),
         ('ОТ', ('тематический обзор Президиума Верховного Суда РФ', 'тематических обзора Президиума Верховного Суда РФ', 'тематических обзоров Президиума Верховного Суда РФ'))]


def sha(f):
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


LOGS = {}
for f in [os.path.join(ROOT, '.github/downloader/log.tsv')] + sorted(glob.glob(os.path.join(ROOT, '.github/downloader/logs/*.tsv'))):
    for row in csv.reader(open(f, encoding='utf-8', newline=''), delimiter='\t'):
        if len(row) >= 9 and row[4] == 'ok' and row[8]:
            LOGS[row[8]] = row


def tsv(name):
    p, out = os.path.join(HERE, name), []
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            if l.strip() and not l.startswith('#'):
                out.append(l.rstrip('\n').split('\t'))
    return out


def questions(d):
    """{часть: [(сквозной номер, номер в части, текст)]}"""
    res, n = {}, 0
    for f in sorted(glob.glob(os.path.join(ROOT, '.github/answers', PARTS[d], 'parts', '*.txt'))):
        part = os.path.basename(f)[:2]
        k = 0
        for l in open(f, encoding='utf-8'):
            if l.strip() and not l.startswith('#'):
                n += 1
                k += 1
                res.setdefault(part, []).append((n, k, l.strip()))
    return res


def label(r):
    k = r['kind']
    if k == 'КП':
        return 'Постановление Конституционного Суда РФ от %s № %s' % (r['date'], r['num'])
    if k == 'КО':
        return 'Определение Конституционного Суда РФ от %s № %s' % (r['date'], r['num'])
    if k == 'ПЛ':
        return 'Постановление Пленума Верховного Суда РФ от %s № %s' % (r['date'], r['num'])
    if k == 'ОН':
        return 'Обзор судебной практики Верховного Суда РФ %s (утверждён Президиумом %s)' % (r['num'], r['date'])
    return 'Обзор практики Верховного Суда РФ от %s' % r['date']


def about(r):
    return r['topic'] if r['kind'] != 'ОН' else ''


def inspect(f):
    """(источник-ссылка, что в файле, страниц, знаков, замечание)"""
    row = LOGS.get(sha(f))
    rd = PdfReader(f)
    text = ' '.join(' '.join((p.extract_text() or '') for p in rd.pages).split())
    note = ''
    if len(text) < 3000:
        note = 'в файле мало текста (%d знаков)' % len(text)
    if row:
        url = row[2].split('#')[0]
        site = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
        link = '[%s](%s)' % (site, url)
        saved = row[0][:10]
        saved = '%s.%s.%s' % (saved[8:10], saved[5:7], saved[:4])
    else:
        link, saved, site = 'нет записи в журнале', '', ''
        note = (note + '; ' if note else '') + 'нет записи в журнале загрузки'
    ed = re.search(r'\(ред\. от (\d\d\.\d\d\.\d{4})\)', text[:900])
    ed2 = re.search(r'Редакция от (\d\d\.\d\d\.\d{4})', text[:400])
    if ed:
        what = 'редакция от %s' % ed.group(1)
    elif ed2:
        what = 'редакция от %s (по отметке сайта)' % ed2.group(1)
    elif 'consultant' in site:
        what = 'изменений в названии документа на сайте не указано'
    else:
        what = 'текст решения'
    if saved:
        what += '; сохранено %s' % saved
    return link, what, len(rd.pages), len(text), note


def plural(n, forms):
    one, few, many = forms
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def main():
    rows = m.catalog()
    CAT = {r['code']: r for r in rows}
    MAP = {}
    for d, q, codes in tsv('map.tsv'):
        part, k = q.split(':')
        cs = [] if codes.strip() == '—' else [c.strip() for c in codes.split(',')]
        for c in cs:
            assert c in CAT, (d, q, c)
            assert d in CAT[c]['disc'], ('акт не отнесён к дисциплине', d, q, c)
        MAP[(d, part, int(k))] = cs
    MANUAL = {c: (src, t) for c, src, t in tsv('manual.tsv')}
    NOTES = {}
    for c, t in tsv('notes.tsv'):
        NOTES.setdefault(c, []).append(t)
    MISSING = tsv('missing.tsv')
    for d in 'GS':
        mine = [r for r in rows if d in r['disc']]
        have, table, notes = [], [], []
        for r in mine:
            f = m.path(r, d)
            if not os.path.exists(f):
                notes.append('%s — файла нет' % label(r))
                continue
            link, what, pages, chars, note = inspect(f)
            if r['code'] in MANUAL and 'нет записи' in link:
                link, what, note = MANUAL[r['code']][0], MANUAL[r['code']][1], note.replace('нет записи в журнале загрузки', '').strip('; ')
            have.append(r)
            table.append('| %s | %s | %s | %s | %d |' % (m.FOLD[r['kind']].split('.')[0], os.path.basename(f), link, what, pages))
            for t in ([note] if note else []) + NOTES.get(r['code'], []):
                notes.append('%s — %s' % (label(r), t))
        used = {c for (dd, p, k), cs in MAP.items() if dd == d for c in cs}
        cnt = [(sum(1 for r in have if r['kind'] == k), nm) for k, nm in KINDS]
        counts = ', '.join('%d %s' % (c[0], plural(c[0], c[1])) for c in cnt if c[0])
        Q = questions(d)
        mapped = [(p, k) for (dd, p, k) in MAP if dd == d]
        empty = [(p, k) for (dd, p, k), cs in MAP.items() if dd == d and not cs]

        # --- раздел реестра ---
        reg = ['<!-- SP-BEGIN -->', '## Судебная практика (этап 2 сбора источников)', '',
               'Состояние на %s. В папке `2. Судебная практика` — **%d %s**: %s. '
               'Какой акт к какому вопросу относится и что в нём главное — в файле `2. Судебная практика/Судебная практика по вопросам.md`.'
               % (TODAY, len(have), plural(len(have), ('акт', 'акта', 'актов')), counts), '',
               'Решения Конституционного Суда РФ взяты с ips.pravo.gov.ru («Законодательство России»), постановления Пленума и обзоры — '
               'с consultant.ru (некоммерческая интернет-версия) или из «Контур.Норматив»; рядом с каждым PDF в папке '
               '`Исходные страницы (HTML)` лежит страница сайта в том виде, в каком она получена. Файлы, уже имевшиеся в базах '
               'других дисциплин репозитория, скопированы оттуда без повторной загрузки (дата сохранения указана в таблице).', '',
               '### СП.1. Файлы', '',
               '| Папка | Файл | Источник | Что в файле | Стр. |', '|---|---|---|---|---|'] + table + ['']
        reg += ['### СП.2. Чего в базе нет', '']
        miss = [x for x in MISSING if d in x[0]]
        reg += ['- %s — %s' % (x[1], x[2]) for x in miss] or ['- Все отобранные акты получены.']
        reg += ['', '### СП.3. Что проверить и какие оговорки нужны', '']
        reg += ['- %s' % x for x in notes] + ['- %s' % x[1] for x in tsv('common.tsv') if d in x[0]]
        reg += ['', '<!-- SP-END -->']
        rp = os.path.join(ROOT, m.DISC[d], '2. Источники', 'Реестр источников.md')
        s = open(rp, encoding='utf-8').read()
        block = '\n'.join(reg)
        if '<!-- SP-BEGIN -->' in s:
            s = re.sub(r'<!-- SP-BEGIN -->.*?<!-- SP-END -->', lambda _: block, s, flags=re.S)
        else:
            s = s.replace('<!-- NPA-END -->', '<!-- NPA-END -->\n\n' + block, 1)
        open(rp, 'w', encoding='utf-8').write(s)

        # --- акты по вопросам ---
        nq = sum(len(v) for v in Q.values())
        out = ['# Судебная практика по вопросам экзамена', '',
               'Дисциплина: «%s». Состояние на %s.' % (m.DISC[d], TODAY), '',
               'В папке `2. Судебная практика` лежат %d %s: %s. Откуда взят каждый файл и в какой он редакции — в `Реестр источников.md`, раздел «Судебная практика».'
               % (len(have), plural(len(have), ('акт', 'акта', 'актов')), counts), '']
        pos = os.path.join(HERE, 'positions-%s.md' % PARTS[d])
        out += [open(pos, encoding='utf-8').read().rstrip('\n'), '']
        out += ['## 2. Акты по вопросам', '',
                'Из %d вопросов перечня судебная практика нужна прежде всего для %d: это раздел о судебной практике и отдельные вопросы других разделов. '
                'Номер перед вопросом — сквозной номер по перечню. По остальным вопросам судебные акты не подбирались.' % (nq, len(mapped)), '']
        for part in sorted(Q):
            qs = [(n, k, t) for n, k, t in Q[part] if (d, part, k) in MAP]
            if not qs:
                continue
            out += ['### Раздел %d' % int(part), '']
            for n, k, t in qs:
                out += ['**%d. %s**' % (n, t), '']
                cs = MAP[(d, part, k)]
                if not cs:
                    out.append('- актов Конституционного Суда РФ, Пленума и Президиума Верховного Суда РФ, посвящённых этому вопросу, в базе нет (см. раздел 3)')
                for c in cs:
                    r = CAT[c]
                    a = about(r)
                    out.append('- %s%s (папка %s)%s' % (label(r), ' — ' + a if a else '', m.FOLD[r['kind']].split('.')[0],
                                                       '' if r in have else ' — текста в базе нет'))
                out.append('')
        free = [r for r in have if r['code'] not in used]
        if free:
            out += ['### Акты, не привязанные к отдельным вопросам', ''] + ['- %s%s' % (label(r), ' — ' + about(r) if about(r) else '') for r in free] + ['']
        out += ['## 3. Чего в базе нет и какие оговорки нужны', '']
        out += ['- %s — %s' % (x[1], x[2]) for x in miss]
        out += ['- %s' % x[1] for x in tsv('common.tsv') if d in x[0]]
        out += ['']
        open(os.path.join(ROOT, m.DISC[d], m.SP, 'Судебная практика по вопросам.md'), 'w', encoding='utf-8').write('\n'.join(out))

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
        print('%s: актов в каталоге %d, файлов %d (%s); вопросов с подборкой %d, из них без актов %d; не привязано актов %d; замечаний %d'
              % (d, len(mine), len(have), counts, len(mapped), len(empty), len(free), len(notes)))
        for x in notes:
            print('   !', x[:200])
        for r in free:
            print('   ? не привязан:', r['code'])


if __name__ == '__main__':
    main()
