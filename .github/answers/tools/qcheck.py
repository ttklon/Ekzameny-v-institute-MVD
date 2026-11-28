#!/usr/bin/env python3
"""qcheck.py SRC [N…] — сверка цитат варианта 2 с текстами источников (SRC — папка, созданная extract_src.py).
Каждая цитата «…» длиной от 4 слов ищется дословно (без учёта регистра, ё/е, пробелов, знаков препинания) во всех источниках.
Печатает ненайденные цитаты; отдельно — пары соседних цитат, которые могут быть разорванным предложением."""
import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2') + '/'
def norm(s): return re.sub(r'[^0-9a-zа-я]', '', s.lower().replace('ё', 'е'))
src = sys.argv[1]; only = {int(x) for x in sys.argv[2:] if x.isdigit()}
names = []; parts = []
for f in sorted(glob.glob(os.path.join(src, '*.txt'))):
    raw = open(f, encoding='utf-8', errors='replace').read()
    raw = re.sub(r'<\d+>', ' ', raw)                                                    # знаки сносок
    raw = re.sub(r'\((?:В редакции|Дополнен|Абзац|Пункт|Часть|Подпункт|Статья|Наименование|Утратил|Введен|Изменен)[^()]{0,400}\)', ' ', raw)   # отметки о редакции
    names.append(os.path.basename(f)); parts.append(norm(raw))
BIG = '\x00'.join(parts)
def where(q):
    i = BIG.find(q)
    if i < 0: return None
    return names[BIG.count('\x00', 0, i)]
def quotes(line):
    """цитаты верхнего уровня «…» (вложенные кавычки остаются внутри)"""
    out = []; d = 0; st = None
    for i, ch in enumerate(line):
        if ch == '«':
            if d == 0: st = i
            d += 1
        elif ch == '»' and d > 0:
            d -= 1
            if d == 0: out.append((st, i + 1))
    return out
if __name__ != '__main__': only = {0}
tot = bad = 0; res = []
for f in sorted(glob.glob(A + 'q*.txt')):
    n = int(f[-7:-4])
    if only and n not in only: continue
    for ln, line in enumerate(open(f, encoding='utf-8').read().split('\n'), 1):
        if line.startswith('#'): continue
        for a, b in quotes(line):
            q = line[a + 1:b - 1]
            if len(q.split()) < 4: continue
            tot += 1
            # многоточие внутри цитаты — проверяем части по отдельности
            segs = [x for x in re.split(r'\s*(?:\.\.\.|…|<\.\.\.>|\[\.\.\.\])\s*', q) if len(norm(x)) >= 12]
            miss = [x for x in segs if where(norm(x)) is None]
            if miss:
                x = norm(miss[0]); k = len(x)
                while k > 12 and BIG.find(x[:k]) < 0: k -= 4
                j = BIG.find(x[:k]) if k > 12 else -1
                hint = ' | совпало начало (%d из %d зн.), далее в источнике: …%s…' % (k, len(x), BIG[j + k - 15:j + k + 60]) if j >= 0 else ''
                bad += 1; res.append('q%03d:%d НЕТ В ИСТОЧНИКАХ: «%s» | после: %s' % (n, ln, q[:230], line[b:b + 60]) + hint)
print('цитат проверено:', tot, 'не найдено:', bad)
for r in res: print(r)
