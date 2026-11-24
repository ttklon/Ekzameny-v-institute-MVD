#!/usr/bin/env python3
"""listcheck.py ПАПКА_ОТВЕТОВ ФАЙЛ_АКТА СТАТЬЯ ЧАСТЬ [ПУНКТ] [-v]

Сверка перечней статей. Норма-перечень (например, ч. 1 ст. 23.3 КоАП — что рассматривают органы внутренних дел,
п. 1 ч. 2 ст. 28.3 — по каким статьям они составляют протоколы) разбирается на пары «статья — части».
В ответах берётся каждое предложение со ссылкой на эту норму; статьи того же акта, названные в предложении,
проверяются на вхождение в перечень. Печатаются предложения, где статья или часть в перечень не входит.
Пометка — повод прочитать предложение: статья могла быть названа как раз как исключение («дел главы 7 в перечне нет»).
  -v   печатать и предложения без расхождений.
"""
import re, sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawtext as L

def dec(tok):
    """«51» в тексте акта — часть 5.1 (надстрочный индекс слит с номером); 11 и 12 остаются одиннадцатой и двенадцатой."""
    tok = tok.strip()
    if '.' in tok: return float(tok)
    if len(tok) == 2 and int(tok) > 12 and tok[1] in '123456789': return float(tok[0] + '.' + tok[1])
    return float(tok)

def glue(art):
    p = art.split('.')
    return p[0] + '.' + ''.join(p[1:]) if len(p) > 2 else art

def spans(s, sep=r'\s*[-–]\s*'):
    out = []
    for tok in re.split(r'\s*(?:,|\bи\b)\s*', s.strip(' ,')):
        tok = tok.strip()
        if not tok: continue
        ab = re.split(sep, tok)
        out.append((ab[0], ab[-1]))
    return out

def parse_law(t):
    t = re.sub(r'\s+', ' ', t)
    for _ in range(3): t = re.sub(r'\([^()]*\)', ' ', t)
    arts, ranges, parts, pend = set(), [], {}, []
    rx = re.compile(r'стать(?:ей|ями|ьями)\s+([\d.,\s–-]+)|част(?:ью|ями)\s+((?:\d+(?:\s*[-–]\s*\d+)?(?:\s*(?:,|и)\s*)?)+)|статьи\s+(\d+\.\d+)')
    for m in rx.finditer(t):
        if m.group(1):
            pend = []
            for a, b in spans(m.group(1)):
                if not re.fullmatch(r'\d+\.\d+', a) or not re.fullmatch(r'\d+\.\d+', b): continue
                if a == b: arts.add(a)
                else: ranges.append((a, b))
        elif m.group(2): pend += [(dec(a), dec(b)) for a, b in spans(m.group(2))]
        elif m.group(3):
            parts.setdefault(m.group(3), []).extend(pend); pend = []
    return arts, ranges, parts

def key(a):
    ch, n = a.split('.', 1)
    return int(ch), float(n.replace('.', '')) if n.count('.') == 0 else float(n.split('.')[0] + '.' + n.split('.')[1])

def art_in(a, arts, ranges):
    """a — номер статьи из ответа («19.15.1»). Возвращает True, если вся статья названа в перечне."""
    if glue(a) in arts: return True
    ch, n = key(a)
    for lo, hi in ranges:
        (c1, n1), (c2, n2) = key(lo), key(hi)
        if n1 > n2:   # «6.91 - 6.12» в акте — это 6.9.1–6.12: индекс слит с номером
            s = lo.split('.', 1)[1]; n1 = float(s[:-1] + '.' + s[-1])
        if c1 == c2 == ch and n1 <= n <= n2: return True
    return False

REF = re.compile(r'ч\.\s*((?:\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?(?:\s*(?:,|и)\s*)?)+)\s*ст\.\s*(\d+\.\d+(?:\.\d+)?)|ст\.\s*((?:\d+\.\d+(?:\.\d+)?(?:\s*[-–]\s*\d+\.\d+(?:\.\d+)?)?(?:\s*,\s*)?)+)', re.I)

def check(sent, law, skip):
    arts, ranges, parts = law
    bad = []
    for m in REF.finditer(sent):
        if m.group(2):
            a = m.group(2)
            if a in skip or int(a.split('.')[0]) < 5 or int(a.split('.')[0]) > 21: continue
            if art_in(a, arts, ranges): continue
            sp = parts.get(glue(a))
            if not sp: bad.append('ст. %s — статьи в перечне нет' % a); continue
            for x, y in spans(m.group(1)):
                for p in {float(x), float(y)}:
                    q = float(('%g' % p).replace('.', ''))   # «1.1» в акте напечатано как «11»
                    if not any(lo <= p <= hi or lo <= q <= hi for lo, hi in sp): bad.append('ч. %g ст. %s — части в перечне нет' % (p, a))
        else:
            for x, y in spans(m.group(3)):
                for a in {x, y}:
                    if a in skip or int(a.split('.')[0]) < 5 or int(a.split('.')[0]) > 21: continue
                    if art_in(a, arts, ranges): continue
                    if glue(a) in parts: bad.append('ст. %s — в перечне только части %s' % (a, ', '.join('%g' % lo if lo == hi else '%g–%g' % (lo, hi) for lo, hi in parts[glue(a)])))
                    else: bad.append('ст. %s — статьи в перечне нет' % a)
    return bad

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(args) < 4: sys.exit(__doc__)
    d, lawfile, art, part = args[:4]; point = args[4] if len(args) > 4 else None
    t = re.sub(r'\s+', ' ', L.unit(lawfile, art, part, None) or '')
    t = re.sub(r'\((?:В редакции|Дополнение|Пункт|Часть)[^()]*\)', ' ', t)
    if point:
        m = re.search(r'(?:^|[;:.]\s+)%s\) (.*?)(?=;\s+\d+\) |$)' % re.escape(point), t)
        t = m.group(1) if m else ''
    law = parse_law(t)
    if not (law[0] or law[1] or law[2]): sys.exit('перечень не разобран')
    want = (r'п\.\s*(?:[\d.]+\s*(?:,|и|–|-)\s*)*%s(?![\d.])[^/]{0,24}' % re.escape(point) if point else '') + r'ч\.\s*%s\s*ст\.\s*%s(?![\d.])' % (re.escape(part), re.escape(art))
    tot = flagged = 0
    for f in sorted(glob.glob(os.path.join(d, 'q*.txt'))):
        for i, line in enumerate(open(f, encoding='utf-8').read().split('\n'), 1):
            for sent in re.split(r'(?<=[.;])\s+(?=[А-ЯЁ*«\-/])', line):
                if not re.search(want, sent): continue
                tot += 1
                bad = check(sent, law, {art})
                if bad or '-v' in sys.argv:
                    flagged += bool(bad)
                    print('%s:%d %s' % (os.path.basename(f)[:-4], i, '; '.join(bad) or 'ок'))
                    print('    ' + sent.strip()[:700])
    print('-- предложений со ссылкой на перечень: %d, с пометками: %d (в перечне статей целиком: %d, диапазонов: %d, статей с частями: %d)'
          % (tot, flagged, len(law[0]), len(law[1]), len(law[2])))
