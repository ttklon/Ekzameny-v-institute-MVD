#!/usr/bin/env python3
"""ugpcheck.py SRC [N…] — формальная сверка ответов по Уголовному праву (ugp/qNNN.txt) с текстом УК РФ и Пленумов.

SRC — папка, созданная kextract.py (УК РФ — файл с кодом fc7900). Печатаются только расхождения:
  REF   — в ответе названа статья, часть или пункт УК РФ, которых в кодексе нет (или статья утратила силу);
  TERM  — срок лишения свободы рядом с «ч. N» не найден в санкции этой части;
  CAT   — категория преступления рядом с «ч. N» не совпадает с расчётом по максимуму санкции
          (расчёт сделан как для умышленного деяния; для неосторожных — смотреть глазами);
  PLEN  — у постановления Пленума не найден файл, не совпала редакция или нет названного пункта.
Пометка не означает ошибку: ссылки на другие кодексы без названия акта и сроки, не относящиеся
к лишению свободы, проверяются глазами.
    python3 tools/ugpcheck.py /tmp/usrc            # все ответы
    python3 tools/ugpcheck.py /tmp/usrc 1 2 3
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "..", "ugp")
SRC = sys.argv[1]
ONLY = {int(x) for x in sys.argv[2:] if x.isdigit()}

NUM = {"одного": 1, "двух": 2, "трех": 3, "четырех": 4, "пяти": 5, "шести": 6, "семи": 7, "восьми": 8,
       "девяти": 9, "десяти": 10, "одиннадцати": 11, "двенадцати": 12, "тринадцати": 13, "четырнадцати": 14,
       "пятнадцати": 15, "шестнадцати": 16, "семнадцати": 17, "восемнадцати": 18, "девятнадцати": 19,
       "двадцати": 20, "полутора": 1.5}


def e(s):
    return s.replace("ё", "е")


# ---------- УК РФ ----------
def load_uk():
    path = glob.glob(f"{SRC}/fc7900*")[0]
    text = re.sub(r"@@ \d+ \| \S+\n", "", open(path, encoding="utf-8").read())
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.split("\n")]
    arts, cur, part = {}, None, None
    for l in lines:
        if not l:
            continue
        m = re.match(r"^Статья (\d+)(?: (\d+))? ?\.(?!\d)\s*(.*)", l)
        if m:
            cur = m.group(1) + ("." + m.group(2) if m.group(2) else "")
            arts[cur] = {"title": m.group(3), "parts": {}, "void": False, "raw": []}
            part = None
            continue
        if re.match(r"^(Глава \d|Раздел [IVXLC]+|ГЛАВА|РАЗДЕЛ)", l):
            cur = None
            continue
        if cur is None:
            continue
        a = arts[cur]
        if "утратила силу" in l and not a["parts"] and not a["title"]:
            a["void"] = True
        if re.match(r"^\((В редакции|Дополнение|Часть|Статья|Пункт|Абзац|Наименование|Примечани)", l):
            if re.match(r"^\((Часть|Пункт) утратил", l) and part:
                a["parts"][part]["void"] = True
            continue
        a["raw"].append(l)
        m = re.match(r"^(\d+)(?: (\d+))? ?\. ", l)
        if m and not l.startswith("Примечани"):
            part = m.group(1) + ("." + m.group(2) if m.group(2) else "")
            a["parts"].setdefault(part, {"text": "", "san": "", "points": set(), "void": False})
        if re.match(r"^Примечани", l):
            part = None
            continue
        if part is None:
            # статья без деления на части: единственная «часть 1»
            part = "1"
            a["parts"].setdefault(part, {"text": "", "san": "", "points": set(), "void": False})
            a["single"] = True
        p = a["parts"][part]
        if re.match(r"^наказыва", l):
            p["san"] += " " + e(l)
        else:
            p["text"] += " " + l
            m = re.match(r"^([а-я])(?: (\d+))? ?\) ", l)
            if m:
                p["points"].add(m.group(1) + ("." + m.group(2) if m.group(2) else ""))
    return arts


UK = load_uk()


def maxterm(san):
    """(максимум лишения свободы в годах | None, пожизненное/смертная казнь)"""
    life = "пожизненн" in san or "смертной казн" in san
    best = None
    for m in re.finditer(r"лишением свободы на (?:срок )?(?:от \w+(?: \w+)? (?:лет |года )?)?до (\w+) (?:лет|года)", san):
        v = NUM.get(m.group(1))
        if v:
            best = max(best or 0, v)
    # «…либо лишением свободы на тот же срок»
    for m in re.finditer(r"на срок (?:от \w+ )?до (\w+) (?:лет|года)[^.;]{0,120}?лишением свободы на тот же срок", san):
        v = NUM.get(m.group(1))
        if v:
            best = max(best or 0, v)
    return best, life


def category(san):
    y, life = maxterm(san)
    if life or (y and y > 10):
        return "особо тяжк"
    if y is None:
        return "небольшой"
    return "небольшой" if y <= 3 else "средней" if y <= 5 else "тяжк"


# ---------- Пленумы ----------
PL = {}
for f in sorted(os.listdir(SRC)):
    m = re.search(r"Пленума ВС РФ от (\d\d\.\d\d\.\d{4}) № (\d+)", f)
    if not m:
        continue
    t = re.sub(r"\s+", " ", open(os.path.join(SRC, f), encoding="utf-8", errors="ignore").read())
    key = (m.group(1), m.group(2))
    if key not in PL or t.startswith("Источник: https://www.consultant.ru"):
        PL[key] = t


def pl_points(t):
    pts, pos = set(), 0
    for n in range(1, 200):
        i = t.find(f" {n}. ", pos)
        if i < 0:
            continue
        pts.add(str(n))
        pos = i + 1
    for m in re.finditer(r" (\d+)\.(\d+)\. ", t):
        pts.add(m.group(1) + "." + m.group(2))
    return pts


def pl_red(t):
    m = re.search(r"\(ред\. от (\d\d\.\d\d\.\d{4})\)", t[:1500])
    return m.group(1) if m else None


OTHER = r"(УПК|УИК|КоАП|Кодекса РФ об административных|Конституци|ГК РФ|закона|Закона|ФЗ|УК РСФСР|Конвенци|Устав|Положени|Правил|НК РФ|ТК РФ|СК РФ)"


def check(n):
    path = os.path.join(A, f"q{n:03d}.txt")
    L = open(path, encoding="utf-8").read().split("\n")
    out = []
    cit = re.search(r"//\(([^/]*)\)//", L[1]) if len(L) > 1 else None
    main = re.findall(r"ст\. (\d+(?:\.\d+)?)", cit.group(1) if cit else (L[1] if len(L) > 1 else ""))
    main_art = main[0] if main else None
    plen_names = {}
    for i, raw in enumerate(L, 1):
        l = e(raw)
        # --- Пленумы: полное упоминание ---
        l = l.replace("Верховного Суда Российской Федерации", "Верховного Суда РФ")
        for m in re.finditer(r"(?:Пленума Верховного Суда РФ|(?<=\) и)) от (\d\d\.\d\d\.\d{4}) № (\d+)()", l):
            key = (m.group(1), m.group(2))
            plen_names[m.group(2)] = key
            if key not in PL:
                out.append(f"PLEN {n}:{i} нет файла Пленума от {key[0]} № {key[1]}")
                continue
            r = re.search(r"в редакции от (\d\d\.\d\d\.\d{4})", re.split(r"Пленума Верховного Суда РФ от|\) и от", l[m.end():m.end() + 260])[0])
            red = pl_red(PL[key])
            if r and red and r.group(1) != red:
                out.append(f"PLEN {n}:{i} № {key[1]}: в ответе редакция {r.group(1)}, в файле {red}")
            if r and not red:
                out.append(f"PLEN {n}:{i} № {key[1]}: в ответе редакция {r.group(1)}, в файле редакции нет")
            if not r and red:
                out.append(f"PLEN {n}:{i} № {key[1]}: в ответе редакция не названа, в файле {red}")
        # --- Пленумы: пункты ---
        for m in re.finditer(r"пп?\. ([\d., –и]+?) (?:постановления )?Пленума (?:Верховного Суда РФ от (\d\d\.\d\d\.\d{4}) )?№ (\d+)", l):
            num = m.group(3)
            key = (m.group(2), num) if m.group(2) else plen_names.get(num)
            if not key or key not in PL:
                out.append(f"PLEN {n}:{i} пункт {m.group(1)} — Пленум № {num} в ответе выше полностью не назван или нет файла")
                continue
            pts = pl_points(PL[key])
            for p in re.findall(r"\d+(?:\.\d+)?", m.group(1)):
                if p not in pts:
                    out.append(f"PLEN {n}:{i} № {num}: пункта {p} нет")
        # --- ссылки на статьи УК ---
        for m in re.finditer(r"((?:п\. «[а-я](?:\.\d)?»(?:, «[а-я](?:\.\d)?»| и «[а-я](?:\.\d)?»| – «[а-я]»)* )?)((?:чч?\. [\d.]+(?:(?:, | и | – |–)[\d.]+)* )?)ст\. (\d+(?:\.\d+)?)(.{0,60})", l):
            pts, parts, art, tail = m.groups()
            if re.match(r"(?:(?:, | и |–| – )\d+(?:\.\d+)?)* " + OTHER, tail) or re.match(r" " + OTHER, tail):
                continue
            ctx = l[max(0, m.start() - 0):m.end() + 80]
            if art not in UK:
                if int(float(art)) > 361:
                    continue
                out.append(f"REF  {n}:{i} ст. {art} — нет в УК: …{raw[max(0, m.start()-30):m.end()-30]}…")
                continue
            a = UK[art]
            if a["void"]:
                if "утратил" not in l and "исключен" not in l and "отменен" not in l:
                    out.append(f"REF  {n}:{i} ст. {art} утратила силу: …{raw[max(0, m.start()-30):m.start()+60]}…")
                continue
            plist = re.findall(r"\d+(?:\.\d+)?", parts)
            rng = re.search(r"(\d+)\s*–\s*(\d+)", parts)
            if rng:
                plist = [str(x) for x in range(int(rng.group(1)), int(rng.group(2)) + 1)]
            for p in plist:
                if p not in a["parts"]:
                    out.append(f"REF  {n}:{i} ч. {p} ст. {art} — такой части нет: …{raw[max(0, m.start()-20):m.start()+70]}…")
            if pts and len(plist) == 1 and plist[0] in a["parts"]:
                have = a["parts"][plist[0]]["points"]
                for q in re.findall(r"«([а-я](?:\.\d)?)»", pts):
                    if q not in have:
                        out.append(f"REF  {n}:{i} п. «{q}» ч. {plist[0]} ст. {art} — такого пункта нет")
        # --- сроки и категории рядом с «ч. N» ---
        if re.search(r"тяжести|тяжк|лет|года", l) and "ч. " in l:
            for seg in re.split(r"[;]|\. (?=[А-ЯЧ])", l):
                arts_here = [x for x in re.findall(r"ст\. (\d+(?:\.\d+)?)", seg) if x in UK]
                if re.search(OTHER, seg):
                    continue
                for m in re.finditer(r"ч\. ([\d.]+)((?:(?:, | и )[\d.]+)*)(?: ст\. (\d+(?:\.\d+)?))?([^;]{0,140})", seg):
                    p0, more, art, tail = m.groups()
                    art = art or (arts_here[0] if len(set(arts_here)) == 1 else None) or main_art
                    if not art or art not in UK:
                        continue
                    plist = [p0.rstrip(".")] + re.findall(r"[\d.]+", more)
                    plist = [p.rstrip(".") for p in plist]
                    if any(p not in UK[art]["parts"] for p in plist):
                        continue
                    nxt = re.search(r"ч\. \d", tail)
                    tail_own = tail[:nxt.start()] if nxt else tail
                    # срок в скобках сразу после части
                    tm = re.match(r"\s*(?:ст\. [\d.]+ )?\((?:лишение свободы )?((?:от \w+ )?до \w+) (?:лет|года)", tail_own)
                    if tm and len(plist) == 1:
                        term = tm.group(1)
                        san = UK[art]["parts"][plist[0]]["san"]
                        if term not in san:
                            out.append(f"TERM {n}:{i} ч. {plist[0]} ст. {art}: «{term} лет» нет в санкции | {raw.strip()[:110]}")
                    cm = re.search(r"(небольшой тяжести|средней тяжести|особо тяжк(?=ое|ие|им)|(?<!особо )тяжк(?=ое\b|ие\b|им\b)(?!\w* (?:вред|последств|преступлени[ея] против)))", tail_own[:90])
                    if cm:
                        said = cm.group(1).replace(" тяжести", "")
                        for p in plist:
                            calc = category(UK[art]["parts"][p]["san"])
                            if calc != said:
                                y, life = maxterm(UK[art]["parts"][p]["san"])
                                out.append(f"CAT  {n}:{i} ч. {p} ст. {art}: в ответе «{said}», по санкции «{calc}» (макс. {y}{', пожизн.' if life else ''}) | {raw.strip()[:100]}")
    return out


if __name__ == "__main__":
    total = 0
    for n in range(1, 118):
        if ONLY and n not in ONLY:
            continue
        if not os.path.exists(os.path.join(A, f"q{n:03d}.txt")):
            continue
        for s in check(n):
            print(s)
            total += 1
    print(f"-- пометок: {total}")
