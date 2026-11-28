#!/usr/bin/env python3
"""tspwords.py SRC [--k=3] [--win=40] [N…] — слова ответов по ТСП, которые нигде в источниках не стоят в том же окружении.

Для каждого значимого слова предложения (по первым пяти буквам) ищется место в любом файле SRC, где это слово
стоит рядом (в пределах --win слов) не менее чем с --k другими значимыми словами того же предложения.
Если такого места нет, слово печатается как «без опоры». Проверка терпима к пересказу: предложение может быть
собрано из разных мест источника. Отсеивает глаголы пересказа хуже, чем существительные и числа, поэтому
результат читают глазами: значение имеют названия, признаки, количества и категоричные утверждения.
    python3 tools/tspwords.py /tmp/tsrc 13 14
"""
import glob
import os
import re
import sys
from bisect import bisect_left

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(os.path.dirname(HERE), "tsp")
args = [x for x in sys.argv[1:] if not x.startswith("--")]
opts = dict((x[2:].split("=") + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
SRC = args[0]
ONLY = [int(x) for x in args[1:] if x.isdigit()]
K = int(opts.get("k", 3))
WIN = int(opts.get("win", 40))
STOP = set("котор этого этому такой также может могут должн если либо только более менее между через после перед "
           "стать часть части пункт далее иными иные иных своих свою свое того тому этим "
           "быть было были будет являе имеет имеют самог самой всех всем него нему ними когда тогда чтобы "
           "напри приме учебн пособ ответ источ одном одног друго лекци курсе назыв приво дает дают указа".split())


def e(s):
    return s.replace("ё", "е").replace("Ё", "Е")


def words(s):
    return re.findall(r"[а-яa-z]{4,}", e(s.lower()))


IDX = []
for f in sorted(glob.glob(os.path.join(SRC, "*.txt"))):
    raw = open(f, encoding="utf-8", errors="replace").read().replace("\u00ad", "")
    raw = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", raw)
    idx = {}
    for i, w in enumerate(words(raw)):
        idx.setdefault(w[:5], []).append(i)
    IDX.append(idx)


def supported(w, others, need):
    for idx in IDX:
        ps = idx.get(w)
        if not ps:
            continue
        cand = [(o, idx[o]) for o in others if o in idx]
        if len(cand) < need:
            continue
        for p in ps:
            k = 0
            for o, lst in cand:
                j = bisect_left(lst, p - WIN)
                if j < len(lst) and lst[j] <= p + WIN:
                    k += 1
                    if k >= need:
                        return True
    return False


def sentences(line):
    s = re.sub(r"\*\*|^[#>!\-\s]+|^\d+\.\s+", "", line)
    parts = re.split(r"(?<=[.;:?!])\s+(?=[А-ЯЁ«\d—])", s)
    out, buf = [], ""
    for p in parts:
        buf = (buf + " " + p).strip()
        if len({w[:5] for w in words(buf)} - STOP) >= 5:
            out.append(buf)
            buf = ""
    if buf:
        if out:
            out[-1] += " " + buf
        else:
            out.append(buf)
    return out


tot = bad = 0
for n in (ONLY or range(1, 88)):
    L = open(os.path.join(A, f"q{n:03d}.txt"), encoding="utf-8").read().split("\n")
    for i, l in enumerate(L):
        if l.startswith("# ") or l.startswith("## ") or not l.strip():
            continue
        for s in sentences(l):
            full = {}
            for w in words(s):
                if w[:5] not in STOP:
                    full.setdefault(w[:5], w)
            st = list(full)
            if len(st) < 4:
                continue
            tot += 1
            need = min(K, max(2, len(st) // 3))
            orph = [full[w] for w in st if not supported(w, [o for o in st if o != w], need)]
            if orph:
                bad += 1
                print(f"{n}:{i + 1}{' !!' if l.startswith('!!') else ''} [{', '.join(orph)}] {s[:int(opts.get('w', 260))]}")
print(f"-- предложений: {tot}; со словами без опоры: {bad}")
