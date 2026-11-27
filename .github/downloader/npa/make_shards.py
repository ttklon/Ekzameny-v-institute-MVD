#!/usr/bin/env python3
"""Строит списки заданий загрузчика (.github/downloader/shards/*.tsv) по каталогу актов catalog.txt.
Запуск: python3 make_shards.py <префикс списков> [код ...]  — без кодов берутся все акты каталога."""
import sys, os, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DISC = {'G': 'Деятельность Госавтоинспекции', 'S': 'Обеспечение собственной безопасности органов внутренних дел'}
FOLD = {'КОН': '1. Конституция РФ', 'ФКЗ': '2. Федеральные конституционные законы', 'КОД': '3. Кодексы',
        'ФЗ': '4. Федеральные законы и законы РФ', 'ЗРФ': '4. Федеральные законы и законы РФ', 'У': '5. Указы Президента РФ',
        'П': '6. Постановления Правительства РФ', 'Р': '6. Постановления Правительства РФ', 'М': '7. Приказы МВД России', 'В': '8. Акты иных ведомств'}
ADOPT = {'ФКЗ': 'Федеральный конституционный закон', 'КОД': 'Федеральный закон', 'ФЗ': 'Федеральный закон', 'ЗРФ': 'Закон Российской Федерации',
         'У': 'Указ Президента Российской Федерации', 'П': 'Постановление Правительства Российской Федерации',
         'Р': 'Распоряжение Правительства Российской Федерации'}
NAME = {'ФКЗ': 'ФКЗ', 'ФЗ': 'ФЗ', 'ЗРФ': 'Закон РФ', 'У': 'Указ Президента РФ', 'П': 'Постановление Правительства РФ',
        'Р': 'Распоряжение Правительства РФ', 'М': 'Приказ МВД России'}


def catalog():
    rows = []
    for l in open(os.path.join(HERE, 'catalog.txt'), encoding='utf-8'):
        l = l.rstrip('\n')
        if not l or l.startswith('#'):
            continue
        code, kind, date, num, disc, title = l.split('|')
        rows.append(dict(code=code, kind=kind, date=date, num=num, disc=disc, title=title))
    return rows


def filename(r):
    k = r['kind'].split(':')[0]
    if k == 'КОН':
        return 'Конституция РФ (официальный текст с изменениями, опубликован 06.10.2022).pdf'
    if k == 'КОД':
        return '%s от %s № %s.pdf' % (r['title'], r['date'], r['num'])
    head = NAME[k] if k != 'В' else r['kind'].split(':', 1)[1]
    base = '%s от %s № %s ' % (head, r['date'], r['num'])
    title = r['title'].replace('«', '').replace('»', '')
    # имя файла в Linux — не длиннее 255 байт; оставляем запас для служебных расширений загрузчика
    while len((base + title).encode('utf-8')) > 226:
        title = title.rsplit(' ', 1)[0].rstrip(' ,—-(')
    return base + title + '.pdf'


def path(r, d):
    return '%s/2. Источники/1. Нормативные правовые акты/%s/%s' % (DISC[d], FOLD[r['kind'].split(':')[0]], filename(r))


def task(r, d):
    k = r['kind'].split(':')[0]
    if k == 'КОН':
        return 'get\thttp://publication.pravo.gov.ru/file/pdf?eoNumber=0001202210060013\t' + path(r, d)
    if k in ADOPT:
        adoption = '%s от %s № %s' % (ADOPT[k], r['date'], r['num'])
        url = 'http://ips.pravo.gov.ru/api/ips/legislation/search.json?query=%s&limit=10&page=1' % urllib.parse.quote_plus(adoption)
        return 'ipsact\t%s#%s\t%s' % (url, adoption, path(r, d))
    head = 'Приказ МВД России' if k == 'М' else r['kind'].split(':', 1)[1].split(',')[0]
    return 'consauto\t%s от %s N %s#от %s N %s\t%s' % (head, r['date'], r['num'], r['date'], r['num'], path(r, d))


if __name__ == '__main__':
    prefix, codes = sys.argv[1], set(sys.argv[2:])
    ips, cons = [], []
    for r in catalog():
        if codes and r['code'] not in codes:
            continue
        k = r['kind'].split(':')[0]
        if k in ('М', 'В'):
            cons.append(task(r, r['disc'][0]))          # ведомственный акт загружается один раз, во вторую папку копируется
        else:
            ips += [task(r, d) for d in r['disc']]
    out = os.path.join(ROOT, '.github', 'downloader', 'shards')
    os.makedirs(out, exist_ok=True)
    def split(rows, n, tag):
        for i in range(n):
            part = rows[i::n]
            if part:
                open(os.path.join(out, '%s_%s%d.tsv' % (prefix, tag, i + 1)), 'w', encoding='utf-8').write('\n'.join(part) + '\n')
    split(ips, max(1, min(4, len(ips) // 40 + 1)), 'ips')
    split(cons, max(1, min(3, len(cons) // 12 + 1)), 'cons')
    print('ips', len(ips), 'cons', len(cons))
