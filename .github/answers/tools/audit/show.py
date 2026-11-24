#!/usr/bin/env python3
"""show.py ФАЙЛ_ВЫВОДА [РЕГ [С [ПО]]] — печатает блоки вывода refcheck.py, первая строка которых подходит под выражение, с номера С по номер ПО."""
import sys, re
t = open(sys.argv[1], encoding='utf-8').read().split('\n\n')
rx = sys.argv[2] if len(sys.argv) > 2 else '.'; a = int(sys.argv[3]) if len(sys.argv) > 3 else 0; b = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9
bl = [x for x in t if x.strip() and re.search(rx, x.split('\n')[0]) and not x.startswith(('==', '--'))]
print(len(bl), 'блоков')
for x in bl[a:b]: print(x)
