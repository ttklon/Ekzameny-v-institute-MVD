#!/usr/bin/env python3
"""uppcheck.py [N1 N2] [--all] — сверка ссылок на УПК РФ в ответах по уголовно-процессуальному праву.

Для каждой ссылки вида «п. 3 ч. 2 ст. 29», «ч. 2, 3 ст. 187», «ст. 61–65» проверяет, что такая статья, часть и
пункт есть в тексте Кодекса из папки источников (редакция на 06.08.2026), и считает, сколько значимых слов
строки ответа встречается в названной норме. Печатает:
  НЕТ   — статьи, части или пункта в Кодексе нет (ошибка в ссылке);
  МАЛО  — общих слов меньше порога: ссылку надо открыть и прочитать (часто ложное срабатывание);
  ЧИСЛО — срок из строки ответа («5 суток», «3 часов», «6 месяцев») не найден ни в одной из норм,
          на которые строка ссылается: срок надо сверить с текстом.
Ссылки на УК, Конституцию и другие законы пропускаются. С ключом --all печатает и совпавшие ссылки.
"""
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upk26

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set('котор также может могут должн после если иных иные этого этом либо только случа числе лицо лица лицу '
           'уголо дела делу делам насто кодек стать части пункт'.split())
REF = re.compile(r'(?:(?:подп|п)\. (?P<pt>\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*) )?'
                 r'(?:ч\. (?P<ch>\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*) )?'
                 r'ст\. (?P<st>\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*)(?=(?P<tail>[^;()/]{0,40}))')
OTHER = re.compile(r'^\s*(УК|Конституци|Уголовного кодекса|УИК|Закона|Федерального|ГК|ГПК|КоАП|Пакта|Конвенци|закона)')


WORDS = {'1': 'од', '2': 'дв', '3': 'тр', '4': 'четыр', '5': 'пят', '6': 'шест', '7': 'сем', '8': 'восьм|восем',
         '9': 'девят', '10': 'десят', '12': 'двенадцат', '14': 'четырнадцат', '15': 'пятнадцат', '16': 'шестнадцат',
         '18': 'восемнадцат', '20': 'двадцат', '24': 'двадцат[ьи] четыр', '30': 'тридцат', '48': 'сорок[а]? восьм',
         '72': 'семидесят[ьи] дв'}
UNIT = r'(сут|час|месяц|лет|год|дн|недел|минут)'


def numbers(line):
    return set(re.findall(r'(\d+) ' + UNIT, line))


def num_in(num, unit, txt):
    w = WORDS.get(num)
    pat = r'(?<![\d.])%s(?![\d.])\D{0,25}%s' % (num, unit)
    if re.search(pat, txt):
        return True
    return bool(w and re.search(r'\b(%s)\w*\W{1,3}(\w+\W{1,3}){0,2}%s' % (w, unit), txt.lower()))


def stems(s):
    return {w[:5] for w in re.findall(r'[а-яё]{4,}', s.lower().replace('ё', 'е'))} - STOP


def items(s):
    """«2, 3» → ['2','3']; «61–65» → ('61','65') как диапазон."""
    res = []
    for bit in re.split(r', | и ', s):
        if '–' in bit:
            a, b = bit.split('–')
            res.append((a, b))
        else:
            res.append(bit)
    return res


def expand(rng, pool):
    a, b = rng
    if a in pool and b in pool:
        return pool[pool.index(a):pool.index(b) + 1]
    return [a, b]


def check(n, show_all):
    path = os.path.join(HERE, '..', 'upp', 'q%03d.txt' % n)
    arts, order = upk26.load()
    out = []
    for ln, line in enumerate(open(path, encoding='utf-8').read().split('\n'), 1):
        if line.startswith(('!! ', '## ')):
            continue
        plain = re.sub(r'\*\*|//|__', '', line)
        line_txt = []
        # чужой закон может стоять перед скобкой: «(ст. 22 Конституции)», «по ст. 301 УК»
        for m in REF.finditer(plain):
            if OTHER.match(m.group('tail')):
                continue
            rest = re.split(r'[;)]|\. (?=[А-ЯЁ])', plain[m.end('st'):])[0]
            if re.search(r'(?<![А-Яа-я])(УК|УИК)(?![А-Яа-я])|Конституци', rest):
                continue
            sts = []
            ranged = '–' in m.group('st')
            for it in items(m.group('st')):
                sts += expand(it, order) if isinstance(it, tuple) else [it]
            chs = []
            pts = []
            for st in sts:
                if st not in arts:
                    out.append((n, ln, 'НЕТ', 'ст. %s' % st, plain))
                    continue
                keys = list(upk26.parts(st))
                txt_all = arts[st]['title'] + '\n' + '\n'.join(upk26.parts(st).values())
                chs = []
                if m.group('ch') and st == sts[0]:
                    for it in items(m.group('ch')):
                        chs += expand(it, keys) if isinstance(it, tuple) else [it]
                pts = []
                if m.group('pt') and st == sts[0]:
                    for it in items(m.group('pt')):
                        pts += [str(x) for x in range(int(it[0]), int(it[1]) + 1)] if isinstance(it, tuple) and '.' not in it[0] + it[1] else (list(it) if isinstance(it, tuple) else [it])
                targets = []
                if chs:
                    for ch in chs:
                        ptxt = upk26.part(st, ch)
                        if ptxt is None:
                            out.append((n, ln, 'НЕТ', 'ч. %s ст. %s' % (ch, st), plain))
                            continue
                        if pts:
                            for pt in pts:
                                mm = re.search(r'(?m)^%s\) .*' % re.escape(pt), ptxt)
                                if not mm:
                                    out.append((n, ln, 'НЕТ', 'п. %s ч. %s ст. %s' % (pt, ch, st), plain))
                                else:
                                    targets.append(('п. %s ч. %s ст. %s' % (pt, ch, st), mm.group(0)))
                        else:
                            targets.append(('ч. %s ст. %s' % (ch, st), ptxt))
                elif pts:
                    for pt in pts:
                        mm = re.search(r'(?m)^%s\) .*' % re.escape(pt), txt_all)
                        if not mm:
                            out.append((n, ln, 'НЕТ', 'п. %s ст. %s' % (pt, st), plain))
                        else:
                            targets.append(('п. %s ст. %s' % (pt, st), mm.group(0)))
                else:
                    targets.append(('ст. %s' % st, txt_all))
                sw = stems(plain)
                line_txt += [x[1] for x in targets]
                for name, txt in targets:
                    k = len(sw & stems(txt))
                    lim = 2 if name.startswith('ст.') else 3
                    if 'утратил' in txt[:60] and len(txt) < 120:
                        out.append((n, ln, 'НЕТ', name + ' (утратила силу)', plain))
                    elif k < lim and not ranged and not (name.startswith('ст.') and len(sw) < 7):
                        out.append((n, ln, 'МАЛО', '%s [%d]' % (name, k), plain))
                    elif show_all:
                        out.append((n, ln, 'ок', '%s [%d]' % (name, k), ''))
        if line_txt:
            union = '\n'.join(line_txt)
            for num, unit in sorted(numbers(plain)):
                if not num_in(num, unit, union):
                    out.append((n, ln, 'ЧИСЛО', '%s %s…' % (num, unit), plain))
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    have = sorted(int(os.path.basename(p)[1:4]) for p in glob.glob(os.path.join(HERE, '..', 'upp', 'q*.txt')))
    a, b = (int(args[0]), int(args[1])) if len(args) == 2 else (have[0], have[-1])
    bad = total = 0
    for n in have:
        if a <= n <= b:
            for r in check(n, '--all' in sys.argv):
                if r[2] != 'ок':
                    bad += 1
                print('%3d:%-3d %-4s %-28s %s' % (r[0], r[1], r[2], r[3], r[4][:150]))
    print('замечаний:', bad)
