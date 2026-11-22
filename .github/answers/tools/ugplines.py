#!/usr/bin/env python3
"""ugplines.py SRC [--t=0.7] [--all] [N…] — опора каждой строки ответа по Уголовному праву на источники порции.

Источники порции — файлы, коды которых стоят в первой графе таблиц ugp/notes/qNNN-NNN.md
(кодекс, постановления Пленума, учебники, пособия, статьи). Строка ответа делится на предложения;
для каждого ищется окно текста источника, где встречается наибольшая доля значимых слов предложения
(по первым пяти буквам). Печатаются предложения с долей ниже порога: источник, страница, чего нет.
Это не проверка смысла. Так находят предложения, которые надо перечитать рядом с источником:
примеры, выводы и собственные формулировки дают низкую долю и без ошибки.
    python3 tools/ugplines.py /tmp/usrc --t=0.7 1 2 3
Ключи: --all — все предложения; --show=N — рядом с предложением N знаков найденного места источника;
--skip — не печатать разделы «Значение для сотрудника полиции» и «Главное для запоминания».
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "ugp")
args = [x for x in sys.argv[1:] if not x.startswith("--")]
opts = dict((x[2:].split("=") + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
SRC = args[0]
ONLY = [int(x) for x in args[1:] if x.isdigit()]
T = float(opts.get("t", 0.7))
STOP = set("котор этого этому такой также может могут должн если либо только более менее между через после перед "
           "лицо лица лицу лицом стать часть части пункт далее иными иные иных своих свою свое того тому этим "
           "быть было были будет являе имеет имеют самог самой всех всем него нему ними когда тогда чтобы "
           "напри приме учебн росси федер кодек".split())


def e(s):
    return s.replace("ё", "е").replace("Ё", "Е")


def words(s):
    return [w[:5] for w in re.findall(r"[а-яa-z]{4,}", e(s.lower()))]


_cache = {}


def corpus(code):
    """(список основ, позиции основ, [(номер слова, метка страницы)], текст по словам)"""
    if code in _cache:
        return _cache[code]
    fs = sorted(glob.glob(os.path.join(SRC, code + "*")))
    if not fs:
        _cache[code] = None
        return None
    raw = open(fs[0], encoding="utf-8", errors="replace").read()
    raw = raw.replace("\u00ad", "")
    raw = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", raw)
    toks, pages, spans = [], [], []
    for m in re.finditer(r"@@ (\d+) \| ([^\n]*)|[А-Яа-яЁёA-Za-z]{4,}", raw):
        if m.group(1):
            pages.append((len(toks), m.group(2).strip() or m.group(1)))
        else:
            toks.append(e(m.group(0).lower())[:5])
            spans.append(m.start())
    idx = {}
    for i, w in enumerate(toks):
        idx.setdefault(w, []).append(i)
    _cache[code] = (toks, idx, pages, raw, spans, os.path.basename(fs[0])[7:47])
    return _cache[code]


def best(st, code):
    c = corpus(code)
    if not c:
        return 0.0, None
    toks, idx, pages, raw, spans, name = c
    W = max(60, 7 * len(st))
    ev = sorted((p, w) for w in st for p in idx.get(w, ()))
    if not ev:
        return 0.0, None
    cnt, have, j, bestv, bestp = {}, 0, 0, 0, 0
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
        if have > bestv:
            bestv, bestp = have, ev[j][0]
    return bestv / len(st), bestp


def page(code, pos):
    toks, idx, pages, raw, spans, name = corpus(code)
    lab = ""
    for p, l in pages:
        if p <= pos:
            lab = l
        else:
            break
    return lab


def excerpt(code, pos, n):
    toks, idx, pages, raw, spans, name = corpus(code)
    s = spans[pos]
    return re.sub(r"\s+", " ", raw[max(0, s - 40):s + n])


def codes_for(n):
    out = []
    for f in sorted(glob.glob(os.path.join(A, "notes", "q*.md"))):
        m = re.search(r"q(\d+)-(\d+)\.md", f)
        if int(m.group(1)) <= n <= int(m.group(2)):
            for l in open(f, encoding="utf-8"):
                mm = re.match(r"\| ?`?([0-9a-f]{6})`? ?\|", l)
                if mm and mm.group(1) not in out:
                    out.append(mm.group(1))
    return out


def sentences(line):
    s = re.sub(r"//\([^/]*\)//", " ", line)
    s = re.sub(r"\*\*|^[#>!\-\s]+", "", s)
    parts = re.split(r"(?<=[.;:?!])\s+(?=[А-ЯЁ«\d—])", s)
    out, buf = [], ""
    for p in parts:
        buf = (buf + " " + p).strip()
        if len(set(words(buf)) - STOP) >= 5:
            out.append(buf)
            buf = ""
    if buf:
        if out:
            out[-1] += " " + buf
        else:
            out.append(buf)
    return out


def run(n):
    L = open(os.path.join(A, f"q{n:03d}.txt"), encoding="utf-8").read().split("\n")
    cs = codes_for(n)
    sect = ""
    res = []
    for i, l in enumerate(L):
        if l.startswith("## "):
            sect = l[3:]
            continue
        if l.startswith("# ") or not l.strip():
            continue
        own = "сотрудника полиции" in sect or l.startswith("!!")
        for s in sentences(l):
            st = set(words(s)) - STOP
            if len(st) < 4:
                continue
            bv, bc, bp = 0, None, None
            for c in cs:
                v, p = best(st, c)
                if v > bv:
                    bv, bc, bp = v, c, p
            res.append((i + 1, bv, bc, bp, s, own, st))
    return res, cs


if __name__ == "__main__":
    tot = low = 0
    for n in (ONLY or range(1, 118)):
        res, cs = run(n)
        for ln, v, c, p, s, own, st in res:
            tot += 1
            if own and "skip" in opts:
                continue
            if v < T or "all" in opts:
                low += 1
                lab = f"{c} с.{page(c, p)}" if c else "—"
                print(f"{n}:{ln} {v:.2f} [{lab}] {s[:int(opts.get('w', 300))]}")
                if "show" in opts and c:
                    print("      ≈ " + excerpt(c, p, int(opts["show"])))
    print(f"-- предложений: {tot}; ниже порога {T}: {low}")
