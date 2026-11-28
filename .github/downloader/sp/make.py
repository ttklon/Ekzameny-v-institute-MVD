#!/usr/bin/env python3
"""Судебная практика (этап 2): по каталогу catalog.txt копирует уже имеющиеся в репозитории акты в папки двух
дисциплин и строит задания загрузчика для недостающих.
Запуск: python3 make.py copy            — скопировать имеющиеся (PDF и исходную страницу), разнести между дисциплинами;
        python3 make.py shards <префикс> — записать задания для актов, которых нет нигде в репозитории;
        python3 make.py list            — показать, что есть и чего нет."""
import sys, os, glob, shutil, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DISC = {'G': 'Деятельность Госавтоинспекции', 'S': 'Обеспечение собственной безопасности органов внутренних дел'}
SP = '2. Источники/2. Судебная практика'
FOLD = {'КП': '1. Конституционный Суд РФ', 'КО': '1. Конституционный Суд РФ', 'ПЛ': '2. Пленум Верховного Суда РФ',
        'ОН': '3. Обзоры и иные акты Верховного Суда РФ', 'ОТ': '3. Обзоры и иные акты Верховного Суда РФ'}
HTML = 'Исходные страницы (HTML)'


def catalog():
    rows = []
    for l in open(os.path.join(HERE, 'catalog.txt'), encoding='utf-8'):
        if not l.strip() or l.startswith('#'):
            continue
        p = l.rstrip('\n').split('|') + ['']
        rows.append(dict(code=p[0], kind=p[1], date=p[2], num=p[3], disc=p[4], topic=p[5], query=p[6]))
    return rows


def head(r):
    """Начало имени файла, по которому акт узнаётся в любой папке репозитория."""
    k = r['kind']
    if k == 'КП':
        return 'Постановление КС РФ от %s № %s' % (r['date'], r['num'])
    if k == 'КО':
        return 'Определение КС РФ от %s № %s' % (r['date'], r['num'])
    if k == 'ПЛ':
        return 'Постановление Пленума ВС РФ от %s № %s' % (r['date'], r['num'])
    if k == 'ОН':
        return 'Обзор судебной практики ВС РФ %s' % r['num']
    return 'Обзор практики ВС РФ от %s' % r['date']


def name(r):
    k = r['kind']
    if k == 'ОН':
        return head(r) + (' (утв. Президиумом ВС РФ %s)' % r['date'] if r['date'] else '') + '.pdf'
    if k == 'ОТ':
        return head(r) + ' ' + r['topic'] + '.pdf'
    return head(r) + (' (%s)' % r['topic'] if r['topic'] else '') + '.pdf'


def path(r, d):
    return os.path.join(ROOT, DISC[d], SP, FOLD[r['kind']], name(r))


def find(r):
    """Файл акта в папке судебной практики любой дисциплины (сначала — двух наших)."""
    h = head(r)
    hits = []
    for f in glob.glob(os.path.join(ROOT, '*', '2. Источники', '2. Судебная практика', '*', '*.pdf')):
        b = os.path.basename(f)
        if b.startswith(h) and b[len(h):len(h) + 1] in ('.', ' '):
            own = f.split(os.sep)[len(ROOT.split(os.sep))] in DISC.values()
            hits.append((0 if own else 1, f))
    return sorted(hits)[0][1] if hits else None


def html_of(f):
    return os.path.join(os.path.dirname(f), HTML, os.path.basename(f)[:-4] + '.html')


def main():
    rows = catalog()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'list':
        for r in rows:
            f = find(r)
            print('%-12s %s  %s' % (r['code'], 'есть' if f else 'НЕТ ', name(r)[:110]))
        return
    if cmd == 'copy':
        n = 0
        for r in rows:
            src = find(r)
            if not src:
                continue
            for d in r['disc']:
                dst = path(r, d)
                if os.path.exists(dst):
                    continue
                os.makedirs(os.path.join(os.path.dirname(dst), HTML), exist_ok=True)
                shutil.copyfile(src, dst)
                if os.path.exists(html_of(src)):
                    shutil.copyfile(html_of(src), html_of(dst))
                n += 1
        print('скопировано файлов:', n)
        return
    if cmd == 'shards':
        pref = sys.argv[2]
        ips, cons = [], []
        for r in rows:
            if find(r):
                continue
            out = os.path.relpath(path(r, r['disc'][0]), ROOT)
            assert len(os.path.basename(out).encode()) <= 235, out
            if r['kind'] in ('КП', 'КО'):
                ad = '%s Конституционного Суда Российской Федерации от %s № %s' % (
                    'Постановление' if r['kind'] == 'КП' else 'Определение', r['date'], r['num'])
                u = 'http://ips.pravo.gov.ru/api/ips/legislation/search.json?query=%s&limit=10&page=1#%s' % (
                    urllib.parse.quote_plus(ad), ad)
                ips.append('ipsact\t%s\t%s' % (u, out))
            elif r['kind'] == 'ПЛ':
                q = 'от %s N %s' % (r['date'], r['num'])
                cons.append('consauto\tПостановление Пленума Верховного Суда РФ %s#%s\t%s' % (q, q, out))
            else:
                cons.append('consauto\t%s\t%s' % (r['query'], out))
        sh = os.path.join(HERE, '..', 'shards')
        files = []
        for i in range(0, len(ips), 12):
            files.append(('%s_ips%d.tsv' % (pref, i // 12 + 1), ips[i:i + 12]))
        for i in range(0, len(cons), 4):
            files.append(('%s_cons%d.tsv' % (pref, i // 4 + 1), cons[i:i + 4]))
        for fn, lines in files:
            open(os.path.join(sh, fn), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
            print(fn, len(lines))


if __name__ == '__main__':
    main()
