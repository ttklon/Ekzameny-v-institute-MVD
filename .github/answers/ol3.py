#!/tmp/venv/bin/python
"""ol3.py N… — оглавление оставшихся (не вырезанных) строк /tmp/auto, начиная с 3-го раздела; для добора сокращений"""
import sys, re
sys.path.insert(0, '/tmp/w'); import mk2, ol
import importlib.util
spec = importlib.util.spec_from_file_location('cut', '/tmp/w/cut.py'); cut = importlib.util.module_from_spec(spec)
src = open('/tmp/w/cut.py', encoding='utf-8').read().split("if __name__")[0]; exec(src, cut.__dict__)
cuts = {}
for ln in open('/tmp/w/cuts.txt', encoding='utf-8'):
    ln = ln.strip()
    if not ln or ln.startswith('#') or ':' not in ln: continue
    n, sp = ln.split(':', 1); cuts[int(n)] = sp.split('|')[0].strip()
Q = mk2.load_v1()
def rng(sp):
    s = set()
    for p in sp.replace(' ', '').split(','):
        if not p or p[0] in 'AK': continue
        a, _, b = p.partition('-'); s |= set(range(int(a), int(b or a) + 1))
    return s
for n in map(int, sys.argv[1:]):
    L = open('/tmp/auto/q%03d.txt' % n, encoding='utf-8').read().split('\n')
    dele = rng(cuts[n])
    cur = len(open('/home/user/Ekzameny-v-institute-MVD/.github/answers/adp2/q%03d.txt' % n, encoding='utf-8').read().split())
    v1 = len(Q[n][1].split())
    print('=== %d | надо убрать %d…%d' % (n, cur - v1 / 1.33, cur - v1 / 1.38))
    ks = 0; i = 0
    while i < len(L):
        x = L[i]
        if i in dele or not x.strip() or x.startswith('# ') or x.startswith('!!'): i += 1; continue
        if x.startswith('## '):
            ks += 1
            if ks >= 3:
                w = 0; j = i + 1
                while j < len(L) and not L[j].startswith('## '):
                    if j not in dele and not L[j].startswith('!!'): w += len(L[j].split())
                    j += 1
                print('%d [%d] %s' % (i, w, x[3:60]))
            i += 1; continue
        if ks < 3: i += 1; continue
        if x.lstrip().startswith('- '):
            j = i; w = 0; k = 0
            while j < len(L) and L[j].lstrip().startswith('- '):
                if j not in dele: w += len(L[j].split()); k += 1
                j += 1
            print(' %d-%d L%d %d %s' % (i, j - 1, k, w, x.replace('**', '').lstrip('- ')[:30])); i = j; continue
        fl = ('D' if 'далее —' in x else '') + ('*' if ol.is_A(x) else '')
        print(' %d %d %s %s' % (i, len(x.split()), fl, x.replace('**', '')[:40])); i += 1
