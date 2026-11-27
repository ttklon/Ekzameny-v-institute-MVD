#!/usr/bin/env python3
"""Сборка перечня вопросов из рабочих частей.

Использование:
    python3 .github/answers/tools/build_questions.py <код> <ожидаемое число> "<заголовок>" "<путь к итоговому .txt>"

Части лежат в .github/answers/<код>/parts/NN.txt. Строка «# …» — заголовок раздела,
строка «## …» — заголовок подраздела, любая другая непустая строка — один вопрос.
Скрипт нумерует вопросы подряд, проверяет число, повторы и опечатки раскладки
и пишет файл в кодировке UTF-8 с переводами строк CRLF, как в остальных перечнях.
"""
import glob
import os
import re
import sys

code, expected, title, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parts = sorted(glob.glob(os.path.join(root, code, "parts", "*.txt")))
lines, questions, sections, errors = [title, ""], [], [], []
n = 0
for p in parts:
    for raw in open(p, encoding="utf-8").read().splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("## "):
            lines += ["", s[3:], ""]
        elif s.startswith("# "):
            sections.append([s[2:], 0])
            lines += ["", "", s[2:].upper(), ""]
        else:
            n += 1
            sections[-1][1] += 1
            questions.append(s)
            lines.append(f"{n}. {s}")
            if not s.endswith((".", "?")):
                errors.append(f"нет точки: {n}. {s}")
            if re.search(r"[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]", s):
                errors.append(f"смешение раскладок: {n}. {s}")
            if "  " in s:
                errors.append(f"двойной пробел: {n}. {s}")
norm = {}
for i, q in enumerate(questions, 1):
    k = re.sub(r"[^а-яёa-z0-9]", "", q.lower())
    if k in norm:
        errors.append(f"повтор: {norm[k]} и {i}: {q}")
    norm[k] = i
if n != expected:
    errors.append(f"вопросов {n}, ожидалось {expected}")
for name, cnt in sections:
    print(f"{cnt:4d}  {name}")
print(f"{n:4d}  всего")
if errors:
    print("\n".join(errors))
    sys.exit(1)
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write("\r\n".join(lines).strip() + "\r\n")
print("записано:", out)
