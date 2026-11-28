#!/usr/bin/env python3
"""summary.py КОД_ИЛИ_ПАПКА [-v]

Числа в блоке «Главное для запоминания» против текста того же ответа.
Для каждого ответа берёт строку «Главное для запоминания», выписывает из неё числа (цифрами и словами:
«60 дней», «трёх часов», «1 500 000 рублей») и печатает те, которых в остальном тексте ответа нет ни цифрами,
ни словами. Номера статей, частей, пунктов и годы не учитываются. Пометка — повод прочитать строку,
а не готовая ошибка: число могло быть записано в теле ответа иначе («полтора года» и «18 месяцев»).
  -v   печатать и ответы без расхождений (одной строкой).
  -s   под пометкой печатать предложения блока, в которых стоит такое число.
"""
import re, sys, os, glob

U = {'один': 1, 'одн': 1, 'дв': 2, 'три': 3, 'тре': 3, 'четыр': 4, 'пят': 5, 'шест': 6, 'сем': 7, 'восьм': 8, 'восем': 8,
     'девят': 9, 'десят': 10, 'одиннадцат': 11, 'двенадцат': 12, 'тринадцат': 13, 'четырнадцат': 14, 'пятнадцат': 15,
     'шестнадцат': 16, 'семнадцат': 17, 'восемнадцат': 18, 'девятнадцат': 19, 'двадцат': 20, 'тридцат': 30, 'сорок': 40,
     'сорока': 40, 'пятидесят': 50, 'пятьдесят': 50, 'шестидесят': 60, 'шестьдесят': 60, 'семидесят': 70, 'семьдесят': 70,
     'восьмидесят': 80, 'восемьдесят': 80, 'девяност': 90, 'сто': 100, 'ста': 100, 'двухсот': 200, 'двести': 200,
     'трехсот': 300, 'триста': 300, 'четырехсот': 400, 'четыреста': 400, 'пятисот': 500, 'пятьсот': 500, 'шестисот': 600,
     'шестьсот': 600, 'семисот': 700, 'семьсот': 700, 'восьмисот': 800, 'восемьсот': 800, 'девятисот': 900, 'девятьсот': 900}
LONG = sorted((k for k in U if len(k) > 4), key=len, reverse=True)
SHORT = {r'дв(а|е|ух|ум|умя)': 2, r'одн(а|ой|у|ого|ому|им|ом)|один': 1, r'пят(ь|и|ью)': 5, r'шест(ь|и|ью)': 6,
         r'тр(ех|ем|и|емя)': 3, r'сем(ь|и|ью)': 7, r'сто|ста': 100, r'сорок|сорока': 40, r'восьми|восемь': 8,
         r'четыр(е|ех|ем)': 4, r'девят(ь|и)': 9, r'десят(ь|и|ью)': 10}

def tok(w):
    w = w.lower().replace('ё', 'е')
    if w.startswith('тысяч'): return 'K'
    if w.startswith('миллион'): return 'M'
    for rx, v in SHORT.items():
        if re.fullmatch(rx, w): return v
    for k in LONG:
        if w.startswith(k) and len(w) - len(k) <= 3: return U[k]
    return None

CMP = {'одно': 1, 'двух': 2, 'трех': 3, 'четырех': 4, 'пяти': 5, 'шести': 6, 'семи': 7, 'восьми': 8, 'девяти': 9,
       'десяти': 10, 'двенадцати': 12, 'четырнадцати': 14, 'пятнадцати': 15, 'двадцати': 20, 'тридцати': 30}
CMP_RE = re.compile(r'\b(' + '|'.join(sorted(CMP, key=len, reverse=True)) +
                    r')(?=дневн|месячн|кратн|суточн|недельн|летн|часов|годичн)', re.I)

def wnums(t):
    # «десятидневный», «трёхкратного», «двухмесячный» считаются как 10, 3, 2
    t = t.replace('ё', 'е').replace('Ё', 'Е')
    comp = {CMP[m.group(1).lower()] for m in CMP_RE.finditer(t)}
    t = CMP_RE.sub(' ', t)
    out, cur, tot, act = set(), 0, 0, False
    for w in re.findall(r'[А-Яа-яёЁ]+|[^\sА-Яа-яёЁ]+', t):
        v = tok(w) if re.match(r'[А-Яа-яёЁ]', w) else None
        if v is None:
            if act: out.add(tot + cur)
            cur = tot = 0; act = False
            continue
        act = True
        if v == 'K': tot += (cur or 1) * 1000; cur = 0
        elif v == 'M': tot += (cur or 1) * 1000000; cur = 0
        else: cur += v
    if act: out.add(tot + cur)
    return {float(x) for x in out | comp}

REF = re.compile(r'(?:\b(?:ч|п|пп|ст|гл|подп|чч)\.|№|стать[яиюейх]+|част[ьияюейх]+|пункт[аеуыовмих]*|глав[аыеуой]+|подпункт[аеуыовмих]*|класс[аовемих]*|подкласс[аовемих]*)[  ]?[\d.,  и–-]+(?:\.\d+)*', re.I)
def dnums(s):
    s = re.sub(r'//.*?//', ' ', s)
    s = REF.sub(' ', s)
    s = re.sub(r'\d{1,2}\.\d{1,2}\.\d{4}|\b(?:19|20)\d\d\b(?:[  ]?(?:год\w*|г\.))?', ' ', s)
    out = set()
    for m in re.finditer(r'(?<![\d.,])(\d{1,3}(?:[  ]\d{3})+|\d+)(?![\d]|[.,]\d)([  ]?(?:млн|тыс))?', s):
        v = float(re.sub(r'[  ]', '', m.group(1)))
        if m.group(2): v *= 1000000 if 'млн' in m.group(2) else 1000
        out.add(v)
    return out

def nums(s): return dnums(s) | {x for x in wnums(REF.sub(' ', re.sub(r'//.*?//', ' ', s))) if x >= 2}

def answers(path):
    """(метка, текст) для каждого ответа в файле; в сборных файлах АДП ответы начинаются с «# Вопрос N»."""
    t = open(path, encoding='utf-8').read()
    parts = re.split(r'(?m)^(?=# Вопрос \d+)', t)
    for p in parts:
        m = re.match(r'# Вопрос (\d+)', p)
        if p.strip(): yield (m.group(1) if m else '—'), p

if __name__ == '__main__':
    arg = [a for a in sys.argv[1:] if not a.startswith('-')][0]
    base = arg if os.path.isdir(arg) else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', arg)
    tot = bad = 0
    for f in sorted(glob.glob(os.path.join(base, 'q*.txt'))):
        for lab, txt in answers(f):
            ls = txt.split('\n')
            idx = [i for i, l in enumerate(ls) if 'Главное для запоминания' in l]
            if not idx: continue
            for i in idx:
                tot += 1
                # блок «Главное» — строка и её продолжение до пустой строки
                j = i
                while j + 1 < len(ls) and ls[j + 1].strip() and not ls[j + 1].startswith('#'): j += 1
                summ = '\n'.join(ls[i:j + 1]); body = '\n'.join(ls[:i] + ls[j + 1:])
                have = dnums(body) | wnums(body)
                miss = sorted(x for x in nums(summ) if x not in have and x >= 2)
                name = '%s:%d (вопрос %s)' % (os.path.basename(f)[:-4], i + 1, lab)
                if miss:
                    bad += 1
                    print(name, [int(x) if x == int(x) else x for x in miss])
                    if '-s' in sys.argv:
                        for s in re.split(r'(?<=[.;])\s+', summ):
                            if nums(s) & set(miss): print('      ', s.strip()[:300])
                elif '-v' in sys.argv: print(name, 'ок')
    print('-- блоков «Главное для запоминания»: %d, с числами, которых нет в тексте ответа: %d' % (tot, bad))
