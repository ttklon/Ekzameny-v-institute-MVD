#!/usr/bin/env python3
"""tsplines.py SRC [--t=0.7] [--all] [--show=N] [--miss] [--nums] [N…] — опора каждого предложения ответа по ТСП на источники.

SRC — папка с извлечёнными текстами (kextract.py). Ответ делится на предложения; для каждого ищется окно текста
источника, где встречается наибольшая доля значимых слов предложения (по первым пяти буквам). Сначала берутся
источники, коды которых названы в tsp/notes для этого ответа, затем, если доля ниже порога, — все файлы SRC.
Печатаются предложения с долей ниже порога: источник, страница (по kpage.py), место источника.
Ключ --miss печатает слова предложения, которых нет в найденном месте.
Ключ --nums печатает числа предложения, которых нет в найденном месте источника (цифрами).
Это не проверка смысла: так находят предложения, которые надо перечитать рядом с источником.
    python3 tools/tsplines.py /tmp/tsrc --t=0.7 --show=260 1 2 3
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "tsp")
args = [x for x in sys.argv[1:] if not x.startswith("--")]
opts = dict((x[2:].split("=") + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
SRC = args[0]
ONLY = [int(x) for x in args[1:] if x.isdigit()]
T = float(opts.get("t", 0.7))
STOP = set("котор этого этому такой также может могут должн если либо только более менее между через после перед "
           "стать часть части пункт далее иными иные иных своих свою свое того тому этим "
           "быть было были будет являе имеет имеют самог самой всех всем него нему ними когда тогда чтобы "
           "напри приме учебн пособ ответ источ".split())


def e(s):
    return s.replace("ё", "е").replace("Ё", "Е")


def words(s):
    return [w[:5] for w in re.findall(r"[а-яa-z]{4,}", e(s.lower()))]


_cache = {}
ALL = sorted(os.path.basename(f)[:6] for f in glob.glob(os.path.join(SRC, "*.txt")))


def corpus(code):
    if code in _cache:
        return _cache[code]
    fs = sorted(glob.glob(os.path.join(SRC, code + "*")))
    if not fs:
        _cache[code] = None
        return None
    raw = open(fs[0], encoding="utf-8", errors="replace").read().replace("\u00ad", "")
    raw = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", raw)
    toks, pages, spans = [], [], []
    for m in re.finditer(r"@@ (\d+) \| ([^\n]*)|[А-Яа-яЁёA-Za-z]{4,}", raw):
        if m.group(1):
            pages.append((len(toks), m.group(1)))
        else:
            toks.append(e(m.group(0).lower())[:5])
            spans.append(m.start())
    idx = {}
    for i, w in enumerate(toks):
        idx.setdefault(w, []).append(i)
    _cache[code] = (toks, idx, pages, raw, spans)
    return _cache[code]


def best(st, code):
    c = corpus(code)
    if not c:
        return 0.0, None
    toks, idx, pages, raw, spans = c
    W = max(60, 7 * len(st))
    ev = sorted((p, w) for w in st for p in idx.get(w, ()))
    if not ev:
        return 0.0, None
    cnt, have, j, bestv, bestp = {}, 0, 0, 0, 0
    for p, w in ev:
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
    lab = ""
    for p, l in corpus(code)[2]:
        if p <= pos:
            lab = l
        else:
            break
    return lab


def excerpt(code, pos, n, st=None):
    toks, idx, pages, raw, spans = corpus(code)
    s = spans[pos]
    if st is not None:
        W = max(60, 7 * len(st))
        end = spans[min(len(spans) - 1, pos + W)]
        return raw[max(0, s - 200):end + 200]
    return re.sub(r"\s+", " ", raw[max(0, s - 40):s + n])


def codes_for(n):
    out = []
    for f in sorted(glob.glob(os.path.join(A, "notes", "q*.md"))):
        m = re.search(r"q(\d+)-(\d+)\.md", f)
        if int(m.group(1)) <= n <= int(m.group(2)):
            for c in re.findall(r"(?<![0-9a-f])([0-9a-f]{6})(?![0-9a-f])", open(f, encoding="utf-8").read()):
                if c not in out and c in ALL:
                    out.append(c)
    return out


def sentences(line):
    s = re.sub(r"\*\*|^[#>!\-\s]+|^\d+\.\s+", "", line)
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


def nums(s):
    s = re.sub(r"(?<=\d)[\u00a0 ](?=\d{3}\b)", "", s)
    return set(re.findall(r"\d+(?:[.,]\d+)?", s))


def run(n):
    L = open(os.path.join(A, f"q{n:03d}.txt"), encoding="utf-8").read().split("\n")
    cs = codes_for(n)
    res = []
    for i, l in enumerate(L):
        if l.startswith("# ") or l.startswith("## ") or not l.strip():
            continue
        for s in sentences(l):
            st = set(words(s)) - STOP
            if len(st) < 3:
                res.append((i + 1, 1.0, None, None, s, st, True))
                continue
            bv, bc, bp = 0, None, None
            for c in cs:
                v, p = best(st, c)
                if v > bv:
                    bv, bc, bp = v, c, p
            if bv < T and "local" not in opts:
                for c in ALL:
                    if c in cs:
                        continue
                    v, p = best(st, c)
                    if v > bv + 0.1:
                        bv, bc, bp = v, c, p
            res.append((i + 1, bv, bc, bp, s, st, False))
    return res


if __name__ == "__main__":
    tot = low = 0
    for n in (ONLY or range(1, 88)):
        for ln, v, c, p, s, st, short in run(n):
            tot += 1
            miss = []
            if "nums" in opts and c and not short:
                ex = excerpt(c, p, 0, st)
                have = nums(ex)
                miss = sorted(x for x in nums(s) if x not in have and x.replace(",", ".") not in {h.replace(",", ".") for h in have})
            flag = (v < T and not short) or bool(miss) or "all" in opts
            if flag:
                low += 1
                lab = f"{c} с.{page(c, p)}" if c else "—"
                print(f"{n}:{ln} {v:.2f} [{lab}]{' НЕТ ЧИСЕЛ ' + ','.join(miss) if miss else ''} {s[:int(opts.get('w', 400))]}")
                if "miss" in opts and c:
                    toks, idx, pages, raw, spans = corpus(c)
                    W = max(60, 7 * len(st))
                    win = set(toks[p:p + W + 1])
                    ww = []
                    for w in re.findall(r"[а-яa-z]{4,}", e(s.lower())):
                        if w[:5] in st and w[:5] not in win and w not in ww:
                            ww.append(w)
                    print("      нет в этом месте: " + ", ".join(ww))
                if "show" in opts and c:
                    print("      ≈ " + excerpt(c, p, int(opts["show"])))
    print(f"-- предложений: {tot}; отмечено: {low}")
