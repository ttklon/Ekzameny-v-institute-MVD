#!/usr/bin/env python3
"""qart25.py SRC [N…] — каждая цитата (4 слова и больше) сверяется дословно со статьёй, на которую указывает
ближайшая ссылка: сначала ссылка после цитаты в том же предложении, затем ближайшая ссылка перед цитатой в строке.
В отличие от qcheck2.py: проверяются и строки блока «Главное для запоминания», и цитаты, перед которыми стоит ссылка
(«//ч. 1 ст. 8.2// — … («цитата»)»), и статьи любых законов и кодексов, а не только Закона о полиции и КоАП РФ.
Печатает: «НЕ В АКТЕ» (цитаты нет в названном акте), «НЕ В СТАТЬЕ» (в акте есть, в названной статье нет; где найдена)."""
import sys, os, re, glob, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = sys.argv[1]; only = [int(x) for x in sys.argv[2:]]
sys.argv = [sys.argv[0], src]
with contextlib.redirect_stdout(io.StringIO()):
    import cut25, qcheck, qcheck2
import srctok25 as K
norm, quotes = qcheck.norm, qcheck.quotes
AC = {}
def acts(fp, koap):
    if fp not in AC:
        raws = qcheck2.load(fp); AC[fp] = ([norm(t) for t in raws], [qcheck2.articles(t, koap) for t in raws])
    return AC[fp]
def run(n):
    out = []; lines = open(cut25.A + 'q%03d.txt' % n, encoding='utf-8').read().split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces)
    for (i, _z), line in pieces:
        if line.startswith('#'): continue
        refs = list(cut25.REF.finditer(line)); sents = []; pos = 0
        for s in K.sentences(line):
            a = line.find(s[:40], pos); a = pos if a < 0 else a; sents.append((a, a + len(s))); pos = a + len(s)
        for a, b in quotes(line):
            q = line[a + 1:b - 1]
            if len(q.split()) < 4 or re.match(r'Об? ', q): continue
            sa, sb = next(((x, y) for x, y in sents if x <= a < y), (0, len(line)))
            k = next((k for k, m in enumerate(refs) if b <= m.start() < sb and '«' not in line[b:m.start()]), None)
            how = 'после'
            if k is None:
                prev = [k for k, m in enumerate(refs) if m.end() <= a]
                if not prev: continue
                k = prev[-1]; how = 'перед'
            act, art = res[((i, 0), k)]; disp = names[((i, 0), k)]
            if not disp: continue
            kind, fp = qcheck2.act_files(disp)
            if kind in ('SKIP', 'UNK') or not fp: continue
            texts, arts = acts(fp, kind == 'KOAP')
            if not texts: continue
            segs = [norm(x) for x in re.split(r'\s*(?:\.\.\.|…)\s*', q) if len(norm(x)) >= 12]
            if not segs: continue
            ref = line[refs[k].start():refs[k].end()][:60]
            if not all(any(sg in t for t in texts) for sg in segs):
                out.append('q%03d:%d НЕ В АКТЕ (%s, ссылка %s → %s): «%s» | найдено в: %s' % (n, i + 1, ref, how, disp[:50], q[:120], qcheck.where(segs[0]))); continue
            if art and any(len(A) > 3 for A in arts):
                keys = (art, art.replace('.', ''))                 # в текстах законов «Статья 29 2» читается как 292
                if not any(k_ in A and all(sg in A[k_] for sg in segs) for A in arts for k_ in keys):
                    found = sorted({x for A in arts for x, t in A.items() if all(sg in t for sg in segs)})
                    out.append('q%03d:%d НЕ В СТАТЬЕ (%s, ссылка %s → ст. %s, %s): «%s» | найдено в ст.: %s' % (n, i + 1, ref, how, art, disp[:40], q[:120], ', '.join(found[:6])))
    return out
if __name__ == '__main__':
    tot = 0
    for n in (only or range(1, 150)):
        for o in run(n): print(o); tot += 1
    print('замечаний:', tot)
