#!/usr/bin/env python3
"""kpage.py SRC КОД A-B [ЗНАКОВ] — печатает страницы A–B файла источника (текст сплошной строкой на страницу).

КОД — первые шесть знаков имени файла в SRC. В начале каждой страницы — «[N/M]»: номер страницы файла и номер,
напечатанный на странице. ЗНАКОВ — сколько знаков страницы показать (по умолчанию вся).
"""
import sys, os, re, glob
src, code, rng = sys.argv[1:4]; lim = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
a, b = (int(x) for x in rng.split('-')) if '-' in rng else (int(rng), int(rng))
f = glob.glob(os.path.join(src, code + '*'))[0]; print('#', os.path.basename(f)[7:-4])
t = open(f, encoding='utf-8').read(); t = re.sub(r'(?<=[а-яё])-\n(?=[а-яё])', '', t)
for m in re.finditer(r'@@ (\d+) \| (\S+)\n(.*?)(?=@@ \d+ \| |\Z)', t, re.S):
    n = int(m.group(1))
    if a <= n <= b: print('[%d/%s] %s' % (n, m.group(2), re.sub(r'\s+', ' ', m.group(3))[:lim]))
