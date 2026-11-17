#!/tmp/venv/bin/python
"""ol.py N [N2]  — оглавление автоверсии (/tmp/auto) для выбора сокращений.
Формат строки: <номер строки> <слов> <флаги r=есть ссылка q=есть цитата> <начало текста>"""
import sys, re, glob
sys.path.insert(0, '/tmp/w'); import mk2
Q = None
def outline(n, width=52):
    global Q
    if Q is None: Q = mk2.load_v1()
    L = open('/tmp/auto/q%03d.txt' % n, encoding='utf-8').read().split('\n')
    v1 = len(Q[n][1].split()); tot = sum(len(x.split()) for x in L)
    print('=== %d | v1 %d | авто %d | цель ≤ %d (1,4) … %d (1,3) | убрать %d–%d' % (n, v1, tot, v1 / 1.4, v1 / 1.3, tot - v1 / 1.3, tot - v1 / 1.4))
    # слова по разделам
    sec = {}; cur = None
    for i, x in enumerate(L):
        if x.startswith('## '): cur = i; sec[cur] = 0
        elif cur is not None and not x.startswith('!!'): sec[cur] += len(x.split())
    for i, x in enumerate(L):
        if not x.strip() or x.startswith('# '): continue
        w = len(x.split())
        if x.startswith('## '):
            print('%3d [%d] %s' % (i, sec[i], x[:70])); continue
        if x.startswith('!!'):
            print('%3d %3d !!' % (i, w)); continue
        fl = ('r' if '//' in x else '-') + ('q' if '«' in x else '-') + ('D' if 'далее —' in x else '')
        wd = width if not x.lstrip().startswith('- ') else 40
        x = x.replace('**', '')
        print('%3d %3d %s %s' % (i, w, fl, x[:wd]))
if __name__ == '__main__':
    a = int(sys.argv[1]); b = int(sys.argv[2]) if len(sys.argv) > 2 else a
    for n in range(a, b + 1):
        if n in mk2.MANUAL: continue
        outline(n)
