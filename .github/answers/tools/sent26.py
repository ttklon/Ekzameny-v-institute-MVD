#!/usr/bin/env python3
"""Счёт абзацев и предложений в ответах (для журнала full-read.md).

Запуск из .github/answers:
    python3 tools/sent26.py ПАПКА_ВАРИАНТА_1 [ОТ ДО]
ПАПКА_ВАРИАНТА_1 — каталог, созданный tools/v1split.py (по файлу на вопрос).
Без ОТ и ДО печатает итог по всем наборам; с ними — ещё и по вопросам ОТ..ДО.

Правило: абзац — непустая строка (служебная строка «@@» не считается);
в абзаце одно предложение плюс по одному на каждый знак «.», «!» или «?»,
за которым идут пробел и заглавная буква (перед ней допускаются « и *).
Ссылки //…// перед счётом заменяются одной буквой.
"""
import glob
import re
import sys

END = re.compile(r'[.!?] +[«*]*[А-ЯЁA-Z]')


def count(path):
    par = sen = 0
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('@@'):
            continue
        par += 1
        sen += 1 + len(END.findall(re.sub(r'//.*?//', 'R', line)))
    return par, sen


def total(files):
    p = s = 0
    for f in files:
        a, b = count(f)
        p += a
        s += b
    return p, s


def main():
    v1 = sys.argv[1]
    sets = [('вариант 2', sorted(glob.glob('adp2/q*.txt'))),
            ('вариант 1', sorted(glob.glob(v1 + '/q*.txt'))),
            ('УПП', sorted(glob.glob('upp/q*.txt')))]
    for name, files in sets:
        print(name, 'абзацев %d, предложений %d' % total(files))
    if len(sys.argv) > 3:
        lo, hi = int(sys.argv[2]), int(sys.argv[3])
        tp = [0, 0, 0, 0]
        for q in range(lo, hi + 1):
            a = count('adp2/q%03d.txt' % q)
            b = count('%s/q%03d.txt' % (v1, q))
            print(q, 'вариант 2: %d и %d; вариант 1: %d и %d' % (a + b))
            for i, v in enumerate(a + b):
                tp[i] += v
        print('итого %d–%d: вариант 2 — %d и %d; вариант 1 — %d и %d' % (lo, hi, *tp))


if __name__ == '__main__':
    main()
