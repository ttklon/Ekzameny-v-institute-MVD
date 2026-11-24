#!/usr/bin/env python3
"""lawtext.py — разбор текста нормативного акта, извлечённого kextract.py: статьи, части, пункты, числа.

Запуск для печати нормы:
  lawtext.py ФАЙЛ СТАТЬЯ [ЧАСТЬ [ПУНКТ]]     статья кодекса или закона (часть «прим» — примечания)
  lawtext.py ФАЙЛ -p ПУНКТ                    пункт акта без статей (приказ, указ, постановление Пленума)
Остальное — функции для refcheck.py.
"""
import re, sys, functools

def load(path):
    t = open(path, encoding='utf-8').read().replace('\xad', '')
    t = re.sub(r'@@ \d+(?: \| \S+)?', ' ', t); t = re.sub(r'Стр\. \d+ из \d+', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    # «1 1 . Судья» (надстрочный знак через пробел) → «1.1. Судья»
    return re.sub(r'(?<= )(\d{1,3}) (\d) ?\. (?=[А-ЯЁ(«])', r'\1.\2. ', t)

@functools.lru_cache(maxsize=None)
def text(path): return load(path)

def _key(c):
    try: return [int(x) for x in c.split('.')]
    except ValueError: return None

def _fix(raw, prev):
    """«3892» после «389.1» → «389.2»; «12.211» после «12.21» → «12.21.1»: из вариантов разбивки берётся ближайший следующий номер"""
    if prev is None: return raw
    last = raw.split('.')[-1]; head = raw.split('.')[:-1]; cands = [raw]
    for k in (1, 2):
        if len(last) > k and last[-k] != '0': cands.append('.'.join(head + [last[:-k], last[-k:]]))
    pk = _key(prev); ok = [(_key(c), c) for c in cands if _key(c) and pk and _key(c) > pk]
    return min(ok)[1] if ok else raw

@functools.lru_cache(maxsize=None)
def articles(path):
    """номер статьи → текст статьи (при повторах — самый длинный: оглавление короче)"""
    t = text(path)
    t = re.sub(r'(Статья \d+(?:\.\d+)?) (\d{1,2}) ?\. (?=[А-ЯЁ(])', r'\1.\2. ', t)   # «Статья 19.15 1 .» → «Статья 19.15.1.»
    if 'Конституци' in t[:3000] and 'Статья 2 ' in t[:20000]:                          # в Конституции у статьи нет названия: «Статья 55 1. Перечисление…»
        t = re.sub(r'Статья (\d{1,3})\.1\. (?=[А-ЯЁ])', r'Статья \1. Текст 1. ', t); t = re.sub(r'Статья (\d{1,3}) (?=[А-ЯЁ])', r'Статья \1. Текст ', t)
    out = {}; ms = list(re.finditer(r'(?<![«"\w])Статья (\d+(?:\.\d+)*)\.? (?=[А-ЯЁ(])', t)); prev = None
    for i, m in enumerate(ms):
        n = _fix(m.group(1), prev)
        body = t[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(t)]
        if len(body) > len(out.get(n, '')): out[n] = body
        prev = n
    return out

PM = re.compile(r'(?<= )(\d{1,3}(?:\.\d{1,2})?)\. (?=[А-ЯЁ«(\[])')
def parts(body):
    """номер части → текст; 'прим' — примечания. Пустой словарь частей (кроме 'прим') — части не нумерованы (ТК РФ)"""
    note = re.search(r' Примечани[ея]\s?[.:] ', body); main = body[:note.start()] if note else body
    out = {}; prev = '0'; marks = []
    h = re.match(r'\s*Статья [\d.]+\s', main); h = h.end() if h else 0
    for m in PM.finditer(main, h):
        raw = m.group(1); cands = [raw]
        if '.' not in raw and len(raw) >= 2: cands += [raw[:i] + '.' + raw[i:] for i in range(1, len(raw)) if raw[i] != '0']
        pk = _key(prev); ok = [c for c in cands if _key(c) > pk and _key(c)[0] <= pk[0] + 1]
        if not ok: continue
        n = min(ok, key=_key); marks.append((n, m.start())); prev = n
    for i, (n, s) in enumerate(marks): out[n] = main[s:marks[i + 1][1] if i + 1 < len(marks) else len(main)]
    if note: out['прим'] = body[note.start():]
    return out

def point(u, p):
    """пункт «3)», «3.1)», «а)» внутри части или статьи"""
    p = p.strip('«»"'); m = None
    for f in [p] + ([p.replace('.', ' '), p.replace('.', '')] if '.' in p else []):      # «19.1)» в тексте бывает «19 1 )» и «191)»
        ms = list(re.finditer(r'(?<= )%s ?\) ' % re.escape(f), ' ' + u))
        if ms:
            m = ms[-1] if (f == p and len(p) > 1 and p.isdigit()) else ms[0]          # «31)» встречается дважды: сначала это «3.1)» с надстрочной единицей, затем настоящий п. 31
            break
    if not m: return None
    kind = r'\d+(?:\.\d+)?' if p[0].isdigit() else r'[а-яё]'
    rest = (' ' + u)[m.end():]; m2 = re.search(r'(?<= )%s\) ' % kind, rest)
    return (' ' + u)[m.start():m.end() + (m2.start() if m2 else len(rest))]

def act_points(path, p):
    """все места акта без статей, похожие на начало пункта p («6. Текст», «8.2. Текст»): у акта и приложений своя нумерация"""
    t = text(path); out = []; p = p.strip('«»"')
    forms = {p, p.replace('(', '.').replace(')', ''), p.replace('(', ' ').replace(')', '')}
    if re.fullmatch(r'\d+\.\d+', p): forms.add(p.replace('.', '(') + ')')                 # «5.1» в постановлениях Пленума пишется «5(1).»
    for f in forms:
        k = _key(f.replace(' ', '.').replace('(', '.').replace(')', ''))
        nxt = []
        if k:
            nxt.append('.'.join(map(str, k[:-1] + [k[-1] + 1])))
            if len(k) > 1: nxt.append('.'.join(map(str, k[:-2] + [k[-2] + 1])))
        for m in re.finditer(r'(?<= )%s\.? (?=[А-ЯЁ«(\[])' % re.escape(f), t):
            if not m.group().rstrip().endswith('.') and len(k or []) < 2: continue
            rest = t[m.end():m.end() + 150000]; e = None
            for q in nxt:
                m2 = re.search(r' %s\.? (?=[А-ЯЁ«(\[])' % re.escape(q), rest)
                if m2 and (e is None or m2.start() < e): e = m2.start()
            out.append(t[m.start():m.end() + (e if e is not None else 2500)][:150000])
    return out

MARK = re.compile(r'\((?:[А-ЯЁа-яё][^()]{0,60})?(?:в ред(?:акции|\.)|введен\w*|утратил\w*|дополнен\w*|см\. текст)[^()]*(?:\([^()]*\)[^()]*)*\)', re.I)
def strip_marks(u):
    """убирает пометки о редакции — «(В редакции Федерального закона от … № …)», «(в ред. …)», «(см. текст в предыдущей редакции)»"""
    return MARK.sub(' ', u)

# ---------- числа ----------
_W = {1: 'один одна одно одного одной одному одним одну одном', 2: 'два две двух двум двумя двое двоих', 3: 'три трех трем тремя трое троих',
      4: 'четыре четырех четырем четырьмя четверо', 5: 'пять пяти пятеро', 6: 'шесть шести', 7: 'семь семи', 8: 'восемь восьми',
      9: 'девять девяти', 10: 'десять десяти', 11: 'одиннадцать одиннадцати', 12: 'двенадцать двенадцати', 13: 'тринадцать тринадцати',
      14: 'четырнадцать четырнадцати', 15: 'пятнадцать пятнадцати', 16: 'шестнадцать шестнадцати', 17: 'семнадцать семнадцати',
      18: 'восемнадцать восемнадцати', 19: 'девятнадцать девятнадцати', 20: 'двадцать двадцати', 30: 'тридцать тридцати', 40: 'сорок сорока',
      50: 'пятьдесят пятидесяти', 60: 'шестьдесят шестидесяти', 70: 'семьдесят семидесяти', 80: 'восемьдесят восьмидесяти',
      90: 'девяносто девяноста', 100: 'сто ста', 200: 'двести двухсот', 300: 'триста трехсот', 400: 'четыреста четырехсот',
      500: 'пятьсот пятисот', 600: 'шестьсот шестисот', 700: 'семьсот семисот', 800: 'восемьсот восьмисот', 900: 'девятьсот девятисот',
      1.5: 'полтора полутора полуторы'}
WORD = {w: v for v, ws in _W.items() for w in ws.split()}
_PRE = {'одно': 1, 'двух': 2, 'трех': 3, 'четырех': 4, 'пяти': 5, 'шести': 6, 'семи': 7, 'восьми': 8, 'девяти': 9, 'десяти': 10,
        'двенадцати': 12, 'пятнадцати': 15, 'двадцати': 20, 'тридцати': 30, 'сорока': 40, 'шестидесяти': 60, 'девяноста': 90, 'полутора': 1.5}
PRE = re.compile(r'(%s)(дневн|суточн|месячн|летн|недельн|часов|кратн|годичн|минутн)' % '|'.join(sorted(_PRE, key=len, reverse=True)))
TOK = re.compile(r'\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?![\d])|\d+(?:,\d+)?|[а-яё]+')
UNIT1 = re.compile(r'(год|месяц|сут|час|недел|ден|дня|дню|дне|раз|трет|втор|четверт|процент|экземпляр|минут|тысяч|миллион)')
def _mult(w):
    if w.startswith('тысяч') or w == 'тыс': return 1000
    if w.startswith('миллион') or w == 'млн': return 10 ** 6
    if w.startswith('миллиард') or w == 'млрд': return 10 ** 9
def nums(s, answer=False):
    """множество чисел текста: цифры («3 000», «1,5») и числительные («сорока восьми», «двух тысяч пятисот», «трёхдневный»).
    «от трёх до пяти тысяч» даёт 3000 и 5000 (для нормы ещё и 3). answer=True: «один» считается только перед единицей измерения."""
    s = s.lower().replace('ё', 'е'); toks = list(TOK.finditer(s)); vals = []; i = 0
    while i < len(toks):
        w = toks[i].group(); isd = w[0].isdigit()
        if isd: v = float(w.replace(',', '.')) if ',' in w else int(re.sub(r'\D', '', w))
        else:
            v = WORD.get(w)
            if v is None:
                m = PRE.match(w)
                if m: vals.append([_PRE[m.group(1)], i, i + 1, 0])
                i += 1; continue
        j = i + 1; total = 0; cur = v; mult = 0
        while j < len(toks) and not s[toks[j - 1].end():toks[j].start()].strip(' \u00a0'):
            w2 = toks[j].group(); m_ = _mult(w2)
            if m_ and cur: total += cur * m_; cur = 0; mult = max(mult, m_); j += 1; continue
            v2 = None if (isd or w2[0].isdigit()) else WORD.get(w2)
            if v2 and not cur and total and isinstance(v2, int) and v2 < 1000: cur = v2; j += 1; continue
            if v2 and cur and isinstance(cur, int) and isinstance(v2, int) and ((v2 < 10 and cur % 10 == 0 and cur % 100 != 10) or (10 <= v2 < 100 and cur % 100 == 0)):
                cur += v2; j += 1; continue
            break
        val = total + cur
        if answer and val == 1 and not isd:
            nxt = toks[j].group() if j < len(toks) else ''
            if not UNIT1.match(nxt): i = j; continue
        vals.append([val, i, j, mult]); i = j
    out = set()
    for k, (val, a, b, mult) in enumerate(vals):
        prop = None
        if not mult and k + 1 < len(vals) and vals[k + 1][3] and val < vals[k + 1][0] / vals[k + 1][3]:
            gap = s[toks[b - 1].end():toks[vals[k + 1][1]].start()].strip()
            if gap in ('до', '–', '-', '—', 'или', 'и', '−'): prop = val * vals[k + 1][3]
        if prop is not None:
            out.add(prop)
            if not answer: out.add(val)
        else: out.add(val)
    return {int(x) if float(x).is_integer() else x for x in out}

STOP = set('котор также может могут должн являе этого этому этом таких такой такие иных иной либо если случа случаях указа настоя соотв предус устан федер закон россий стать части пункт подпу числе после более менее течен между через лица лицо лицом'.split())
def stems(s):
    return {w[:5] for w in re.findall(r'[а-яё]{4,}', s.lower().replace('ё', 'е'))} - STOP

def unit(path, art, part=None, pnt=None):
    """текст статьи / части / пункта; None, если не найдено"""
    A = articles(path); b = A.get(str(art))
    if b is None: return None
    if part:
        P = parts(b); u = P.get(str(part))
        if u is None: return None
        b = u
    if pnt:
        u = point(b, str(pnt))
        if u is None: return None
        b = u
    return b

if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) >= 3 and a[1] == '-p':
        for u in act_points(a[0], a[2]): print(u[:int(a[3]) if len(a) > 3 else 6000], '\n-----')
    elif len(a) >= 2:
        u = unit(a[0], *a[1:4]); print(u if u else 'не найдено; статей: %d' % len(articles(a[0])))
        if u and len(a) == 2: print('\n-- части:', ' '.join(parts(u)))
    else: print(__doc__)
