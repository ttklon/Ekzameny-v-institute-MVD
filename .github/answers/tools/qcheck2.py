#!/usr/bin/env python3
"""qcheck2.py SRC — цитата, за которой стоит ссылка (//…//), проверяется на принадлежность названному акту,
а для Закона о полиции и КоАП РФ — названной статье. Контекст неполной ссылки («ч. 2») берётся в пределах раздела."""
import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
from qcheck import norm, quotes   # noqa (qcheck при импорте читает sys.argv[1] и строит общий корпус)
import qcheck
src = sys.argv[1]
files = {}
for l in open(os.path.join(src, '_index.tsv'), encoding='utf-8'):
    nm, rel = l.rstrip('\n').split('\t'); files[rel] = os.path.join(src, nm)
def clean(raw):
    raw = re.sub(r'<\d+>', ' ', raw)
    return re.sub(r'\((?:В редакции|Дополнен|Абзац|Пункт|Часть|Подпункт|Статья|Наименование|Утратил|Введен|Изменен)[^()]{0,400}\)', ' ', raw)
def load(pat):
    return [clean(open(f, encoding='utf-8', errors='replace').read()) for n, f in sorted(files.items()) if re.search(pat, n)]
def articles(raw, koap=False):
    """{номер статьи: нормализованный текст}; понимает и PDF («Статья 19.151.»), и HTML («Статья 19.15 1 .»)"""
    res = {}; base = None; ms = list(re.finditer(r'Статья\s+(\d+)(?:\.(\d+))?(?:\s(\d)\s)?\s?\.\s+(?=[А-ЯЁ(])', raw))
    for i, m in enumerate(ms):
        a, b, c = m.group(1), m.group(2), m.group(3)
        if b is None: num = a
        elif c: num = '%s.%s.%s' % (a, b, c)
        elif koap and base and base[0] == a and b.startswith(base[1]) and len(b) > len(base[1]): num = '%s.%s.%s' % (a, base[1], b[len(base[1]):])
        else: num = '%s.%s' % (a, b); base = (a, b)
        txt = norm(raw[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(raw)])
        res[num] = res.get(num, '') + txt
    return res
POL = [articles(t) for t in load(r'№ 3-ФЗ О полиции')]
KOAP = [articles(t, True) for t in load(r'КоАП РФ от 30\.12\.2001')]
print('статей: Закон о полиции', [len(x) for x in POL], 'КоАП', [len(x) for x in KOAP])
NAMED = [(r'ополиции|№3фз', 'POL', r'№ 3-ФЗ О полиции'), (r'коап|обадминистративныхправ', 'KOAP', r'КоАП РФ от'), (r'ослужбе', None, r'№ 342-ФЗ'), (r'опрокуратуре', None, r'№ 2202-1'),
         (r'уголовногокодекса|^укрф|уголовныйкодекс', None, r'УК РФ|Уголовный кодекс'), (r'уголовнопроцесс|упкрф', None, r'УПК|Уголовно-процессуальн'), (r'конституци', 'SKIP', ''), (r'положенияоминистерстве|положениеоминистерстве|положенияомвд|положениеомвд', None, r'№ 699'), (r'кодексаэтики|кодексэтики', None, r'№ 460')]
cache = {}
def act_files(disp):
    key = norm(disp)
    m = re.search(r'№ ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', disp)
    if m and m.group(1) not in ('3-ФЗ', '195-ФЗ', '342-ФЗ', '2202-1', '63-ФЗ', '174-ФЗ'):
        return None, r'№ ' + re.escape(m.group(1).split('/')[0]) + r'(?![\d-])'
    for pat, kind, fp in NAMED:
        if re.search(pat, key): return kind, fp
    m = re.search(r'№ ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', disp)
    if m: return None, r'№ ' + re.escape(m.group(1)) + r'(?![\d-])'
    return 'UNK', ''
tot = chk = art_chk = 0; out = []
for f in sorted(glob.glob(cut25.A + 'q*.txt')):
    n = int(f[-7:-4]); txt = open(f, encoding='utf-8').read(); lines = txt.split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip() and not l.startswith('!! ')]
    res, names = cut25.resolve(pieces)
    for (i, _z), line in pieces:
        if line.startswith('#'): continue
        refs = list(cut25.REF.finditer(line))
        for a, b in quotes(line):
            q = line[a + 1:b - 1]
            if len(q.split()) < 4 or re.match(r'Об? ', q): continue      # названия актов не проверяются
            # ссылка сразу после цитаты (до следующей цитаты, не дальше 60 знаков)
            k = next((k for k, m in enumerate(refs) if m.start() >= b and m.start() - b <= 60 and '«' not in line[b:m.start()]), None)
            if k is None: continue
            tot += 1
            act, art = res[((i, 0), k)]; disp = names[((i, 0), k)]
            if not disp: continue
            kind, fp = act_files(disp)
            if kind in ('SKIP', 'UNK'): continue
            segs = [norm(x) for x in re.split(r'\s*(?:\.\.\.|…)\s*', q) if len(norm(x)) >= 12]
            if fp not in cache: cache[fp] = [norm(t) for t in load(fp)]
            if not cache[fp]: out.append('q%03d:%d нет файла акта «%s» для цитаты «%s»' % (n, i + 1, disp[:50], q[:60])); continue
            chk += 1
            if not all(any(sg in t for t in cache[fp]) for sg in segs):
                w = qcheck.where(segs[0]); out.append('q%03d:%d НЕ В ЭТОМ АКТЕ (%s → %s): «%s» | найдено в: %s' % (n, i + 1, line[refs[k].start():refs[k].end()][:70], disp[:60], q[:110], w)); continue
            if kind in ('POL', 'KOAP') and art:
                arts = POL if kind == 'POL' else KOAP; art_chk += 1
                if not any(art in A and all(sg in A[art] for sg in segs) for A in arts):
                    found = sorted({x for A in arts for x, t in A.items() if all(sg in t for sg in segs)})
                    out.append('q%03d:%d НЕ В ЭТОЙ СТАТЬЕ (%s → ст. %s): «%s» | найдено в ст.: %s' % (n, i + 1, line[refs[k].start():refs[k].end()][:60], art, q[:110], ', '.join(found[:6])))
print('цитат со ссылкой:', tot, 'проверено по акту:', chk, 'по статье:', art_chk, 'замечаний:', len(out))
for o in out: print(o)
if len(sys.argv) > 2:
    for o in out:
        m = re.match(r'q(\d+):(\d+) ', o); L = open(cut25.A + 'q%s.txt' % m.group(1), encoding='utf-8').read().split('\n'); print('>>', o[:60]); print('   ', L[int(m.group(2)) - 1][:700])
