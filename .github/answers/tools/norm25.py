#!/usr/bin/env python3
"""Нормативная база после сокращения: какие акты (по номеру) были названы в ответе
до сокращения (30db505) и не названы теперь. Блок «!!» не считается.
  norm25.py          — сводка
  norm25.py show [N] — строки прежнего текста, где стоял пропавший акт
"""
import subprocess, re, sys, os
A = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'adp2')
BASE = '30db505'
NUM = re.compile(r'№\s?(\d[\d/.\-]*(?:-?[А-Яа-яA-Z]{1,4})?\d*)')
def old(n):
    return subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (BASE, n)],
                          capture_output=True, text=True).stdout
def cur(n):
    return open(os.path.join(A, 'q%03d.txt' % n), encoding='utf-8').read()
def body(t):
    return '\n'.join(l for l in t.split('\n') if not l.startswith('!! '))
def acts(t):
    return {m.group(1).rstrip('.-/') for m in NUM.finditer(body(t))}
def has(a, line):
    return re.search(r'№\s?' + re.escape(a) + r'(?![\d\-А-Яа-я]|/\d)', line) is not None
def lost(n):
    return sorted(acts(old(n)) - acts(cur(n)))
hk = lambda h: re.sub(r'^##\s*\d+\.\s*', '', h).strip()
def main():
    show = len(sys.argv) > 1 and sys.argv[1] == 'show'
    only = [int(x) for x in sys.argv[2:]]
    na = nq = 0
    for n in range(1, 150):
        if only and n not in only: continue
        l = lost(n)
        if not l: continue
        nq += 1; na += len(l)
        if not show:
            print('q%03d' % n, ', '.join('№ ' + x for x in l)); continue
        o = old(n).split('\n'); c = cur(n)
        ch = {hk(x) for x in c.split('\n') if x.startswith('## ')}
        print('=== q%03d %s' % (n, ', '.join('№ ' + x for x in l)))
        sec = ''
        for i, line in enumerate(o):
            if line.startswith('## '): sec = line
            if line.startswith('!! '): continue
            hit = [a for a in l if has(a, line)]
            if hit:
                print('  [%s%s | стр. %d | %d сл. | %s]' % ('' if hk(sec) in ch else 'РАЗДЕЛ УДАЛЁН: ', sec[:60], i + 1, len(line.split()), ', '.join(hit)))
                print('   ', line)
    print('ответов: %d, актов: %d' % (nq, na))
if __name__ == '__main__':
    main()
