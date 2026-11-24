#!/usr/bin/env python3
"""band.py ФАЙЛ_REFCHECK ОТ ДО [-p СТРАНИЦА] [-n НА_СТРАНИЦЕ=22] [-s 460] [-w 400] [-u 2]

Чтение по полосам совпадения. ФАЙЛ_REFCHECK — вывод «refcheck.py … -a -c»: у каждого предложения в заголовке стоит доля
его значимых слов, найденных в названной норме («{57%}»). Скрипт печатает подряд предложения с долей от ОТ до ДО
(включительно; «-1 -1» — короткие предложения без доли) и под каждым — отрывки нормы, выбранные refcheck.py.
Ничего не оценивает: это лист для чтения глазами. -p — номер страницы (с 1), в конце печатается, сколько всего.
"""
import re, sys
def opt(k, d):
    if k in sys.argv:
        i = sys.argv.index(k); v = sys.argv[i + 1]; del sys.argv[i:i + 2]; return v
    return d
P = int(opt('-p', 1)); N = int(opt('-n', 22)); S = int(opt('-s', 460)); W = int(opt('-w', 400)); U = int(opt('-u', 2))
f, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
blocks = []; cur = None
for line in open(f, encoding='utf-8'):
    m = re.match(r'(\S+:\d+)  (.*?)  \[(.*)\]\s*$', line)
    if m:
        k = re.search(r'\{(\d+)%\}', m.group(2)); cur = [m.group(1), int(k.group(1)) if k else -1, m.group(3), '', []]; blocks.append(cur)
    elif cur is not None and line.startswith('      → '): cur[4].append(line[8:].strip())
    elif cur is not None and line.startswith('   ') and not cur[3]: cur[3] = line.strip()
sel = [b for b in blocks if lo <= b[1] <= hi]
for loc, cov, refs, sent, us in sel[(P - 1) * N:P * N]:
    print('%s {%s} [%s]' % (loc, cov if cov >= 0 else '-', re.sub(r' ← \w{6} ', ' ← ', refs)[:110]))
    print('  О: ' + sent[:S])
    for u in us[:U]: print('  Н: ' + re.sub(r'\s+', ' ', u)[:W])
print('-- полоса %d–%d: всего %d, страница %d из %d' % (lo, hi, len(sel), P, (len(sel) + N - 1) // N))
