#!/usr/bin/env python3
"""podved26.py SRC [--v1] [--all] [N1 N2] — подведомственность по КоАП РФ.
Из текста КоАП РФ (html-редакция) разбираются перечни статей в ч. 1, 1.1–3 ст. 23.1, ч. 1 и пунктах ч. 2 ст. 23.3,
пунктах ч. 2 ст. 28.3, ч. 1 ст. 28.4, ч. 1 ст. 23.85. В ответах берётся каждый отрезок строки (до «;» или конца предложения),
где стоит ссылка на одну из этих норм; все названные в отрезке статьи глав 5–21 ищутся в перечне этой нормы.
Печатается то, чего в перечне нет (или есть только отдельными частями, а в ответе статья названа целиком)."""
import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = [a for a in sys.argv[1:] if not a.startswith('--')]; flags = [a for a in sys.argv[1:] if a.startswith('--')]
sys.argv = [sys.argv[0], args[0], 'x']
import koap25 as KO
def tup(s): return tuple(int(x) for x in s.split('.') if x.isdigit())
def norm_num(tok):
    tok = tok.strip().strip('.').strip()
    tok = re.sub(r'^(\d+(?:\.\d+)?) (\d+)$', r'\1.\2', tok)
    return tok if re.fullmatch(r'\d+(?:\.\d+)*', tok) else None
def rng(tok):
    tok = tok.strip()
    if not tok: return None
    m = re.split(r'\s[-–]\s|–', tok)
    a = norm_num(m[0]); b = norm_num(m[-1])
    if not a or not b: return None
    return (tup(a), tup(b))
def strip_par(t):
    for _ in range(4): t = re.sub(r'\([^()]*\)', ' ', t)
    return re.sub(r'\s+', ' ', t)
def parse_law(t):
    """[(арт_от, арт_до, [(ч_от, ч_до)…] | None)]"""
    t = strip_par(t); res = []; pos = 0
    for m in re.finditer(r'стать(ей|ями|и|ях|ям)\s+([\d\. ,\-–и]+)', t):
        pre = t[pos:m.start()]; pos = m.end()
        pp = None
        k = pre.rfind('част')
        if m.group(1) == 'и' and k >= 0:
            seg = pre[k:]
            # все «частью/частями …» подряд перед «статьи»
            k0 = k
            while True:
                j = pre.rfind('част', 0, k0)
                if j < 0 or not re.fullmatch(r'част\w+\s+[\d ,\-–и]+', pre[j:k0].strip() + ' ') and not re.fullmatch(r'част\w+\s+[\d ,\-–и]+,?\s*', pre[j:k0]): break
                k0 = j
            seg = pre[k0:]
            seg = re.sub(r'част\w+', ',', seg)
            pp = [r for r in (rng(x) for x in re.split(r',| и ', seg)) if r]
        toks = [x for x in re.split(r',| и ', m.group(2))]
        first = True
        for x in toks:
            r = rng(x)
            if not r: continue
            res.append((r[0], r[1], pp if first else None)); first = False
    return res
def law_text(art, part, punkt=None):
    out = []
    for A in KO.art(art):
        P = KO.parts(A)
        if part not in P: continue
        t = P[part]
        if punkt:
            ms = list(re.finditer(r'(?<![\d.])(\d+(?: \d+)?)\)\s', t))
            for i, m in enumerate(ms):
                if m.group(1).replace(' ', '.') == punkt:
                    out.append(t[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(t)]); break
        else: out.append(t)
    return out[0] if out else ''
CACHE = {}
def lawset(key):
    if key not in CACHE:
        art, part, punkt = key
        CACHE[key] = parse_law(law_text(art, part, punkt))
    return CACHE[key]
def inlaw(S, a, parts):
    """'да' | 'часть' (статья есть, но не эта часть / названа целиком при частичном перечне) | 'нет'"""
    hit = [e for e in S if e[0] <= a <= e[1]]
    if not hit: return 'нет'
    if any(e[2] is None for e in hit): return 'да'
    lawp = [r for e in hit for r in e[2]]
    if not parts: return 'часть'
    for p in parts:
        for q in (p[0], p[1]):
            if not any(lo <= q <= hi for lo, hi in lawp): return 'часть'
    return 'да'
JRE = re.compile(r'(?:п\. (\d+(?:\.\d+)?) )?ч\. (\d+(?:\.\d+)?) ст\. (23\.1|23\.3|28\.3|28\.4|23\.85)(?![\d.])')
ARE = re.compile(r'(?:ч\. ([\d\.,–\- и]+?) )?ст\. (\d+\.\d+(?:\.\d+)?(?:[–-]\d+\.\d+(?:\.\d+)?)?(?:, \d+\.\d+(?:\.\d+)?(?:[–-]\d+\.\d+(?:\.\d+)?)?(?! ст\.))*)')
def check(tag, line):
    txt = line.replace('//', '').replace('**', '')
    for seg in re.split(r';\s|(?<=[а-яё\)»])\.\s+(?=[А-ЯЁ])', txt):
        js = [(m.start(), (m.group(3), m.group(2), m.group(1))) for m in JRE.finditer(seg)]
        js = [j for j in js if not (j[1][0] == '28.3' and not j[1][2]) and not (j[1][0] == '23.1' and j[1][1] not in ('1', '2', '1.1', '1.2', '1.3', '3'))]
        for m in re.finditer(r'(?<!ч\. \d )(?<!ч\. \d\.\d )(?<![\d.])ст\. (23\.1|23\.3|28\.3)(?![\d.])', seg):
            if '--words' in flags and not any(abs(j[0] - m.start()) < 12 for j in js):
                js.append((m.start(), {'23.1': ('23.1', '1', None), '23.3': ('23.3', '1', None), '28.3': ('28.3', '2', '1')}[m.group(1)]))
        if not js and '--words' in flags:
            low = seg.lower()
            if re.search(r'рассматрива\w+ (?:только )?(?:мировы\w+ )?суд|суд\w* рассматрива|— суд(?:ья|ьи)\b|только суд', low): js.append((low.find('суд'), ('23.1', '1', None)))
            if re.search(r'(?:полици\w+|орган\w* внутренних дел|госавтоинспекци\w+)[^.;]{0,40}рассматрива|рассматрива\w+[^.;]{0,30}(?:полици|орган\w* внутренних дел|госавтоинспекци)', low): js.append((low.find('рассматрива'), ('23.3', '1', None)))
            if re.search(r'протокол\w*[^.;]{0,60}(?:полици|внутренних дел)|(?:полици\w+|внутренних дел)[^.;]{0,40}протокол', low) and 'рассматрива' not in low: js.append((low.find('протокол'), ('28.3', '2', '1')))
        if not js: continue
        for m in ARE.finditer(seg):
            parts = None
            if m.group(1):
                parts = [r for r in (rng(x) for x in re.split(r',| и ', m.group(1))) if r]
            first = True
            for x in m.group(2).split(','):
                x = x.strip().rstrip('.')
                r = rng(x)
                if not r: continue
                if not (5 <= r[0][0] <= 21): continue
                pos, key = min(js, key=lambda j: abs(j[0] - m.start()))
                S = lawset(key)
                if not S: print('%s ?? нет текста нормы %s' % (tag, key)); continue
                for a in (r[0], r[1]):
                    v = inlaw(S, a, parts if first else None)
                    if v != 'да' or '--all' in flags:
                        print('%s [%s] %s ст. %s ↔ %s ч. %s ст. %s | %s' % (tag, v, ('ч. ' + m.group(1)) if (m.group(1) and first) else '', '.'.join(map(str, a)), ('п. %s' % key[2]) if key[2] else '', key[1], key[0], seg.strip()[:230]))
                first = False
if __name__ == '__main__':
    lo, hi = (int(args[1]), int(args[2])) if len(args) > 2 else (1, 149)
    base = os.path.join(HERE, '..')
    if '--v1' in flags:
        files = sorted(glob.glob(os.path.join(base, 'adp', 'q*.txt')))
    else:
        files = [os.path.join(base, 'adp2', 'q%03d.txt' % n) for n in range(lo, hi + 1)]
    n = 0
    for f in files:
        for i, line in enumerate(open(f, encoding='utf-8'), 1):
            if 'ст. 23.' in line or 'ст. 28.' in line or '--words' in flags:
                check('%s:%d' % (os.path.basename(f)[:28], i), line); n += 1
    print('строк со ссылками на нормы о подведомственности:', n)
