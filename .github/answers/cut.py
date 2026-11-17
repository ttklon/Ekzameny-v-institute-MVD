#!/tmp/venv/bin/python
"""cut.py — применяет сокращения из /tmp/w/cuts.txt к /tmp/auto и пишет .github/answers/adp2/qNNN.txt
Строка cuts.txt:  N: 5-7,12,30-33   (номера строк автоверсии). """
import sys, re, os
sys.path.insert(0, '/tmp/w'); import mk2
ROOT = mk2.ROOT
def parse(spec):
    s = set()
    for part in spec.replace(' ', '').split(','):
        if not part: continue
        if part == 'A': s.add('A'); continue
        if part[0] == 'K': s.add(part); continue
        if '-' in part:
            a, b = part.split('-'); s |= set(range(int(a), int(b) + 1))
        else: s.add(int(part))
    return s
def apply(n, dele, ren=None):
    L = open('/tmp/auto/q%03d.txt' % n, encoding='utf-8').read().split('\n')
    for i, h in (ren or {}).items():
        assert L[i].startswith('## '), (n, i, L[i][:40])
        L[i] = '## 0. ' + h
    dele = set(dele)
    if 'A' in dele:
        from ol import is_A
        keep = {int(x[1:]) for x in dele if isinstance(x, str) and x[0] == 'K'}
        dele = {x for x in dele if isinstance(x, int)} | {i for i, x in enumerate(L) if is_A(x) and i not in keep}
    else:
        dele = {x for x in dele if isinstance(x, int)}
    AUTO = re.compile(r'^(Это определение законное|Определение законное|Оба определения законные|Все три определения даны в самой Инструкции|Оба определения даны в законе|Определение дано в законе)\.$')
    dele |= {i for i, x in enumerate(L) if AUTO.match(x.strip())}
    rest = '\n'.join(x for i, x in enumerate(L) if i not in dele)
    for i in dele:
        if 0 <= i < len(L) and 'далее —' in L[i]:
            for ab in re.findall(r'далее — ([^)/;]+?)[)/;]', L[i]):
                ab = ab.strip(' .')
                key = ab[:-1] if len(ab) > 6 else ab
                if key in rest: print('   !!! удалено введение сокращения, а оно используется:', n, i, ab)
        if 0 <= i < len(L) and L[i].startswith('!!'): raise SystemExit('удаляется !! %d %d' % (n, i))
    isli = lambda x: x.lstrip().startswith('- ')
    # вводная строка списка без пунктов — удалить; пункты без вводной оставить
    def nxt(i):
        j = i + 1
        while j < len(L) and (not L[j].strip() or j in dele): j += 1
        return j
    for i, x in enumerate(L):
        if i in dele or not x.strip() or x.startswith('#') or isli(x): continue
        if x.rstrip().endswith(':'):
            # все ли пункты списка под ней удалены
            j = i + 1; items = []
            while j < len(L) and (not L[j].strip() or isli(L[j])):
                if isli(L[j]): items.append(j)
                j += 1
            if items and all(k in dele for k in items): dele.add(i)
    # подпункты удалённого пункта
    for i, x in enumerate(L):
        if i in dele and x.startswith('- '):
            j = i + 1
            while j < len(L) and L[j].startswith('  - '): dele.add(j); j += 1
    out = [x for i, x in enumerate(L) if i not in dele]
    txt = re.sub(r'\n{3,}', '\n\n', '\n'.join(out))
    # пустые разделы и перенумерация
    parts = re.split(r'(?m)^(?=## )', txt)
    head, secs = parts[0], parts[1:]
    res = [head]; k = 0; main = ''
    for s in secs:
        h, _, body = s.partition('\n')
        m = re.search(r'(?m)^!! .*$', body)
        if m: main = m.group(0); body = body[:m.start()] + body[m.end():]
        if not body.strip(): continue
        k += 1
        res.append('## %d. %s\n%s' % (k, re.sub(r'^## \d+\. ', '', h), body.rstrip() + '\n\n'))
    txt = ''.join(res).rstrip() + '\n\n' + main + '\n'
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    txt = re.sub(r'(?m)^((?:- )?\*\*)\d+\.\d+\. ', r'\1', txt)
    return txt
if __name__ == '__main__':
    Q = mk2.load_v1(); tot1 = tot2 = 0; only = set(int(x) for x in sys.argv[1:])
    cuts = {}; rens = {}
    for ln in open('/tmp/w/cuts.txt', encoding='utf-8'):
        ln = ln.split('#')[0].strip()
        if not ln: continue
        n, spec = ln.split(':', 1)
        parts = spec.split('|'); cuts[int(n)] = parse(parts[0])
        rens[int(n)] = {int(x.split('=', 1)[0].strip().lstrip('H')): x.split('=', 1)[1].strip() for x in parts[1:]}
    for n in sorted(cuts):
        txt = apply(n, cuts[n], rens[n])
        open(ROOT + '/adp2/q%03d.txt' % n, 'w', encoding='utf-8').write(txt)
        w1, w2 = len(Q[n][1].split()), len(txt.split()); tot1 += w1; tot2 += w2
        if not only or n in only:
            fl = '' if 1.28 <= w1 / w2 <= 1.6 else '  <<<'
            print(n, w1, w2, round(w1 / w2, 2), 'разделов', txt.count('\n## '), '«»', txt.count('«') - txt.count('»'), fl)
    print('ИТОГО', len(cuts), tot1, tot2, round(tot1 / max(tot2, 1), 2))
