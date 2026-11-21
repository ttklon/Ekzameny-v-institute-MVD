#!/usr/bin/env python3
"""tcov25.py [REV] — слова вопроса, которые после сокращения пропали из заголовков разделов или почти пропали из текста ответа
(сравнение с редакцией REV, по умолчанию 4b36cfb): признак того, что часть вопроса осталась без раздела."""
import re, subprocess, sys, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
REV = sys.argv[1] if len(sys.argv) > 1 else '4b36cfb'
st = lambda w: w[:5] if len(w) > 6 else w[:4]
W = lambda t: [w for w in re.findall(r'[а-яё]+', t.lower().replace('ё', 'е')) if len(w) >= 5]
def cnt(L):
    c = {}
    for w in W(' '.join(l for l in L[1:] if not l.startswith('!! '))): c[st(w)] = c.get(st(w), 0) + 1
    return c
n = 0
for q in range(1, 150):
    L = open('adp2/q%03d.txt' % q, encoding='utf-8').read().split('\n')
    O = subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (REV, q)], capture_output=True, text=True).stdout.split('\n')
    title = re.sub(r'^# Вопрос \d+\.', '', L[0]); c = cnt(L); o = cnt(O)
    hs = {st(w) for w in W(' '.join(l for l in L if l.startswith('## ')))}; oh = {st(w) for w in W(' '.join(l for l in O if l.startswith('## ')))}
    bad = [w + ('(раздел)' if st(w) in oh and st(w) not in hs else '(%d→%d)' % (o.get(st(w), 0), c.get(st(w), 0))) for w in dict.fromkeys(W(title))
           if (c.get(st(w), 0) <= 1 and o.get(st(w), 0) >= 3) or (st(w) in oh and st(w) not in hs)]
    if bad: n += 1; print('q%03d' % q, ', '.join(bad), '|', title[:100])
print('всего', n)
