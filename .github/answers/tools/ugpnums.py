#!/usr/bin/env python3
"""ugpnums.py SRC [N…] — сверка чисел в ответах по Уголовному праву с источниками порции.

Берётся каждое число ответа, за которым стоит единица измерения (лет, месяцев, часов, рублей,
процентов, человек и т. п.), записанное цифрами или словами («двадцати пяти лет», «1 500 000 рублей»).
Для предложения с таким числом в источниках порции (коды из ugp/notes) ищутся места, где
встречается больше всего его значимых слов; число должно стоять в одном из этих мест
(цифрами или словами). Печатаются числа, которых там нет, — их сверяют глазами.
Ссылки на статьи, части, пункты, номера и даты актов в счёт не идут.
    python3 tools/ugpnums.py /tmp/usrc 45 47 48
Ключ --all печатает и найденные числа; --skip пропускает раздел о значении для сотрудника полиции.
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "ugp")
args = [x for x in sys.argv[1:] if not x.startswith("--")]
opts = dict((x[2:].split("=") + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
SRC = args[0] if args else "."
ONLY = [int(x) for x in args[1:] if x.isdigit()]

UNITS = {"один": 1, "одного": 1, "одной": 1, "одна": 1, "одну": 1, "одним": 1, "одному": 1, "одно": 1,
         "два": 2, "две": 2, "двух": 2, "двум": 2, "двумя": 2, "три": 3, "трех": 3, "трем": 3, "тремя": 3,
         "четыре": 4, "четырех": 4, "четырем": 4, "четырьмя": 4, "пять": 5, "пяти": 5, "пятью": 5,
         "шесть": 6, "шести": 6, "шестью": 6, "семь": 7, "семи": 7, "семью": 7, "восемь": 8, "восьми": 8,
         "девять": 9, "девяти": 9, "десять": 10, "десяти": 10, "десятью": 10}
for _s, _v in (("одиннадцат", 11), ("двенадцат", 12), ("тринадцат", 13), ("четырнадцат", 14), ("пятнадцат", 15),
               ("шестнадцат", 16), ("семнадцат", 17), ("восемнадцат", 18), ("девятнадцат", 19)):
    for _e in ("ь", "и", "ью"):
        UNITS[_s + _e] = _v
TENS = {}
for _s, _v in (("двадцат", 20), ("тридцат", 30)):
    for _e in ("ь", "и", "ью"):
        TENS[_s + _e] = _v
TENS.update({"сорок": 40, "сорока": 40, "пятьдесят": 50, "пятидесяти": 50, "шестьдесят": 60, "шестидесяти": 60,
             "семьдесят": 70, "семидесяти": 70, "восемьдесят": 80, "восьмидесяти": 80, "девяносто": 90, "девяноста": 90})
HUND = {"сто": 100, "ста": 100, "двести": 200, "двухсот": 200, "триста": 300, "трехсот": 300, "четыреста": 400,
        "четырехсот": 400, "пятьсот": 500, "пятисот": 500, "шестьсот": 600, "шестисот": 600, "семьсот": 700,
        "семисот": 700, "восемьсот": 800, "восьмисот": 800, "девятьсот": 900, "девятисот": 900}
MULT = {"тысяча": 1000, "тысячи": 1000, "тысяч": 1000, "тысячу": 1000, "тыс": 1000,
        "миллион": 10 ** 6, "миллиона": 10 ** 6, "миллионов": 10 ** 6, "млн": 10 ** 6}
UNIT_RE = re.compile(r"^(лет|года|год|годам|годов|месяц|недел|дня|дней|день|суток|сутки|час|рубл|руб|процент|"
                     r"человек|лиц|джоул|летн|кратн|раз$|раза$|осужденн)")
COMPOUND = sorted(list(UNITS.items()) + list(TENS.items()), key=lambda x: -len(x[0]))


def e(s):
    return s.replace("ё", "е").replace("Ё", "Е")


def tokens(text):
    """[(слово в нижнем регистре, начало в тексте)]"""
    return [(m.group(0).lower(), m.start()) for m in re.finditer(r"\d+(?:[,.]\d+)?|[А-Яа-яA-Za-z]+|%", e(text))]


def compound_age(w):
    """«четырнадцатилетнего» → 14, «шестидесятипятилетнего» → 65"""
    i = w.find("летн")
    if i <= 0:
        return None
    pre, val = w[:i], 0
    while pre:
        for k, v in COMPOUND:
            if pre.startswith(k):
                val += v
                pre = pre[len(k):]
                break
        else:
            return None
    return val or None


def numbers(toks):
    """[(значение, номер первого токена, номер токена после числа)]"""
    out, i, n = [], 0, len(toks)
    while i < n:
        w = toks[i][0]
        if w[0].isdigit():
            j, s = i + 1, w
            # «1 500 000»
            while "," not in s and "." not in s and j < n and re.fullmatch(r"\d{3}", toks[j][0]) \
                    and toks[j][1] - (toks[j - 1][1] + len(toks[j - 1][0])) == 1 and len(toks[i][0]) <= 3:
                s += toks[j][0]
                j += 1
            try:
                v = float(s.replace(",", "."))
            except ValueError:
                i = j
                continue
            if j < n and toks[j][0] in MULT:
                v *= MULT[toks[j][0]]
                j += 1
            out.append((v, i, j))
            i = j
            continue
        ca = compound_age(w) if "летн" in w else None
        if ca:
            out.append((float(ca), i, i))  # единица внутри слова
            i += 1
            continue
        if w in UNITS or w in TENS or w in HUND:
            total, cur, j = 0, 0, i
            while j < n:
                x = toks[j][0]
                if x in HUND:
                    cur += HUND[x]
                elif x in TENS:
                    cur += TENS[x]
                elif x in UNITS:
                    cur += UNITS[x]
                elif x in MULT and cur:
                    total += cur * MULT[x]
                    cur = 0
                else:
                    break
                j += 1
            out.append((float(total + cur), i, j))
            i = j
            continue
        i += 1
    return out


def with_units(text):
    """числа ответа, за которыми идёт единица измерения: [(значение, отрывок)]"""
    t = e(text)
    t = re.sub(r"//\([^/]*\)//", " ", t)
    t = re.sub(r"\d\d\.\d\d\.\d{4}", " ", t)
    t = re.sub(r"№ ?[\d\-]+(-ФЗ|н|-П|-1)?", " ", t)
    t = re.sub(r"\b(стать[а-я]*|ст|чч?|пп?|гл|главы?|раздел[а-я]*|примечани[а-я]*|частью?|пункт[а-я]*)\.? ?"
               r"(«[а-я]»[,–и ]*)*\d+(\.\d+)?(\(\d\))?((, | и |–| – )\d+(\.\d+)?)*", " ", t)
    toks = tokens(t)
    res = []
    for v, i, j in numbers(toks):
        inner = "летн" in toks[i][0] or "-летн" in t[toks[i][1]:toks[i][1] + len(toks[i][0]) + 6]
        nxt = [toks[k][0] for k in range(j, min(j + 2, len(toks)))]
        if inner or any(UNIT_RE.match(x) for x in nxt[:1]) or (nxt[:1] == ["%"]):
            a = toks[i][1]
            res.append((v, t[max(0, a - 30):a + 40].replace("\n", " ")))
        elif nxt[:1] and (nxt[0] in ("до", "или", "и", "либо") or nxt[0][0].isdigit() or nxt[0] in UNITS
                          or nxt[0] in TENS or nxt[0] in HUND) and j + 1 < len(toks):
            # «от двух до шести лет», «6 или 10 лет», «2, 6, 10, 15 лет»
            k, ok = j, False
            while k < len(toks) and k < j + 8:
                if UNIT_RE.match(toks[k][0]):
                    ok = True
                    break
                if not (toks[k][0] in ("до", "или", "и", "либо", "от") or toks[k][0][0].isdigit()
                        or toks[k][0] in UNITS or toks[k][0] in TENS or toks[k][0] in HUND or toks[k][0] in MULT):
                    break
                k += 1
            if ok:
                a = toks[i][1]
                res.append((v, t[max(0, a - 30):a + 40].replace("\n", " ")))
    return res


_c = {}


def corpus(code):
    if code in _c:
        return _c[code]
    fs = sorted(glob.glob(os.path.join(SRC, code + "*")))
    if not fs:
        _c[code] = None
        return None
    raw = open(fs[0], encoding="utf-8", errors="replace").read().replace("\u00ad", "").replace("\u00a0", " ")
    raw = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", raw)
    raw = re.sub(r"\s+", " ", raw)
    toks = tokens(raw)
    idx = {}
    for i, (w, _) in enumerate(toks):
        if len(w) >= 4 and not w[0].isdigit():
            idx.setdefault(w[:5], []).append(i)
    nums = [(i, v) for v, i, j in numbers(toks)]
    _c[code] = (toks, idx, nums, raw)
    return _c[code]


STOP = set("котор этого этому такой также может могут должн если либо тольк более менее между через после перед "
           "лицо лица лицу лицом стать часть части пункт далее иными иные иных своих свою свое того тому этим "
           "быть было были будет являе имеет имеют".split())


def stems(s):
    s = re.sub(r"//\([^/]*\)//", " ", s)
    return {w[:5] for w in re.findall(r"[а-я]{4,}", e(s.lower()))} - STOP


def windows(st, code, top=3):
    """лучшие окна источника: [(доля, начало, конец)]"""
    c = corpus(code)
    if not c:
        return []
    toks, idx, nums, raw = c
    W = max(70, 8 * len(st))
    ev = sorted((p, w) for w in st for p in idx.get(w, ()))
    res, cnt, have, j = [], {}, 0, 0
    for i, (p, w) in enumerate(ev):
        cnt[w] = cnt.get(w, 0) + 1
        if cnt[w] == 1:
            have += 1
        while ev[j][0] < p - W:
            w0 = ev[j][1]
            cnt[w0] -= 1
            if cnt[w0] == 0:
                have -= 1
            j += 1
        res.append((have, ev[j][0], p))
    res.sort(reverse=True)
    out = []
    for h, a, b in res:
        if all(abs(a - x[1]) > W for x in out):
            out.append((h / max(1, len(st)), a, b))
            if len(out) >= top:
                break
    return out


def codes_for(n):
    out = []
    for f in sorted(glob.glob(os.path.join(A, "notes", "q*.md"))):
        m = re.search(r"q(\d+)-(\d+)\.md", f)
        if int(m.group(1)) <= n <= int(m.group(2)):
            for l in open(f, encoding="utf-8"):
                mm = re.match(r"\|([^|]*)\|", l)
                for c in (re.findall(r"\b[0-9a-f]{6}\b", mm.group(1)) if mm else ()):
                    if c not in out:
                        out.append(c)
    return out


def found(v, st, cs):
    for code in cs:
        c = corpus(code)
        if not c:
            continue
        toks, idx, nums, raw = c
        for sc, a, b in windows(st, code):
            if sc < 0.34:
                continue
            lo, hi = a - 90, b + 90
            for p, x in nums:
                if lo <= p <= hi and abs(x - v) < 1e-6:
                    return code, sc
    return None, 0


def run(n):
    L = open(os.path.join(A, f"q{n:03d}.txt"), encoding="utf-8").read().split("\n")
    cs = codes_for(n)
    sect, res = "", []
    for i, l in enumerate(L):
        if l.startswith("## "):
            sect = l
            continue
        if l.startswith("# "):
            continue
        if "skip" in opts and ("сотрудника полиции" in sect or l.startswith("!!")):
            continue
        for sent in re.split(r"(?<=[.;])\s+(?=[А-ЯЁ«\-—*])", l):
            ns = with_units(sent)
            if not ns:
                continue
            st = stems(sent)
            for v, ctx in ns:
                code, sc = found(v, st, cs)
                res.append((i + 1, v, ctx, code, sc))
    return res


if __name__ == "__main__":
    tot = miss = 0
    for n in (ONLY or range(1, 118)):
        for ln, v, ctx, code, sc in run(n):
            tot += 1
            vv = int(v) if v == int(v) else v
            if not code:
                miss += 1
                print(f"{n}:{ln} нет {vv} | …{ctx}…")
            elif "all" in opts:
                print(f"{n}:{ln} ok  {vv} [{code} {sc:.2f}] | …{ctx}…")
    print(f"-- чисел с единицами: {tot}; не найдено рядом в источниках: {miss}")
