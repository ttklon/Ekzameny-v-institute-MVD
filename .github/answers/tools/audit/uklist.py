#!/usr/bin/env python3
"""uklist.py ПАПКА_ОТВЕТОВ ФАЙЛ_УПК [-v]

Подследственность в ответах по уголовному праву против перечней УПК.
Разбирает перечни статей УК в п. 1 ч. 3 ст. 150 (дознание), подп. «а» п. 1, п. 2 и п. 3 ч. 2 ст. 151 УПК
(следователи Следственного комитета, органов федеральной службы безопасности, органов внутренних дел) и
ч. 5 ст. 151 (следователи органа, выявившего преступление). В ответах берёт каждое предложение со ссылкой на
одну из этих норм; статьи и части УК, названные в предложении перед ссылкой, проверяет на вхождение в перечень.
Если статья в предложении не названа, берётся статья из заголовка ответа. Пометка — повод прочитать предложение.
  -v   печатать и предложения без расхождений.
"""
import re, sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawtext as L

ORD = {'первой': 1, 'второй': 2, 'третьей': 3, 'четвертой': 4, 'пятой': 5, 'шестой': 6, 'седьмой': 7, 'восьмой': 8,
       'девятой': 9, 'десятой': 10}
OW = '(?:' + '|'.join(ORD) + r')\d?'

def art(n):
    """«1161» в тексте кодекса — статья 116.1 (индекс слит с номером)."""
    return float(n) if len(n) <= 3 else float(n[:3] + '.' + n[3:])

def ordv(w):
    m = re.fullmatch(r'([а-я]+)(\d?)', w)
    return ORD[m.group(1)] + (int(m.group(2)) / 10 if m.group(2) else 0)

def parse(t):
    """[(lo, hi, parts)], parts — None (вся статья) или [(lo, hi)]."""
    t = re.sub(r'\s+', ' ', t).replace('ё', 'е')
    out = []
    rx = re.compile(r'(?<![\d.])(\d{3,5})(?:\s*-\s*(\d{3,5}))?(?:\s+част(?:ью|ями)\s+((?:%s(?:\s*(?:,|и|-)\s*)?)+))?' % OW)
    for m in rx.finditer(t):
        lo = art(m.group(1)); hi = art(m.group(2)) if m.group(2) else lo
        if lo > 362: continue
        parts = None
        if m.group(3):
            parts = []
            for tok in re.split(r'\s*(?:,|\bи\b)\s*', m.group(3).strip(' ,')):
                ab = [x for x in re.split(r'\s*-\s*', tok.strip()) if x]
                if ab: parts.append((ordv(ab[0]), ordv(ab[-1])))
        out.append((lo, hi, parts))
    return out

def covered(lst, a, p=None):
    """True — статья (часть) в перечне; 'parts' — статья в перечне только частями; False — нет."""
    res = False
    for lo, hi, parts in lst:
        if lo <= a <= hi:
            if parts is None: return True
            if p is not None and any(x <= p <= y for x, y in parts): return True
            res = 'parts'
    return res

def lists(upk):
    def cl(t):
        t = re.sub(r'\s+', ' ', t or '')
        for _ in range(2): t = re.sub(r'\((?:В редакции|Дополнение|Пункт|Подпункт|Часть)[^()]*\)', '', t)
        return t
    t150 = cl(L.unit(upk, '150', '3', None)); t150 = t150[:t150.find(' 2) по уголовным делам об иных')]
    t2 = cl(L.unit(upk, '151', '2', None))
    i1 = t2.find('а) о преступлениях'); i1b = t2.find(' б) о преступлениях', i1)
    i2 = t2.find(' 2) следователями органов федеральной службы'); i3 = t2.find(' 3) следователями органов внутренних дел')
    i4 = t2.find(' 4) ', i3)
    t5 = cl(L.unit(upk, '151', '5', None))
    return {'дознание (п. 1 ч. 3 ст. 150)': parse(t150), 'СК (подп. «а» п. 1 ч. 2 ст. 151)': parse(t2[i1:i1b]),
            'ФСБ (п. 2 ч. 2 ст. 151)': parse(t2[i2:i3]), 'ОВД (п. 3 ч. 2 ст. 151)': parse(t2[i3:i4 if i4 > 0 else None]),
            'выявивший орган (ч. 5 ст. 151)': parse(t5)}

KIND = [(r'п\.\s*1\s*ч\.\s*3\s*ст\.\s*150', 'дознание (п. 1 ч. 3 ст. 150)'),
        (r'подп\.\s*«а»\s*п\.\s*1\s*ч\.\s*2\s*ст\.\s*151', 'СК (подп. «а» п. 1 ч. 2 ст. 151)'),
        (r'(?<!подп\. «а» )п\.\s*2\s*ч\.\s*2\s*ст\.\s*151', 'ФСБ (п. 2 ч. 2 ст. 151)'),
        (r'п\.\s*3\s*ч\.\s*2\s*ст\.\s*151', 'ОВД (п. 3 ч. 2 ст. 151)'),
        (r'ч\.\s*5\s*ст\.\s*151', 'выявивший орган (ч. 5 ст. 151)')]
REF = re.compile(r'ч\.\s*((?:\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?(?:\s*(?:,|и)\s*)?)+)\s*(?:ст\.\s*(\d{3}(?:\.\d+)?))?|ст\.\s*((?:\d{3}(?:\.\d+)?(?:\s*[-–]\s*\d{3}(?:\.\d+)?)?(?:\s*(?:,|и)\s*)?)+)', re.I)

def claims(text, main):
    """[(статья, часть или None)] из текста перед ссылкой; «ч. 2 и 3» без статьи относится к статье, названной раньше, или к главной."""
    out, last = [], main
    for m in REF.finditer(text):
        if m.group(3):
            for tok in re.split(r'\s*(?:,|\bи\b)\s*', m.group(3).strip(' ,')):
                ab = [x for x in re.split(r'\s*[-–]\s*', tok) if x]
                for a in ab: out.append((float(a), None))
                if ab: last = float(ab[-1])
        else:
            a = float(m.group(2)) if m.group(2) else None
            ps = []
            for tok in re.split(r'\s*(?:,|\bи\b)\s*', m.group(1).strip(' ,')):
                ab = [x for x in re.split(r'\s*[-–]\s*', tok) if x]
                if not ab: continue
                lo, hi = float(ab[0]), float(ab[-1])
                ps += [lo, hi] + [float(x) for x in range(int(lo) + 1, int(hi))]
            if a is None:
                # статья стоит после следующих частей («ч. 1 и ч. 2 ст. 158») либо названа раньше
                nxt = re.match(r'[\s,и]*(?:ч\.[^с]*?)?ст\.\s*(\d{3}(?:\.\d+)?)', text[m.end():])
                a = float(nxt.group(1)) if nxt and re.match(r'\s*(?:,|и)\s*ч\.', text[m.end():]) else last
            if a is None: continue
            last = a
            out += [(a, p) for p in sorted(set(ps))]
    return out

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(args) < 2: sys.exit(__doc__)
    LS = lists(args[1])
    tot = flagged = 0
    for f in sorted(glob.glob(os.path.join(args[0], 'q*.txt'))):
        ls = open(f, encoding='utf-8').read().split('\n')
        hm = re.search(r'ст\.\s*(\d{3}(?:\.\d+)?)', ' '.join(ls[:3]))
        main = float(hm.group(1)) if hm else None
        for i, line in enumerate(ls, 1):
            if not re.search(r'ст\.\s*15[01]\s*(?:Уголовно-процессуального|УПК|того же)', line) and 'ст. 151 УПК' not in line: continue
            for cla in re.split(r';\s+', line):
                kinds = [k for rx, k in KIND if re.search(rx, cla)]
                if not kinds: continue
                pos = min(re.search(rx, cla).start() for rx, k in KIND if re.search(rx, cla))
                before = re.sub(r'//\(.*', '', cla[:pos]) if '//(' in cla[:pos] else cla[:pos]
                cs = claims(before, main) or ([(main, None)] if main else [])
                tot += 1
                bad = []
                for a, p in cs:
                    r = [covered(LS[k], a, p) for k in kinds]
                    if True in r: continue
                    name = ('ч. %g ' % p if p else '') + 'ст. %g' % a
                    bad.append(name + (' — в перечне другие части' if 'parts' in r else ' — нет в перечне') + ' [' + '; '.join(kinds) + ']')
                if bad or '-v' in sys.argv or not cs:
                    flagged += bool(bad) or not cs
                    print('%s:%d %s' % (os.path.basename(f)[:-4], i, '; '.join(bad) or ('статья не определена' if not cs else 'ок ' + str(cs))))
                    print('    ' + cla.strip()[:420])
    print('-- утверждений о подследственности: %d, с пометками: %d' % (tot, flagged))
