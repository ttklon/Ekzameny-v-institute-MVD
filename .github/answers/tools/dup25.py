#!/usr/bin/env python3
"""dup25.py [N…] [new] — строки одного ответа, повторяющие друг друга (общие шестёрки слов ≥ 60 % короткой строки);
new — только пары, где хотя бы одна строка отсутствует в HEAD."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
ws = lambda s: re.findall(r'[а-яёa-z0-9]+', s.lower())
def sh(s, n=6):
    w = ws(s); return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
THR = 0.35 if "low" in sys.argv else 0.6
only = [int(a) for a in sys.argv[1:] if a.isdigit()]; new = 'new' in sys.argv; n = 0
for q in range(1, 150):
    if only and q not in only: continue
    L = open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')
    H = set(subprocess.run(['git', 'show', os.environ.get('REV', 'HEAD') + ':.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True, cwd=HERE).stdout.split('\n')) if new else set()
    S = [(i, l, sh(l)) for i, l in enumerate(L) if l.strip() and not l.startswith(('!!', '#'))]
    for a in range(len(S)):
        for b in range(a + 1, len(S)):
            i, l, s = S[a]; j, m, t = S[b]
            if len(s) < 3 or len(t) < 3: continue
            c = len(s & t)
            if c >= THR * min(len(s), len(t)):
                if new and l in H and m in H: continue
                n += 1; print('q%03d:%d ~ %d (%d из %d)\n    %s\n    %s' % (q, i + 1, j + 1, c, min(len(s), len(t)), l[:150], m[:150]))
print('пар:', n)
