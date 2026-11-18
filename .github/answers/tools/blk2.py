#!/usr/bin/env python3
"""blk2.py [N…] [THR] — предложения блока «Главное для запоминания», слова которых плохо покрыты текстом ответа:
блок не должен сообщать то, чего в ответе нет. Печатает предложение и слова, отсутствующие в тексте."""
import re, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
A = os.path.join(HERE, '..', 'adp2')
st = lambda w: w[:5] if len(w) > 6 else w[:4]
words = lambda s: [w for w in re.findall(r'[а-яё]+', re.sub(r'//[^/]*//', ' ', s).lower().replace('ё', 'е')) if len(w) >= 5]
only = [int(a) for a in sys.argv[1:] if a.isdigit()]; n = 0
for q in range(1, 150):
    if only and q not in only: continue
    L = open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n')
    bl = next((l for l in L if l.startswith('!! ')), '')[3:]; body = ' '.join(l for l in L if not l.startswith('!! '))
    bs = set(st(w) for w in words(body))
    for s in cut25.split_sent(bl):
        ws = words(s)
        if len(ws) < 4: continue
        miss = sorted({w for w in ws if st(w) not in bs})
        if len(miss) >= 3 or (len(miss) >= 2 and len(miss) / len(set(ws)) > 0.25):
            n += 1; print('q%03d [нет в тексте: %s]\n     %s' % (q, ', '.join(miss), s.strip()[:230]))
print('всего', n)
