#!/usr/bin/env python3
"""ugpsupport.py SRC [--t=0.6] [--all] [N…] — опора строк ответов по Уголовному праву на названную норму.

Для каждой ссылки //(…)// берётся отрезок ответа перед ней (и пункты списка под ней, если строка
кончается двоеточием) и текст названных в ссылке норм: статьи (части) УК, УПК, УИК, КоАП, Конституции
или пункта постановления Пленума. Считается доля значимых слов отрезка (по первым пяти буквам),
которые есть в тексте нормы. Печатаются отрезки с долей ниже порога — их читают глазами рядом с нормой.
Низкая доля не означает ошибку (пересказ, вывод, пример), высокая — не доказывает верность:
это способ найти места, где ссылка могла встать не к той норме.
    python3 tools/ugpsupport.py /tmp/usrc --t=0.5 1 2 3
Ключ --all печатает все отрезки с долей; --src печатает под отрезком начало текста нормы.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
args = [x for x in sys.argv[1:] if not x.startswith("--")]
opts = dict((x[2:].split("=") + ["1"])[:2] for x in sys.argv[1:] if x.startswith("--"))
sys.argv = [sys.argv[0], args[0]]
import ugpcheck as U  # noqa: E402
import kart  # noqa: E402

SRC = args[0]
ONLY = {int(x) for x in args[1:] if x.isdigit()}
T = float(opts.get("t", 0.6))
CODES = {"УПК": "12e5b7", "УИК": "4e7f02", "КоАП": "22b901", "О полиции": "07a385", "342-ФЗ": "7d485b",
         "государственной тайне": "35ca53", "498-ФЗ": "5f1237"}
ALIAS = {"Закона о службе": "342-ФЗ", "Закон о службе": "342-ФЗ", "№ 3-ФЗ": "О полиции"}
_lines = {}
STOP = set("котор этого этому такой также может могут должн если либо только более менее между через после перед "
           "лицо лица лицу лицом стать часть части пункт далее иными иные иных своих свою свое того тому этим "
           "быть было были будет является являются имеет имеют самого самой всех всем него нему ними"
           .split())


def stems(s):
    s = re.sub(r"//\([^/]*\)//", " ", s)
    w = re.findall(r"[а-яa-z]{4,}", U.e(s.lower()))
    return {x[:5] for x in w if x[:5] not in STOP}


def code_art(code, art):
    if code not in _lines:
        _lines[code] = kart.load(SRC, code)
    return " ".join(kart.article(_lines[code], art))


def uk_text(art, parts):
    a = U.UK.get(art)
    if not a:
        return ""
    if not parts:
        return a["title"] + " " + " ".join(a["raw"])
    out = [a["title"]]
    for p in parts:
        if p in a["parts"]:
            out.append(a["parts"][p]["text"] + " " + a["parts"][p]["san"])
    return " ".join(out)


def pl_point(t, p):
    """текст пункта p («14», «14.1») до начала следующего пункта или подпункта"""
    pos, found = 0, {}
    for n in range(1, 200):
        i = t.find(f" {n}. ", pos)
        if i < 0:
            continue
        found[str(n)] = i
        pos = i + 1
    for m in re.finditer(r" (\d+)[.(](\d+)\)?\. ", t):
        found.setdefault(f"{m.group(1)}.{m.group(2)}", m.start())
    if p not in found:
        return ""
    nxt = sorted(v for v in found.values() if v > found[p])
    return t[found[p]:(nxt[0] if nxt else found[p] + 4000)]


def resolve(cite, plen_names, cur=None):
    """текст норм, названных в ссылке; None — если акт не поддержан"""
    c = U.e(cite).replace("Верховного Суда Российской Федерации", "Верховного Суда РФ")
    c = re.sub(r"(\d+)\((\d+)\)", r"\1.\2", c)
    c = c.replace("Пленума от", "Пленума Верховного Суда РФ от")
    texts, unknown = [], False
    # «п. 5», «пп. 3, 4», «п. 7 того же постановления» — пункт последнего названного Пленума
    m = re.fullmatch(r"пп?\. ([\d., –и]+?)(?: того же постановления| постановления)?(?:, в редакции[^;]*)?", c.strip())
    if m:
        if cur not in U.PL:
            return None
        nums = re.findall(r"\d+(?:\.\d+)?", m.group(1))
        rng = re.search(r"(\d+)\s*–\s*(\d+)", m.group(1))
        if rng:
            nums = [str(x) for x in range(int(rng.group(1)), int(rng.group(2)) + 1)]
        t = " ".join(pl_point(U.PL[cur], p) for p in nums)
        return U.e(t.lower()) if t.strip() else None
    # Пленумы
    for m in re.finditer(r"пп?\. ([\d., –и]+?) (?:постановления )?Пленума (?:Верховного Суда РФ от (\d\d\.\d\d\.\d{4}) )?№ (\d+)", c):
        key = (m.group(2), m.group(3)) if m.group(2) else plen_names.get(m.group(3))
        if key in U.PL:
            nums = re.findall(r"\d+(?:\.\d+)?", m.group(1))
            rng = re.search(r"(\d+)\s*–\s*(\d+)", m.group(1))
            if rng:
                nums = [str(x) for x in range(int(rng.group(1)), int(rng.group(2)) + 1)]
            for p in nums:
                texts.append(pl_point(U.PL[key], p))
        else:
            unknown = True
    c2 = re.sub(r"пп?\. [\d., –и]+? (?:постановления )?Пленума[^;]*", " ", c)
    # статьи: делим по «;» и по запятым между разными актами
    for piece in re.split(r";", c2):
        code = None
        for k in CODES:
            if k in piece or (k == "УПК" and "Уголовно-процессуальн" in piece) or (k == "УИК" and "Уголовно-исполнительн" in piece) \
                    or (k == "КоАП" and "административных правонарушениях" in piece):
                code = k
        for a, k in ALIAS.items():
            if a in piece:
                code = k
        if code is None and re.search(r"закона|Закона|ФЗ|Конституци|Конвенци|Положени|Правил|приказ|Указ|Устав", piece):
            if re.search(r"ст\. \d", piece):
                unknown = True
            continue
        for m in re.finditer(r"((?:чч?\. [\d.]+(?:(?:, | и | – |–)[\d.]+)* )?)(?:ст\.|статьи|статья) (\d+(?:\.\d+)?)((?:(?:, | и |–| – )\d+(?:\.\d+)?)*)", piece):
            parts = [p.rstrip(".") for p in re.findall(r"\d+(?:\.\d+)?", m.group(1))]
            arts = [m.group(2)] + re.findall(r"\d+(?:\.\d+)?", m.group(3))
            rng = re.match(r"(?:–| – )(\d+)$", m.group(3))
            if rng and "." not in m.group(2):
                arts = [str(x) for x in range(int(m.group(2)), int(rng.group(1)) + 1)]
            for a in arts:
                if code is None:
                    full = "примечани" in piece
                    texts.append(uk_text(a, [] if full or len(arts) > 1 else parts))
                else:
                    texts.append(code_art(CODES[code], a))
    if not texts:
        return None if unknown or True else ""
    return U.e(" ".join(texts).lower())


def segments(L):
    """(номер строки, отрезок, ссылка)"""
    for i, raw in enumerate(L):
        pos = 0
        ms = list(re.finditer(r"//\(([^/]*)\)//", raw))
        for k, m in enumerate(ms):
            seg = raw[pos:m.start()]
            pos = m.end()
            rest = raw[m.end():].strip()
            if (seg.rstrip().endswith(":") or rest.startswith(":")) and k == len(ms) - 1:
                j = i + 1
                while j < len(L) and re.match(r"^\s*- ", L[j]):
                    seg += " " + re.sub(r"//\([^/]*\)//", " ", L[j])
                    j += 1
            elif k == len(ms) - 1 and len(stems(seg)) < 4 and rest:
                seg += " " + rest
            yield i + 1, seg, m.group(1)


def run(n):
    path = os.path.join(U.A, f"q{n:03d}.txt")
    L = open(path, encoding="utf-8").read().split("\n")
    plen_names, curat = {}, {}
    cur = None
    for i, raw in enumerate(L):
        l = U.e(raw).replace("Верховного Суда Российской Федерации", "Верховного Суда РФ").replace("Пленума от", "Пленума Верховного Суда РФ от")
        ev = []
        for m in re.finditer(r"(?:Пленума Верховного Суда РФ|(?<=\) и)) от (\d\d\.\d\d\.\d{4}) № (\d+)", l):
            plen_names.setdefault(m.group(2), (m.group(1), m.group(2)))
            ev.append((m.start(), (m.group(1), m.group(2))))
        for m in re.finditer(r"Пленума № (\d+)", l):
            if m.group(1) in plen_names:
                ev.append((m.start(), plen_names[m.group(1)]))
        ev.sort()
        curat[i + 1] = (cur, ev)
        if ev:
            cur = ev[-1][1]
    res = []
    for ln, seg, cite in segments(L):
        st = stems(seg)
        c0, ev = curat[ln]
        tl = U.e(L[ln - 1]).replace("Верховного Суда Российской Федерации", "Верховного Суда РФ").replace("Пленума от", "Пленума Верховного Суда РФ от")
        tc = U.e(cite).replace("Верховного Суда Российской Федерации", "Верховного Суда РФ").replace("Пленума от", "Пленума Верховного Суда РФ от")
        pos = tl.find(tc) + len(tc)
        for p, k in ev:
            if p < pos:
                c0 = k
        src = resolve(cite, plen_names, c0)
        if src is None:
            res.append((ln, None, seg, cite, ""))
            continue
        if len(st) < 3:
            continue
        have = stems(src)
        miss = sorted(x for x in st if x not in have)
        res.append((ln, 1 - len(miss) / len(st), seg, cite, " ".join(miss), src))
    return res


if __name__ == "__main__":
    tot = low = unk = 0
    for n in range(1, 118):
        if ONLY and n not in ONLY:
            continue
        for r in run(n):
            ln, sc, seg, cite = r[:4]
            if sc is None:
                unk += 1
                if "unk" in opts:
                    print(f"{n}:{ln} ?    | {cite[:90]}")
                continue
            tot += 1
            if sc < T or "all" in opts:
                low += sc < T
                s = re.sub(r"\s+", " ", seg).strip()
                print(f"{n}:{ln} {sc:.2f} [{cite[:70]}] {s[:int(opts.get('w', 230))]}")
                print(f"      нет: {r[4][:160]}")
                if "src" in opts:
                    print(f"      норма: {r[5][:int(opts['src']) if opts['src'].isdigit() else 400]}")
    print(f"-- ссылок проверено: {tot}; ниже порога {T}: {low}; акт не поддержан: {unk}")
