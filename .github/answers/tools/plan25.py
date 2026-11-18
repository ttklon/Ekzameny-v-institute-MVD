#!/usr/bin/env python3
"""plan25.py — сводка для выбора разделов под 25 часов: по каждому ответу — объём без блока, цель, разделы с числом слов.
Пометка * — на раздел опирается блок «Главное для запоминания» (в блоке есть ссылки на статьи, которых нет в других разделах)."""
import os, sys, re, math
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(os.path.join(HERE, '..'))
def parse(q):
    L = open('adp2/q%03d.txt' % q, encoding='utf-8').read().split('\n')
    head = L[0]; secs = []; blk = ''
    for l in L[1:]:
        if l.startswith('!!'): blk = l; continue
        if l.startswith('## '): secs.append([l, []]); continue
        if secs: secs[-1][1].append(l)
    return head, secs, blk
def arts(t): return set(re.findall(r'ст\. (\d+(?:\.\d+)*)', t)) | set(re.findall(r'п\. (\d+) ', t))
if __name__ == '__main__':
    data = {q: parse(q) for q in range(1, 150)}
    body = {q: sum(len(l.split()) for h, b in data[q][1] for l in [h] + b) for q in data}
    mean = sum(body.values()) / 149; TOT = float(sys.argv[1]) if len(sys.argv) > 1 else 132500
    raw = {q: math.sqrt(body[q] * mean) for q in data}; k = TOT / sum(raw.values())
    for q in range(1, 150):
        head, secs, blk = data[q]
        print('q%03d %d→%d | %s' % (q, body[q], raw[q] * k, re.sub(r'^# Вопрос \d+\.\s*', '', head)[:230]))
        ba = set(re.findall(r'ст\. (\d+(?:\.\d+)*)', blk)); out = []
        for i, (h, b) in enumerate(secs):
            t = ' '.join(b); others = ' '.join(' '.join(bb) for j, (hh, bb) in enumerate(secs) if j != i)
            mine = set(re.findall(r'ст\. (\d+(?:\.\d+)*)', t)) - set(re.findall(r'ст\. (\d+(?:\.\d+)*)', others))
            star = '*' * min(len(mine & ba), 3)
            out.append('%s(%d)%s' % (re.sub(r'^## ', '', h)[:58], len(t.split()), star))
        print('   ' + ' | '.join(out))
