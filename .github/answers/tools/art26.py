#!/usr/bin/env python3
"""art26.py SRC ЧАСТЬ_ИМЕНИ_ФАЙЛА СТАТЬЯ [ЧАСТЬ|pN] [--w=N] [--s=N] — текст статьи (и её части или пункта) из любого акта базы.
СТАТЬЯ: 13, 27.5, 4.1 (в тексте «Статья 4 1», «Статья 41» и «Статья 4.1» считаются одним номером).
ЧАСТЬ: 2 — «2. …»; p7 — пункт «7) …»; без неё печатается начало статьи. Нужна, чтобы читать норму глазами рядом с ответом."""
import sys, os, re
a = [x for x in sys.argv[1:] if not x.startswith('--')]
o = dict(x[2:].split('=') for x in sys.argv[1:] if x.startswith('--'))
src, name, art = a[0], a[1], a[2]; part = a[3] if len(a) > 3 else None
W = int(o.get('w', 700)); S = int(o.get('s', 0))
fs = sorted(f for f in os.listdir(src) if re.search(name, f))
if not fs: sys.exit('нет файла: ' + name)
for f in fs[:int(o.get('files', 1))]:
    T = open(os.path.join(src, f), encoding='utf-8', errors='ignore').read()
    T = re.sub(r'Стр\. \d+ из \d+', ' ', T); T = re.sub(r'\s+', ' ', T)
    num = art.split('.')
    if len(num) == 1: pat = r'Статья %s\. ?(?=[А-ЯЁ(])' % num[0]
    else: pat = r'Статья %s[. ]? ?%s ?\. ?(?=[А-ЯЁ(])' % (num[0], r'[. ]? ?'.join(num[1:]))
    ms = list(re.finditer(r'Статья %s\. ?(?=[А-ЯЁ(])' % re.escape(art), T)) or list(re.finditer(pat, T))
    if not ms: print('[%s] статья %s не найдена' % (f[:50], art)); continue
    m = ms[-1] if o.get('last') else ms[0]
    e = re.search(r'Статья \d+[\d. ]{0,6}\. ?(?=[А-ЯЁ(])', T[m.end():])
    A = T[m.start(): m.end() + e.start()] if e else T[m.start(): m.start() + 60000]
    if part:
        if part.startswith('p'): pp = r'(?<![\d.]) %s\) ' % re.escape(part[1:])
        else:
            q = part.split('.')
            pp = r'(?<![\d.«"№]) %s\. ?(?=[А-ЯЁ(])' % (q[0] if len(q) == 1 else q[0] + r'[. ]? ?' + q[1] + r' ?')
        k = re.search(pp, A)
        if not k: print('[%s] ст. %s: часть %s не найдена; длина статьи %d' % (f[:40], art, part, len(A))); continue
        A = A[k.start():]
    print('[%s] ст. %s%s: %s' % (f[:40], art, ' ' + part if part else '', A[S:S + W]))
