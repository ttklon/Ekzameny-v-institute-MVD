#!/usr/bin/env python3
"""koap25.py SRC show СТАТЬЯ [ЧАСТЬ] — текст статьи (части) КоАП РФ из источников.
koap25.py SRC check [N…] — каждое число в строке ответа рядом со ссылкой на статью КоАП РФ (размер штрафа, срок, возраст)
ищется в названной части названной статьи; печатаются числа, которых там нет (отдельно — нет и в статье целиком).
Число относится к ближайшей ссылке слева или справа в той же строке. «Полутора» и «1,5» приводятся к одному виду."""
import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K
src = sys.argv[1]
def _arts(f):
    raw = open(f, encoding='utf-8', errors='replace').read(); raw = re.sub(r'<\d+>', ' ', raw); raw = K.CLEAN.sub(' ', raw)
    res = {}; base = None; ms = list(re.finditer(r'Статья\s+(\d+)(?:\.(\d+))?(?:\s(\d)\s)?\s?\.\s+(?=[А-ЯЁ(])', raw))
    for i, m in enumerate(ms):
        a, b, c = m.group(1), m.group(2), m.group(3)
        if b is None: num = a
        elif c: num = '%s.%s.%s' % (a, b, c)
        elif base and base[0] == a and b.startswith(base[1]) and len(b) > len(base[1]): num = '%s.%s.%s' % (a, base[1], b[len(base[1]):])
        else: num = '%s.%s' % (a, b); base = (a, b)
        res[num] = res.get(num, '') + raw[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(raw)]
    return res
ARTS = [_arts(f) for f in sorted(glob.glob(os.path.join(src, '*КоАП РФ от 30.12.2001*.html.txt')) or glob.glob(os.path.join(src, 'e7501c*')))]
def art(n): return [A[n] for A in ARTS if n in A]
def parts(txt):
    """{номер части: текст} по HTML-тексту («  1.\xa0Текст», «  1 1 .\xa0Текст» = часть 1.1); 'прим' — примечания; '' — статья без частей"""
    t = txt; note = re.search(r'\s{2,}Примечани[ея]\s?[.:]', t); res = {}
    if note: res['прим'] = t[note.start():]; t = t[:note.start()]
    ms = list(re.finditer(r'(?:\s{2,}|\xa0\s*)(\d+)(?: (\d+) ?)?\.\xa0(?=[А-ЯЁ(«])', t))
    if not ms: res[''] = t; return res
    res['загл'] = t[:ms[0].start()]
    for i, m in enumerate(ms):
        k = m.group(1) + ('.' + m.group(2) if m.group(2) else '')
        res[k] = res.get(k, '') + t[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(t)]
    return res
def nums(t):
    t = t.lower().replace('ё', 'е'); t = re.sub(r'полутора', ' 1,5 ', t); t = re.sub(r'(\d),5\b', r' \g<1>p5 ', t).replace('1p5', '15000001').replace('2p5', '25000001').replace('0p5', '5000001').replace('7p5', '75000001')
    return {w for w in K.tokens(t) if w[0].isdigit()}
if __name__ == '__main__' and sys.argv[2] == 'show':
    for t in art(sys.argv[3])[-1:]:
        if len(sys.argv) > 4:
            p = parts(t)
            for k in sys.argv[4:]: print(re.sub(r'\s+', ' ', p.get(k, 'нет части ' + k + '; есть: ' + ', '.join(p))))
        else: print(re.sub(r'[ \t]*\n[ \t]*', ' ', t))
RX = re.compile(r'//(.+?)//|\*\*((?:Ч|Ст|ч|ст)\.\s*\d[^*]{0,40}?)\*\*')
UNIT = re.compile(r'\s*(?:–|—|-|до|или|и|,)?\s*(?:\d[\d \u00a0]*(?:,\d+)?\s*)?(?:тыс|млн|руб|сут|час|лет|год|месяц|дн[еяй]|недел|кратн|процент|%|минут|МРОТ)', re.I)
def sanction(pt):
    m = re.search(r'влеч[её]т\s+(.+)', re.sub(r'\s+', ' ', pt)); return (m.group(1) if m else re.sub(r'\s+', ' ', pt))[:420]
if __name__ == '__main__' and sys.argv[2] == 'check':
    only = [int(x) for x in sys.argv[3:]]; tot = bad = 0; A = os.path.join(HERE, '..', 'adp2') + '/'
    for n in (only or range(1, 150)):
        lines = open(A + 'q%03d.txt' % n, encoding='utf-8').read().split('\n'); hart = None; sart = None
        for i, line in enumerate(lines):
            if line.startswith('## '):
                m = re.findall(r'[Сс]т\.\s*(\d+\.\d+(?:\.\d+)?)', line); hart = m[-1] if m else None; sart = hart; continue
            if not line.strip() or line.startswith('#'): continue
            if line.startswith('!!'): hart = sart = None
            refs = []; cur = hart
            for m in RX.finditer(line):
                r = m.group(1) or m.group(2)
                if re.search(r'[А-ЯЁ]{2}|Закон|кодекс|Правил|Положени|Инструкц|приказ|Указ|постановлени', r[1:]) and not re.search(r'КоАП|административных правонарушениях', r): cur = None; continue
                am = re.findall(r'[Сс]т\.\s*(\d+\.\d+(?:\.\d+)?)', r); pm = re.search(r'[Чч]\.\s*(\d+(?:\.\d+)?)', r)
                if am: cur = am[-1]
                elif not pm: continue
                a_ = am[0] if am else (cur if m.start() > 6 or not hart else hart)
                if a_ and art(a_): refs.append((m.start(), m.end(), a_, pm.group(1) if pm else None))
                if line.startswith('!!') and am and sart is None: sart = am[-1]
                if line.startswith('!!') and not am and not cur: cur = sart
            if not refs: continue
            lead = refs[0] if refs[0][0] <= 6 else None
            body = RX.sub(lambda m: ' ' * len(m.group()), line)
            body = re.sub(r'(?:ст\.|ч\.|п\.|№|гл\.|подп\.|примечани[а-я]*|глав[а-я]+|стать[а-я]+)\s*\d+(?:\.\d+)*(?:\s*(?:,|и|–|—|-)\s*\d+(?:\.\d+)*)*', lambda m: ' ' * len(m.group()), body, flags=re.I)
            pos = 0
            for cl in re.split(r'(?<=[;.])\s', body):
                c0 = body.find(cl, pos); c1 = c0 + len(cl); pos = c1
                inref = [r for r in refs if c0 <= r[0] < c1]
                miss = []; cand = []
                for m in re.finditer(r'\d[\d \u00a0]*(?:,\d+)?|[а-яё]+', cl.lower()):
                    w = m.group().replace('ё', 'е')
                    if not (w[0].isdigit() or w in K.U or w == 'полутора'): continue
                    if not UNIT.match(cl[m.end():m.end() + 40]): continue
                    ns = nums(w)
                    if not ns: continue
                    p = c0 + m.start(); left = [r for r in inref if r[1] <= p][-1:]; right = [r for r in inref if r[0] >= p][:1]
                    cand = left + right + ([lead] if lead else [])
                    if not cand: continue
                    tot += 1; ok = False
                    for r in cand:
                        for t in art(r[2]):
                            P = parts(t); pt = P.get(r[3]) if r[3] else t
                            if pt is None: pt = ''
                            if ns <= nums(pt): ok = True
                    if not ok: miss.append((w.strip(), cand))
                if miss:
                    bad += 1; r = miss[0][1][0]; t = art(r[2])[-1]; P = parts(t); pt = P.get(r[3], 'НЕТ ЧАСТИ %s; части: %s' % (r[3], ', '.join(P))) if r[3] else t
                    inart = all(nums(w) <= nums(t) for w, _c in miss)
                    print('q%03d:%d [%s] у ч. %s ст. %s%s | %s\n      ЗАКОН: %s' % (n, i + 1, ', '.join(w for w, _c in miss), r[3], r[2], '' if inart else ' (нет и в статье)', cl.strip()[:260], sanction(pt)))
    print('чисел с единицей рядом со ссылкой на КоАП:', tot, 'мест с расхождением:', bad)
