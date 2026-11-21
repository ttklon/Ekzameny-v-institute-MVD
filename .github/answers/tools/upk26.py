#!/usr/bin/env python3
"""upk26.py СТАТЬЯ[:части через запятую][=макс. знаков] … — печатает статью УПК РФ из папки источников УПП.

Текст берётся из HTML-копии официальной публикации (2. Источники/1. Нормативные правовые акты/2. Кодексы).
Надстрочные номера (статья 6^1^) печатаются как «6.1». Пометки о редакциях сжаты до года, если он не раньше 2023:
«{2025}» после части значит, что часть менялась в 2025 году.
    upk26.py 91 92:1,2 108=3000
    upk26.py --changed        — статьи, менявшиеся с 2024 года (номер закона)
Как модуль: load() → (словарь статей, порядок); part(статья, часть) → текст части; has(статья, часть, пункт).
"""
import glob, html, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', '..', 'Уголовно-процессуальное право', '2. Источники',
                   '1. Нормативные правовые акты', '2. Кодексы', 'Исходные страницы (HTML)')
_cache = None


def load():
    global _cache
    if _cache:
        return _cache
    f = [p for p in glob.glob(os.path.join(SRC, '*.html')) if 'процессуальный' in p][0]
    t = open(f, encoding='utf-8').read()
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', t, flags=re.S | re.I)
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    t = re.sub(r'<span class="W9">\s*(.*?)\s*</span>', lambda m: '^' + m.group(1) + '^', t, flags=re.S)
    t = re.sub(r'<br\s*/?>|</p>|</div>|</h\d>|</tr>', '\n', t, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    t = re.sub(r'[ \t\xa0\r]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t).replace('^^', '')
    arts, order, cur = {}, [], None
    for line in t.split('\n'):
        line = line.strip()
        m = re.match(r'Статья (\d+)(?:\^(\d+)\^)?\.?\s*(.*)', line)
        if m and not re.match(r'Статья \d+[^.]*(настоящего|УК|Уголовного)', line):
            cur = m.group(1) + ('.' + m.group(2) if m.group(2) else '')
            arts[cur] = {'title': m.group(3), 'lines': []}
            order.append(cur)
            continue
        if cur and re.match(r'(Глава|ГЛАВА|Раздел|РАЗДЕЛ|ЧАСТЬ)\b', line):
            arts[cur]['lines'].append('@@' + line)
        elif cur:
            arts[cur]['lines'].append(line)
    _cache = (arts, order)
    return _cache


def clean(s, notes=True):
    s = re.sub(r'\^(\d+)\^', r'.\1', s)

    def note(m):
        ys = sorted({y for y in re.findall(r'\d\d\.\d\d\.(20\d\d)', m.group(0)) if int(y) >= 2023})
        return ' {%s}' % ','.join(ys) if ys and notes else ''
    s = re.sub(r'\((?:В редакции|Дополнение|Часть|Наименование|Пункт|Абзац|Статья|Утратил|Утратила|Дополнен)[^)]*'
               r'[Фф]едеральн[^)]*\)', note, s)
    return s.strip()


def parts(num, notes=False):
    """Части статьи: {'1': текст, '1.1': текст, …}; ключ '' — текст до первой нумерованной части."""
    arts, _ = load()
    res, key = {'': ''}, ''
    for l in arts[num]['lines']:
        if l.startswith('@@'):
            continue
        l = clean(l, notes)
        m = re.match(r'(\d+(?:\.\d+)?)\. ', l)
        if m:
            key = m.group(1)
            res[key] = ''
        res[key] += l + '\n'
    return res


def part(num, p):
    return parts(num).get(str(p))


def has(num, p=None, pt=None):
    arts, _ = load()
    if num not in arts:
        return False
    if p is None and pt is None:
        return True
    ps = parts(num)
    if p is not None:
        if str(p) not in ps:
            return False
        txt = ps[str(p)]
    else:
        txt = '\n'.join(ps.values())
    if pt is None:
        return True
    return re.search(r'(?m)^%s\) ' % re.escape(str(pt)), txt) is not None


if __name__ == '__main__':
    arts, order = load()
    if sys.argv[1:] == ['--changed']:
        for n in order:
            txt = arts[n]['title'] + '\n' + '\n'.join(arts[n]['lines'])
            ys = set()
            for m in re.finditer(r'\((?:В редакции|Дополнение|Утратил|Утратила|Статья|Часть|Пункт|Наименование|Абзац)[^)]*\)', txt):
                for y, k in re.findall(r'от \d\d\.\d\d\.(20\d\d) № (\d+)-ФЗ', m.group(0)):
                    if int(y) >= 2024:
                        ys.add('%s № %s' % (y, k))
            if ys:
                print(n, '; '.join(sorted(ys)))
        sys.exit()
    for arg in sys.argv[1:]:
        mx = None
        if '=' in arg:
            arg, mx = arg.split('=')
            mx = int(mx)
        want = None
        if ':' in arg:
            arg, p = arg.split(':')
            want = p.split(',')
        if arg not in arts:
            print('### НЕТ СТАТЬИ', arg)
            continue
        print('### Ст. %s. %s' % (arg, clean(arts[arg]['title'])))
        ps = parts(arg, notes=True)
        s = ''.join(v for k, v in ps.items() if want is None or k in want)
        s = re.sub(r'\n\(О несоответствии[^\n]*', '', s).strip()
        print(s if mx is None else s[:mx] + (' …' if len(s) > mx else ''))
