#!/usr/bin/env python3
"""Статьи вида N.M (КоАП РФ) в ссылках //…//: были в ответе до сокращения (30db505), теперь нет.
  art25.py            — сводка
  art25.py show N…    — строки прежнего текста с пропавшими статьями
"""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import norm25 as N
A = re.compile(r'(?<![\d.])(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)(?![\d])')
def arts(t):
    s = set()
    for r in re.findall(r'//([^/]+)//', t):
        for m in re.finditer(r'(?:ст(?:\.|ать\w+)|глав\w+)\s*([\d.,\s–-]+(?:и\s[\d.]+)?)', r):
            for a in A.findall(m.group(1)): s.add(a.rstrip('.'))
    return s
key = lambda x: [int(y) for y in x.split('.')]
def lost(q):
    return sorted(arts(N.body(N.old(q))) - arts(N.body(N.cur(q))), key=key)
def main():
    show = len(sys.argv) > 1 and sys.argv[1] == 'show'
    only = [int(x) for x in sys.argv[2:]]
    n = k = 0
    for q in range(1, 150):
        if only and q not in only: continue
        l = lost(q)
        if not l: continue
        n += len(l); k += 1
        print('q%03d (%d) %s' % (q, len(l), ', '.join(l)))
        if show:
            o = N.old(q).split('\n'); c = N.cur(q); sec = ''
            ch = {N.hk(x) for x in c.split('\n') if x.startswith('## ')}
            for i, line in enumerate(o):
                if line.startswith('## '): sec = line
                if line.startswith('!! '): continue
                hit = [a for a in l if a in arts(line)]
                if hit:
                    print('  %d [%s%s] %s: %s' % (i + 1, '' if N.hk(sec) in ch else '✗', sec[3:40], ','.join(hit), line[:int(os.environ.get('W', '260'))]))
    print('статей: %d, ответов: %d' % (n, k))
if __name__ == '__main__':
    main()
