#!/usr/bin/env python3
"""Читает со стандартного ввода ответы подряд (каждый начинается с «# Вопрос N. »), пишет upp/qNNN.txt, печатает число слов."""
import re, sys, os
D = '/home/user/Ekzameny-v-institute-MVD/.github/answers/upp'
t = sys.stdin.read()
ch = re.split(r'(?m)^(?=# Вопрос \d+\. )', t)
tot = 0
for c in ch:
    c = c.strip()
    if not c:
        continue
    n = int(re.match(r'# Вопрос (\d+)\. ', c).group(1))
    lines = [l.rstrip() for l in c.split('\n')]
    bad = []
    for l in lines[1:]:
        if not l:
            continue
        if l.startswith('## '):
            if l[-1] in '.:;,': bad.append(l)
        elif l.startswith(('> ', '- ', '  - ', '!! ')) or not l.startswith(('#', '>', '!', ' ')):
            if l[-1] not in '.;:!?': bad.append(l)
            for mk in ('**', '//', '__'):
                if l.count(mk) % 2: bad.append('РАЗМЕТКА ' + l)
        else:
            bad.append(l)
    last = [l for l in lines if l][-1]
    if not last.startswith('!! '): bad.append('НЕТ БЛОКА !!')
    open(os.path.join(D, 'q%03d.txt' % n), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    w = len(re.sub(r'[#>*/_!-]', ' ', c).split())
    tot += w
    print(n, w, ('  ОШИБКИ: ' + ' | '.join(b[:70] for b in bad)) if bad else '')
print('всего', tot)
