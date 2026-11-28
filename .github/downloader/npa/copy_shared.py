#!/usr/bin/env python3
"""Акты, нужные обеим дисциплинам (в каталоге отметка GS), загружаются один раз.
Скрипт копирует файл акта и его исходную страницу в папку второй дисциплины. Запуск: python3 copy_shared.py"""
import os, shutil
import make_shards as m

n = 0
for r in m.catalog():
    if len(r['disc']) < 2:
        continue
    src = m.have(r)
    if not src:
        continue
    for d in r['disc']:
        dst = os.path.join(m.ROOT, m.path(r, d))
        if os.path.exists(dst):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
        # исходная страница лежит рядом, в «Исходные страницы (HTML)», с тем же именем и расширением .html
        sdir = os.path.join(os.path.dirname(src), 'Исходные страницы (HTML)')
        base = os.path.splitext(os.path.basename(src))[0]
        if os.path.isdir(sdir):
            for f in os.listdir(sdir):
                if os.path.splitext(f)[0] == base:
                    ddir = os.path.join(os.path.dirname(dst), 'Исходные страницы (HTML)')
                    os.makedirs(ddir, exist_ok=True)
                    shutil.copy2(os.path.join(sdir, f), os.path.join(ddir, f))
print('скопировано актов:', n)
