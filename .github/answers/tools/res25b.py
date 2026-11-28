#!/usr/bin/env python3
"""res25b.py [REV] — строки, не менявшиеся с REV (по умолчанию HEAD): каждая неполная ссылка должна разрешаться
в тот же акт и ту же статью, что и в REV. Ловит случаи, когда вставка соседней строки меняет смысл ссылки."""
import sys, subprocess, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cut25 as C
REV = ([a for a in sys.argv[1:]] or ['HEAD'])[0]
def at(rev, n): return subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (rev, n)], capture_output=True, text=True).stdout
def rr(t):
    L = [(i, l) for i, l in enumerate(t.split('\n'))]
    r, _ = C.resolve(L); out = []
    for i, l in L:
        for k, m in enumerate(C.REF.finditer(l)): out.append((m.group(1), r[(i, k)][0], r[(i, k)][1], l))
    return out
n = 0
for q in range(1, 150):
    old = rr(at(REV, q)); cur = rr(open(os.path.join(C.A, 'q%03d.txt' % q), encoding='utf-8').read())
    om = {}
    for ref, a, s, l in old: om.setdefault((ref, l), set()).add((a, s))
    for ref, a, s, l in cur:
        if l.startswith('!! '): continue
        if (ref, l) in om and (a, s) not in om[(ref, l)]:
            print('q%03d //%s// теперь → %s ст. %s; было → %s | %s' % (q, ref[:45], a, s, sorted(om[(ref, l)], key=str)[:2], l[:70])); n += 1
print('всего', n)
