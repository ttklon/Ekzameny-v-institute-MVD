#!/usr/bin/env python3
"""Печать статей кодекса или закона из извлечённых текстов Криминалистики.

    python tools/kart.py SRC КОД СТАТЬЯ[:ЧАСТИ] ...

SRC — каталог, созданный kextract.py; КОД — первые шесть знаков имени файла
(12e5b7 — УПК, fc7900 — УК: тексты из HTML, по абзацу на строку).
СТАТЬЯ — номер («164», «164.1» — для статей с надстрочным номером);
ЧАСТИ — через запятую номера частей («164:4» печатает только ч. 4).
Служебные строки редакций («(в ред. …)») опускаются.
"""
import glob
import re
import sys


def load(src, code):
    path = glob.glob(f"{src}/{code}*")[0]
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"@@ \d+ \| \S+\n", "", text)
    return [re.sub(r"\s+", " ", l).strip() for l in text.split("\n")]


def article(lines, num):
    pat = num.replace(".", r" ?\.? ?")
    head = re.compile(rf"^Статья {pat}\s*\.(?!\d)")
    nxt = re.compile(r"^(Статья \d|Глава \d|Раздел [IVXLC]+|ГЛАВА|РАЗДЕЛ)")
    out, on = [], False
    for l in lines:
        if not l:
            continue
        if on and nxt.match(l):
            break
        if not on and head.match(l):
            on = True
        if on and not re.match(r"^\((в ред\.|часть|п\.|пункт|абзац|введен)", l):
            out.append(l)
    return out


def main():
    src, code, *arts = sys.argv[1:]
    lines = load(src, code)
    for a in arts:
        num, _, parts = a.partition(":")
        body = article(lines, num)
        if not body:
            print(f"!! статья {num} не найдена")
            continue
        print(body[0])
        want = set(parts.split(",")) if parts else None
        cur = None
        for l in body[1:]:
            m = re.match(r"^(\d+(?:\.\d+)?)\. ", l)
            if m:
                cur = m.group(1)
            if want is None or cur in want:
                print("  " + l)
        print()


if __name__ == "__main__":
    main()
