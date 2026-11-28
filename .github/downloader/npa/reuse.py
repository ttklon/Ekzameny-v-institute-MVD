#!/usr/bin/env python3
"""Акты, уже загруженные для других дисциплин, повторно не скачиваются: скрипт находит файл акта
в папках других дисциплин по виду акта, дате и номеру и копирует его (вместе с исходной страницей)
в папку дисциплины из каталога. Запуск: python3 reuse.py  — печатает, что скопировано."""
import os, re, glob, shutil
import make_shards as m

HEAD = {'ФКЗ': 'ФКЗ', 'ФЗ': 'ФЗ', 'ЗРФ': 'Закон РФ', 'У': 'Указ Президента РФ', 'П': 'Постановление Правительства РФ',
        'Р': 'Распоряжение Правительства РФ', 'М': 'Приказ МВД России'}
own = tuple(m.DISC.values())
index = {}
for f in glob.glob(os.path.join(m.ROOT, '*', '2. Источники', '1. Нормативные правовые акты', '*', '*.pdf')):
    rel = os.path.relpath(f, m.ROOT)
    if rel.startswith(own):
        continue
    name = os.path.basename(f)
    mm = re.match(r'(.+?) от (\d\d\.\d\d\.\d{4}) № (\S+)', name)
    if not mm or 'утратил' in name or 'выписка' in name or 'неполн' in name:
        continue
    index.setdefault((mm.group(1), mm.group(2), mm.group(3)), []).append(f)

n = 0
for r in m.catalog():
    if m.have(r) or r['kind'].endswith(':='):
        continue
    k = r['kind'].split(':')[0]
    head = HEAD.get(k) or (r['kind'].split(':', 1)[1] if k == 'В' else None)
    cands = index.get((head, r['date'], r['num']), [])
    if not cands:
        continue
    cands.sort(key=lambda f: (0 if 'действующая редакция' in f else 2 if 'официальное опубликование' in f or 'скан' in f else 1, f))
    src = cands[0]
    dst = os.path.join(m.ROOT, m.path(r, r['disc'][0]))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    sdir = os.path.join(os.path.dirname(src), 'Исходные страницы (HTML)')
    base = os.path.splitext(os.path.basename(src))[0]
    for s in glob.glob(os.path.join(glob.escape(sdir), glob.escape(base) + '.*')):
        ddir = os.path.join(os.path.dirname(dst), 'Исходные страницы (HTML)')
        os.makedirs(ddir, exist_ok=True)
        shutil.copy2(s, os.path.join(ddir, os.path.splitext(os.path.basename(dst))[0] + os.path.splitext(s)[1]))
    n += 1
    print('%s\t%s' % (r['code'], os.path.relpath(src, m.ROOT)))
print('взято из папок других дисциплин:', n)
