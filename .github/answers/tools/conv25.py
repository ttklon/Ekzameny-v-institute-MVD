#!/usr/bin/env python3
"""conv25.py SRC — как сам закон называет деления своих статей и как на них ссылается вариант 2.
SRC — папка extract_src.py. Для каждого закона или кодекса, на который в ответах есть ссылка со статьёй,
считается, сколько раз его текст говорит «частью N настоящей статьи (статьи M)» и сколько раз «пунктом N настоящей
статьи (статьи M)». Затем печатаются ссылки ответов, которые расходятся с этим обозначением:
  • закон делит статьи на пункты, а в ответе стоит «ч. N ст. M»;
  • закон делит статьи на части, а в ответе стоит «п. N ст. M» без части.
Второй вид чаще всего верен: так пишут о статьях-перечнях («Основные понятия», полномочия органа), где пункты «1)», «2)»
идут без деления на части. Ложные места дают и ссылки без названия акта, отнесённые к соседнему акту (cut25.resolve),
и законы с одинаковым номером. Каждое место читается по тексту статьи."""
import sys, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import part25 as P, cut25
NUM = r'\d[\d\s.]*(?:(?:,|и|-|–|—)\s*\d[\d\s.]*)*'
CH = re.compile(r'[Чч]аст[ьияюмех]{1,3} ' + NUM + r' ?(?:настоящей )?стать')
PU = re.compile(r'(?<![а-яёА-ЯЁ])[Пп]ункт[аомеуыхи]{0,3} ' + NUM + r' ?(?:настоящей )?стать')
cache = {}
def info(disp):
    """(длина текста, «частей», «пунктов») последней редакции акта или None"""
    if disp not in cache:
        try: fs = P.files(disp)
        except Exception: fs = []
        if not fs: cache[disp] = None
        else:
            t = re.sub(r'\s+', ' ', ' '.join(fs[-1].values()))
            cache[disp] = (len(t), len(CH.findall(t)), len(PU.findall(t)))
    return cache[disp]
def main():
    T = collections.defaultdict(lambda: [set(), [], []])
    for n in range(1, 150):
        lines = open(cut25.A + 'q%03d.txt' % n, encoding='utf-8').read().split('\n')
        pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
        res, names = cut25.resolve(pieces)
        for (i, _z), line in pieces:
            for k, m in enumerate(cut25.REF.finditer(line)):
                r = m.group(1); disp = names.get(((i, 0), k))
                if not disp or not re.search(r'[Сс]т\.', r): continue
                c = info(disp)
                if not c: continue
                hasch = bool(re.search(r'(?:^|[\s(,и])[Чч]\.\s*\d', r))
                haspu = bool(re.search(r'(?:^|[\s(])пп?\.\s*\d', r)) and not hasch and 'подп' not in r
                e = T[c]; e[0].add(disp[:60])
                if hasch: e[1].append('q%03d:%d %s' % (n, i + 1, r[:44]))
                if haspu: e[2].append('q%03d:%d %s' % (n, i + 1, r[:44]))
    acts = bad = 0
    for c, (nm, a, b) in sorted(T.items(), key=lambda x: sorted(x[1][0], key=len)[0]):
        if not a and not b: continue
        acts += 1; name = sorted(nm, key=len)[0]; _l, ch, pu = c
        print('%-42s в тексте: «частью N» %4d, «пунктом N» %4d | в ответах: «ч.» %3d, «п.» без части %3d' % (name[:42], ch, pu, len(a), len(b)))
        if a and pu > ch:
            bad += len(a)
            for x in a: print('    закон делит статьи на пункты, в ответе «ч.»: ' + x)
        if b and ch > pu:
            bad += len(b)
            for x in b: print('    закон делит статьи на части, в ответе «п.» без части: ' + x)
    print('актов: %d  ссылок для чтения: %d' % (acts, bad))
if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main()
