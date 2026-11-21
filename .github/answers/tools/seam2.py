#!/usr/bin/env python3
"""seam2.py [N…] — швы сокращения на уровне предложений: предложение начинается со слова, отсылающего к предыдущему
(«Это», «Такие», «Они», «Поэтому», «Кроме того»…), а предложение, стоявшее перед ним до сокращения (30db505), удалено.
Печатает: что стоит перед ним сейчас, само предложение, что стояло раньше."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
A = os.path.join(HERE, '..', 'adp2')
ANA = r'(эт[оаиу]|этот|этим|этого|этой|этих|этому|этими|так(ой|ая|ое|ие|им|ого|их|ому|ими|ую)|он[аио]?|его|её|их|ему|ей|им|ими|поэтому|потому|кроме того|также|при этом|однако|но|например|так|здесь|тогда|вместе с тем|наконец|во-вторых|в-третьих|второе|третье|далее|следовательно|значит|иначе|напротив|в (этом|таком|этих|таких|остальных|других|первом|последнем) (случа[еях]+)?|во втором|указанн\w+|названн\w+|данн\w+|перечисленн\w+|последн\w+|тем самым|отсюда|соответственно|в частности|втор(ой|ая)|третий|друг(ой|ая|ие)|остальные|помимо этого|из этого|для этого|после этого|к ним|среди них|в них|с этой|по этой|в этой|на этом|об этом|те же|то же|тот же|именно|и|а|причём|притом|зато|иными словами|то есть|исключени[ея]|оба|обе|все они|каждый из них|тот|та|те|там|туда|оттуда|сюда|сам[аио]?|кроме|вместо этого|в отличие|аналогично|точно так же|равным образом|сверх того|более того|к тому же|впрочем|всё же|все же|тем не менее|в свою очередь|в связи с этим|вследствие этого|в результате|ещё|еще|только|лишь|даже|уже)\b'
norm = lambda s: ' '.join(re.findall(r'[а-яёa-z0-9]+', s.lower().replace('ё', 'е')))
strip = lambda l: re.sub(r'^\s*(?:>\s*|-\s+|\d+\.\s+)?', '', l)
def sents(txt):
    out = []
    for l in txt.split('\n'):
        if not l.strip() or l.startswith(('#', '!!')): 
            if l.startswith('## '): out.append(('H', l))
            continue
        for s in cut25.split_sent(strip(l)):
            if s.strip(): out.append(('S', s.strip()))
    return out
def old(q): return subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True, cwd=HERE).stdout
only = [int(a) for a in sys.argv[1:] if a.isdigit()]; n = 0
for q in range(1, 150):
    if only and q not in only: continue
    O = sents(old(q)); C = sents(open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read())
    prev = {}
    for i, (k, s) in enumerate(O):
        if k == 'S': prev.setdefault(norm(s), set()).add(norm(O[i - 1][1]) if i else '')
    for i, (k, s) in enumerate(C):
        if k != 'S' or not i: continue
        body = re.sub(r'^[\*«(/]+', '', s)
        if not re.match(ANA, body.lower()): continue
        ns = norm(s)
        if ns not in prev: continue
        pc = norm(C[i - 1][1])
        if pc in prev[ns]: continue
        if any(p and (p.startswith(pc) or pc.startswith(p)) for p in prev[ns]): continue
        po = [O[j - 1][1] for j, (kk, ss) in enumerate(O) if kk == 'S' and norm(ss) == ns][0]
        n += 1
        print('q%03d\n   сейчас перед: …%s\n   ► %s\n   было перед:   …%s' % (q, C[i - 1][1][-130:], s[:150], po[-130:]))
print('всего', n)
