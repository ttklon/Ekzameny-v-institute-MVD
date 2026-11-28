#!/usr/bin/env python3
"""tspnums.py SRC [N…] — числа в ответах по ТСП, для которых в источниках не найдено место с тем же числом.

Для каждого числа в тексте ответа берутся значимые слова рядом с ним (по первым пяти буквам). Число
считается подтверждённым, если в каком-либо файле SRC оно стоит отдельным числом и в 250 знаках вокруг него
есть не меньше половины значимых слов, стоящих в ответе рядом с числом (60 знаков в обе стороны). Печатаются остальные числа с предложением.
Номера пунктов списка, номера вопросов и даты актов не отсеиваются: их смотрят глазами.
    python3 tools/tspnums.py /tmp/tsrc 43 64
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "tsp")
SRC = sys.argv[1]
ONLY = [int(x) for x in sys.argv[2:] if x.isdigit()]


def e(s):
    return s.replace("ё", "е").replace("Ё", "Е").replace("\u00ad", "")


TXT = {}
for f in sorted(glob.glob(os.path.join(SRC, "*.txt"))):
    t = e(open(f, encoding="utf-8", errors="replace").read().lower())
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", t)
    TXT[os.path.basename(f)[:6]] = t
NUMPOS = {}
for c, t in TXT.items():
    for m in re.finditer(r"(?<![\d,.])\d+(?:[.,]\d+)?(?![\d])", t):
        NUMPOS.setdefault(m.group(0).replace(",", ".").rstrip("."), []).append((c, m.start()))


def stems(s):
    return {w[:5] for w in re.findall(r"[а-яa-z]{4,}", e(s.lower()))}


def found(num, st):
    need = max(2, (len(st) + 1) // 2) if len(st) >= 3 else max(1, len(st))
    best = (0, None)
    for c, pos in NUMPOS.get(num.replace(",", "."), ()):
        t = TXT[c]
        ctx = stems(t[max(0, pos - 250):pos + 250])
        k = len(st & ctx)
        if k > best[0]:
            best = (k, c)
            if k >= need:
                return True, best
    return best[0] >= need, best


tot = bad = 0
for n in (ONLY or range(1, 88)):
    L = open(os.path.join(A, f"q{n:03d}.txt"), encoding="utf-8").read().split("\n")
    for i, l in enumerate(L):
        if l.startswith("# "):
            continue
        body = re.sub(r"^\d+\.\s+", "", l)
        for s in re.split(r"(?<=[.;?!])\s+(?=[А-ЯЁ«\d—])", body):
            s2 = re.sub(r"(?<=\d)[\u00a0 ](?=\d{3}\b)", "", s)
            for m in re.finditer(r"(?<![\d,.])\d+(?:[.,]\d+)?(?!\d)", s2):
                num = m.group(0).rstrip(".,")
                near = s2[max(0, m.start() - 60):m.end() + 60]
                st = stems(near)
                tot += 1
                ok, b = found(num, st)
                if not ok:
                    bad += 1
                    print(f"{n}:{i + 1} [{num}] (лучшее: {b[0]} слов, {b[1]}) {near.strip()}")
print(f"-- чисел: {tot}; без найденного места: {bad}")
