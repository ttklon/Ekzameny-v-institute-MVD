#!/usr/bin/env python3
"""listqual.py ПАПКА_ОТВЕТОВ ФАЙЛ_АКТА СТАТЬЯ ЧАСТЬ [ПУНКТ] [-v] [-m]

Оговорки и полнота в перечнях статей. Дополняет listcheck.py: тот проверяет, входит ли названная в ответе статья
в перечень, но не смотрит на скобки («в части…», «в пределах своих полномочий», «при непосредственном
обнаружении…») и на то, все ли статьи главы названы.

Норма-перечень разбирается на позиции: статья целиком, диапазон статей или части статьи, и оговорка в скобках,
стоящая сразу после позиции. В ответах берётся каждое предложение со ссылкой на норму. Пометки:
  ЧАСТИ    — в ответе статья названа целиком, в перечне — только её части;
  ОГОВОРКА — в перечне у позиции есть оговорка, в ответе после статьи скобок нет;
  ЛИШНЯЯ   — в ответе после статьи стоит оговорка, в перечне её нет;
  НЕТ      — (с ключом -m) позиции перечня из тех же глав, которых в предложении нет; печатается, если в
             предложении нет слов «и другие», «в частности», «например», «в том числе», «ряд», «отдельные».
Оговорка в акте относится к позиции, после которой стоит; в ответе скобка после группы статей засчитывается всем
статьям группы. Пометка — повод прочитать предложение рядом с нормой.
  -v   печатать и предложения без пометок.
"""
import re, sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawtext as L
from listcheck import dec, glue, spans, key, REF

NUM = r'\d+\.\d+'
PARTS = r'(?:\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?(?:\s*(?:,|и)\s*)?)+'

def parse_law(t):
    """Возвращает список позиций: dict(kind, a, b, parts, qual, raw)."""
    t = re.sub(r'\s+', ' ', t)
    quals = []
    def stash(m):
        quals.append(m.group(1).strip()); return ' ⟦%d⟧ ' % (len(quals) - 1)
    for _ in range(2): t = re.sub(r'\(([^()]*)\)', stash, t)
    t = re.sub(r'\s+', ' ', t)
    items = []
    rx = re.compile(r'стать(?:ей|ями|ьями)\s+((?:%s(?:\s*[-–]\s*%s)?(?:\s*⟦\d+⟧)?(?:\s*(?:,|и)\s*)?)+)'
                    r'|((?:част(?:ью|ями)\s+%s\s*(?:⟦\d+⟧)?\s*(?:и\s+)?)+)статьи\s+(%s)\s*(⟦\d+⟧)?' % (NUM, NUM, PARTS, NUM))
    for m in rx.finditer(t):
        if m.group(1):
            for x in re.finditer(r'(%s)(?:\s*[-–]\s*(%s))?(?:\s*⟦(\d+)⟧)?' % (NUM, NUM), m.group(1)):
                a, b = x.group(1), x.group(2) or x.group(1)
                items.append(dict(kind='art' if a == b else 'range', a=a, b=b, parts=None,
                                  qual=quals[int(x.group(3))] if x.group(3) else None, raw=x.group(0).strip()))
        else:
            # «частями 1, 2 и частью 3 (в части…) статьи 8.28» — у каждой группы частей своя оговорка
            for g in re.finditer(r'част(?:ью|ями)\s+(%s)\s*(?:⟦(\d+)⟧)?' % PARTS, m.group(2)):
                q = g.group(2) if g.group(2) else (m.group(4)[1:-1] if m.group(4) else None)
                items.append(dict(kind='parts', a=m.group(3), b=m.group(3),
                                  parts=[(dec(p), dec(r)) for p, r in spans(g.group(1))],
                                  qual=quals[int(q)] if q is not None else None,
                                  raw='ч. %s ст. %s' % (g.group(1).strip(' ,и'), m.group(3))))
    return items

def in_range(a, lo, hi):
    ch, n = key(a); (c1, n1), (c2, n2) = key(lo), key(hi)
    if n1 > n2:
        s = lo.split('.', 1)[1]; n1 = float(s[:-1] + '.' + s[-1])
    return c1 == c2 == ch and n1 <= n <= n2

def law_for(a, items):
    """Позиции перечня, относящиеся к статье a (номер из ответа, «19.4.1»)."""
    g = glue(a); out = []
    for it in items:
        if it['kind'] == 'range':
            if in_range(a, it['a'], it['b']): out.append(it)
        elif it['a'] == g: out.append(it)
    return out

def covered(it, ans):
    """Названа ли позиция перечня в ответе: ans — список (a, b) статей и диапазонов из ответа, склеенных."""
    for a, b in ans:
        if a == b:
            if it['kind'] == 'range':
                if in_range_g(a, it['a'], it['b']): return True
            elif it['a'] == a: return True
        else:
            lo, hi = kg(a), kg(b)
            x, y = kg(it['a']), kg(it['b'])
            if lo[0] == x[0] and lo <= x and y <= hi: return True
    return False

def kg(a):
    """Ключ склеенного номера из акта: «19.41» → (19, 4.1), если статьи 19.41 в главе быть не может по соседям — не знаем,
    поэтому сравнение приблизительное: берём число после точки как есть."""
    ch, n = a.split('.', 1)
    return int(ch), float(n)

def in_range_g(a, lo, hi):
    return kg(lo)[0] == kg(a)[0] and kg(lo) <= kg(a) <= kg(hi)

HEDGE = re.compile(r'и друг|и др\.|в частности|например|в том числе|\bряд\b|\bряда\b|отдельны|некоторы|прежде всего|среди них|такие как|основн', re.I)

def ans_items(seg):
    """Позиции ответа: (статья, статья_конца, части|None, оговорка|None, начало)."""
    s = seg.replace('**', '').replace('__', '')
    out = []
    for m in REF.finditer(s):
        tail = s[m.end():m.end() + 6]
        q = re.match(r'\s*(?://)?\s*\(([^()]*)\)', s[m.end():])
        qual = q.group(1) if q else None
        if m.group(2):
            out.append((m.group(2), m.group(2), [(float(x), float(y)) for x, y in spans(m.group(1))], qual, m.start()))
        else:
            grp = spans(m.group(3))
            for x, y in grp: out.append((x, y, None, qual, m.start()))
    return out

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(args) < 4: sys.exit(__doc__)
    d, lawfile, art, part = args[:4]; point = args[4] if len(args) > 4 else None
    t = re.sub(r'\s+', ' ', L.unit(lawfile, art, part, None) or '')
    t = re.sub(r'\((?:В редакции|Дополнение|Пункт|Часть|Абзац)[^()]*\)', ' ', t)
    if point:
        m = re.search(r'(?:^|[;:.]\s+)%s\) (.*?)(?=;\s+\d+\) |$)' % re.escape(point), t)
        t = m.group(1) if m else ''
    items = parse_law(t)
    if not items: sys.exit('перечень не разобран')
    want = re.compile((r'п\.\s*(?:[\d.]+\s*(?:,|и|–|-)\s*)*%s(?![\d.])[^/]{0,24}' % re.escape(point) if point else '')
                      + r'ч\.\s*%s\s*ст\.\s*%s(?![\d.])' % (re.escape(part), re.escape(art)))
    other = re.compile(r'(?:ч\.\s*[\d.]+\s*)?ст\.\s*(?:23\.\d+|28\.3)(?![\d.])')
    tot = flagged = 0
    for f in sorted(glob.glob(os.path.join(d, 'q*.txt'))):
        for i, line in enumerate(open(f, encoding='utf-8').read().split('\n'), 1):
            for sent in re.split(r'(?<=[.;])\s+(?=[А-ЯЁ*«\-/])', line):
                m = want.search(sent)
                if not m: continue
                tot += 1
                # кусок предложения, относящийся к этой норме: от ссылки до следующей ссылки на другой перечень
                rest = sent[m.end():]; nx = other.search(rest)
                seg = rest[:nx.start()] if nx else rest
                if not REF.search(seg):
                    before = sent[:m.start()]; pv = list(other.finditer(before))
                    seg = before[pv[-1].end():] if pv else before
                ai = [x for x in ans_items(seg) if 5 <= int(x[0].split('.')[0]) <= 21]
                notes = []
                for a, b, parts, qual, _ in ai:
                    if a != b:
                        continue
                    li = law_for(a, items)
                    if not li: continue
                    whole = [it for it in li if it['kind'] != 'parts']
                    if parts is None and not whole:
                        ps = ', '.join(it['raw'] for it in li)
                        if not qual: notes.append('ЧАСТИ ст. %s: в перечне «%s»' % (a, ps))
                    lq = [it['qual'] for it in li if it['qual']]
                    if parts is not None:
                        lq = [it['qual'] for it in li if it['qual'] and (it['kind'] != 'parts' or any(lo <= p <= hi for lo, hi in it['parts'] for p, _ in parts))]
                    if lq and not qual: notes.append('ОГОВОРКА ст. %s: в перечне «(%s)»' % (a, lq[0][:110]))
                    if qual and not [it for it in li if it['qual']] and not (parts is None and not whole):
                        notes.append('ЛИШНЯЯ ст. %s: в ответе «(%s)», в перечне оговорки нет' % (a, qual[:60]))
                if '-m' in sys.argv and ai and not HEDGE.search(sent):
                    chs = {int(x[0].split('.')[0]) for x in ai}
                    have = [(glue(a), glue(b)) for a, b, _, _, _ in ai]
                    miss = [it['raw'] for it in items if int(it['a'].split('.')[0]) in chs and not covered(it, have)]
                    if miss: notes.append('НЕТ (%d): %s' % (len(miss), '; '.join(miss)[:420]))
                if notes or '-v' in sys.argv:
                    flagged += bool(notes)
                    print('%s:%d' % (os.path.basename(f)[:-4], i))
                    for n in notes: print('    ' + n)
                    print('    > ' + sent.strip()[:900])
    print('-- предложений со ссылкой на перечень: %d, с пометками: %d (позиций в перечне: %d, с оговоркой: %d)'
          % (tot, flagged, len(items), sum(1 for it in items if it['qual'])))
