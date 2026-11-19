#!/usr/bin/env python3
"""sancheck.py SRC — размеры штрафов и сроки (сутки, часы) рядом со ссылкой на статью КоАП РФ сверяются с текстом этой статьи:
число из ответа переводится в слова в родительном падеже («от 2 000 до 4 000 рублей» → «от двух тысяч до четырех тысяч рублей»)."""
import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cut25, qcheck2
from qcheck import norm
KO = qcheck2.KOAP
U = ['', 'одного', 'двух', 'трех', 'четырех', 'пяти', 'шести', 'семи', 'восьми', 'девяти', 'десяти', 'одиннадцати', 'двенадцати', 'тринадцати', 'четырнадцати',
     'пятнадцати', 'шестнадцати', 'семнадцати', 'восемнадцати', 'девятнадцати']
T = ['', '', 'двадцати', 'тридцати', 'сорока', 'пятидесяти', 'шестидесяти', 'семидесяти', 'восьмидесяти', 'девяноста']
H = ['', 'ста', 'двухсот', 'трехсот', 'четырехсот', 'пятисот', 'шестисот', 'семисот', 'восьмисот', 'девятисот']
def lt1000(n, fem=False):
    w = [H[n // 100]]; r = n % 100
    if r < 20: w.append(('одной' if fem and r == 1 else U[r]))
    else: w += [T[r // 10], ('одной' if fem and r % 10 == 1 else U[r % 10])]
    return ''.join(w)
def gen(n):
    s = ''
    if n >= 1000000: m = n // 1000000; s += lt1000(m) + ('миллиона' if m % 10 == 1 and m % 100 != 11 else 'миллионов'); n %= 1000000
    if n >= 1000: k = n // 1000; s += lt1000(k, True) + ('тысячи' if k % 10 == 1 and k % 100 != 11 else 'тысяч'); n %= 1000
    return s + lt1000(n)
NUM = r'(\d{1,3}(?:[  ]\d{3})+|\d+)(?:\s*(тыс\.|млн))?'
def val(a, mult): return int(re.sub(r'\D', '', a)) * {None: 1, '': 1, 'тыс.': 1000, 'млн': 1000000}[mult]
PATS = [(re.compile(r'от\s+' + NUM + r'\s+до\s+' + NUM + r'\s+(рублей|суток|часов)'), 2),
        (re.compile(NUM + r'\s*[–—-]\s*' + NUM + r'\s+(рублей|суток|часов)'), 2),
        (re.compile(r'до\s+' + NUM + r'\s+(рублей|суток|часов)'), 1),
        (re.compile(r'(?:штраф|в размере)\s+' + NUM + r'\s+(рублей)'), 1)]
END = re.compile(r'(?<![ (/]ч)(?<![ (/]п)(?<!ст)(?<!подп)(?<!гл)(?<![ (/]Ч)(?<!Ст)\. |; ')
tot = bad = skip = 0
for f in sorted(glob.glob(cut25.A + 'q*.txt')):
    n = int(f[-7:-4]); lines = open(f, encoding='utf-8').read().split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces)
    secart = None
    for (i, _z), line in pieces:
        if line.startswith('## '): secart = None
        refs = []
        for k, m in enumerate(cut25.REF.finditer(line)):
            act, art = res[((i, 0), k)]; disp = names[((i, 0), k)]
            if art and ((disp and qcheck2.act_files(disp)[0] == 'KOAP') or (not disp and re.match(r'\d+\.\d+', art))): refs.append((m.start(), art))
            elif disp: refs.append((m.start(), None))
        seen = set()
        for pat, cnt in PATS:
            for m in pat.finditer(line):
                if any(m.start() >= a and m.end() <= b for a, b in seen): continue
                seen.add((m.start(), m.end())); g = m.groups(); unit = g[-1]
                if cnt == 2:
                    a, b = val(g[0], g[1] or (g[3] if g[3] else None)), val(g[2], g[3]); key = 'от' + gen(a) + 'до' + gen(b) + unit
                else:
                    a = val(g[0], g[1]); key = ('до' if pat.pattern.startswith('до') else '') + gen(a) + unit
                before = [r for r in refs if r[0] < m.start()]; after = [r for r in refs if r[0] > m.start()]
                # ближайшая ссылка слева в пределах предложения, иначе первая справа до конца предложения
                seg_l = line[:m.start()]; cut_l = max([x.start() for x in END.finditer(seg_l)] or [-1])
                cand = [r for r in before if r[0] > cut_l]
                art = cand[-1][1] if cand else None
                if not cand:
                    seg_r = line[m.end():]; e = ([x.start() for x in END.finditer(seg_r)] or [len(seg_r)])[0] + m.end()
                    cand = [r for r in after if r[0] < e]; art = cand[0][1] if cand else (before[-1][1] if before else None)
                if not art and secart: art = secart
                if not art:
                    skip += 1
                    if len(sys.argv) > 2 and unit != 'часов': print('  ? q%03d:%d %s | %s' % (n, i + 1, m.group(0), line[max(0, m.start() - 150):m.end() + 30]))
                    continue
                tot += 1
                if not any(art in A and key in A[art] for A in KO):
                    bad += 1; print('q%03d:%d ст. %s: «%s» — нет в статье (%s)' % (n, i + 1, art, m.group(0), key))
                    if len(sys.argv) > 2: print('      ', line[max(0, m.start() - 230):m.end() + 60])
        am = re.findall(r'(?:[Сс]т\.|[Сс]тать[яеию])\s*(\d+\.\d+(?:\.\d+)?)', line)
        if am and (line.startswith('#') or not line.startswith('- ')): secart = am[-1]
print('проверено:', tot, 'расхождений:', bad, 'без статьи КоАП рядом:', skip)
