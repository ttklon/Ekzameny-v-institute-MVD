#!/usr/bin/env python3
"""v1split.py КАТАЛОГ — вариант 1 (adp/qNNN-NNN_частьK.txt) режется на 149 файлов qNNN.txt по заголовкам «# Вопрос N.»;
первая строка каждого файла «@@ файл:строка» указывает, откуда взят текст. Нужен программам, которые читают по файлу на вопрос."""
import sys, os, re, glob
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def key(p):
    m = re.search(r'q(\d+)-\d+_часть(\d+)', p); return (int(m.group(1)), int(m.group(2)))
n = 0
for f in sorted(glob.glob(os.path.join(here, 'adp', 'q*_часть*.txt')), key=key):
    cur = None; buf = []
    for i, l in enumerate(open(f, encoding='utf-8'), 1):
        m = re.match(r'# Вопрос (\d+)\.', l)
        if m:
            if cur: open(os.path.join(out, 'q%03d.txt' % cur), 'w', encoding='utf-8').write(''.join(buf)); n += 1
            cur = int(m.group(1)); buf = ['@@ %s:%d\n' % (os.path.basename(f), i)]
        if cur: buf.append(l)
    if cur: open(os.path.join(out, 'q%03d.txt' % cur), 'w', encoding='utf-8').write(''.join(buf)); n += 1
print('файлов', n)
