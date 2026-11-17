#!/tmp/venv/bin/python
"""Сборка варианта 2 из варианта 1: сокращение + дословные цитаты норм, сверенные с текстами актов.
mk2.py            — собрать все (кроме вручную написанных) в .github/answers/adp2/qNNN.txt
mk2.py N [show]   — собрать один вопрос (show — напечатать)"""
import re, glob, os, sys
ROOT = '/home/user/Ekzameny-v-institute-MVD/.github/answers'
MANUAL = {2, 40, 52, 62, 88}
man_file = ROOT + '/adp2/MANUAL.txt'
if os.path.exists(man_file):
    MANUAL |= {int(x) for x in open(man_file).read().split()}
DROP = re.compile(r'пример|типичн\w+ ошибк|самопровер|сводка|как запомнить|памятк', re.I)

def load_v1():
    Q = {}
    for f in sorted(glob.glob(ROOT + '/adp/*.txt')):
        s = open(f, encoding='utf-8').read()
        for m in re.finditer(r'(?ms)^# Вопрос (\d+)\. (.*?)\n(.*?)(?=^# Вопрос \d+\. |\Z)', s):
            Q[int(m.group(1))] = (m.group(2).strip().rstrip('.'), m.group(3))
    return Q

# ---------- корпус актов
FILES = sorted(glob.glob('/tmp/txt/1/*.txt')) + sorted(f for f in glob.glob('/tmp/txt/2/*.txt') if 'Пленума' in f)
_cache = {}
def norm_words(t):
    t = t.lower().replace('ё', 'е')
    return re.findall(r'[0-9a-zа-я]+', t)
def corpus(f):
    if f not in _cache:
        t = open(f, encoding='utf-8').read()
        t = re.sub(r'\[\[стр\. \d+\]\]', ' ', t)
        t = re.sub(r'Стр\. \d+ из \d+', ' ', t)
        t = re.sub(r'\((В редакции|Дополнение|Утратил|в ред\.|введен|п\. \d+ введен)[^)]{0,300}\)', ' ', t)
        t = re.sub(r'\(см\. текст в предыдущей редакции\)', ' ', t)
        t = re.sub(r'<\d+>', ' ', t)
        _cache[f] = ' ' + ' '.join(norm_words(t)) + ' '
    return _cache[f]
def files_for(text):
    nums = set(re.findall(r'№\s?([0-9][0-9А-Яа-яён\-/]*)', text))
    out = []
    for f in FILES:
        b = os.path.basename(f)
        if 'О полиции' in b or 'КоАП РФ от' in b:
            out.append(f); continue
        if ('УК РФ' in text or 'Уголовн' in text) and b.startswith('Уголовный кодекс'): out.append(f); continue
        if 'КАС' in text and b.startswith('КАС РФ'): out.append(f); continue
        if ('УПК' in text or 'Уголовно-процессуальн' in text) and b.startswith('Уголовно-процессуальный'): out.append(f); continue
        if 'Концепци' in text and b.startswith('Концепция'): out.append(f); continue
        for n in re.findall(r'(?:№|N|МВД|Минздрава|_)[ _]?([0-9][0-9А-Яа-яён\-/]*)', b):
            if n in nums:
                out.append(f); break
    return out

# ---------- цитаты
EDGE = set('и в во на с со к ко по или а о об от для при за из не что если либо также но у до то же их его ее'.split())
TOK = re.compile(r'[0-9A-Za-zА-Яа-яЁё]+')
def quote_line(line, corp):
    if '«' in line and line.count('«') != line.count('»'):
        return line.replace(FORCE, ''), 0
    forced = []
    while FORCE in line:
        a = line.index(FORCE); b = line.index(FORCE, a + 1)
        line = line[:a] + line[a + 1:b] + line[b + 1:]
        forced.append((a, b - 1))
    def isf(k): return any(x <= k < y for x, y in forced)
    toks = [(m.start(), m.end(), m.group(0).lower().replace('ё', 'е')) for m in TOK.finditer(line)]
    n = len(toks)
    # запретные зоны: ссылки //…//, готовые кавычки
    bad = [False] * len(line)
    for m in re.finditer(r'//.*?//|«[^»]*»|\*\*.*?\*\*', line):
        for k in range(m.start(), m.end()): bad[k] = True
    spans = []
    i = 0
    while i < n:
        if bad[toks[i][0]]:
            i += 1; continue
        j = i; best = 0
        probe = ' ' + toks[i][2]
        ok_any = [c for c in corp if probe + ' ' in c]
        if not ok_any:
            i += 1; continue
        s = probe
        cur = ok_any
        while j + 1 < n and not bad[toks[j + 1][0]]:
            s2 = s + ' ' + toks[j + 1][2]
            cur2 = [c for c in cur if s2 + ' ' in c]
            if not cur2: break
            s, cur, j = s2, cur2, j + 1
        while j > i and toks[j][2] in EDGE and not isf(toks[j][0]): j -= 1
        while i < j and toks[i][2] in EDGE and not isf(toks[i][0]): i += 1
        L = j - i + 1
        seg0 = line[toks[i][0]:toks[j][1]]
        if seg0.count('(') != seg0.count(')'):
            i += 1; continue
        if L >= 8 or any(isf(toks[x][0]) for x in range(i, j + 1)) and L >= 3:
            spans.append((i, j)); i = j + 1
        else:
            i += 1
    if not spans:
        return line, 0
    out = line; cnt = 0
    for i, j in reversed(spans):
        a, b = toks[i][0], toks[j][1]
        seg = out[a:b]
        # не рвать пары ** внутри цитаты
        if seg.count('**') % 2:
            k = seg.find('**') if seg.count('**') == 1 else None
            if k is None: continue
            left, right = seg[:k], seg[k + 2:]
            if len(TOK.findall(right)) >= 7: a = a + k + 2; seg = right
            elif len(TOK.findall(left)) >= 7: b = a + k; seg = left
            else: continue
        # не начинать/кончать цитату предлогом-обрывком
        out = out[:a] + '«' + seg + '»' + out[b:]
        cnt += 1
    return out, cnt

def prep_line(ln, corp):
    m = re.match(r'((?:- |  - |> )?\*\*[^*]+\*\*)(.*)$', ln, flags=re.S)
    head, rest = (m.group(1), m.group(2)) if m else ('', ln)
    rest = rest.replace('**', '')
    ln = head + rest
    # кавычки вокруг дословных фрагментов снимаются: их расставит сверка заново
    zones = [(z.start(), z.end()) for z in re.finditer(r'//.*?//', ln)]
    def inz(k): return any(a <= k < b for a, b in zones)
    out = []; pos = 0
    for q in re.finditer(r'«([^«»]*)»', ln):
        if inz(q.start()): continue
        w = norm_words(q.group(1))
        if len(w) >= 3 and any(' ' + ' '.join(w) + ' ' in c for c in corp):
            out.append(ln[pos:q.start()] + FORCE + q.group(1) + FORCE); pos = q.end()
    out.append(ln[pos:])
    return ''.join(out)

FORCE = '\u2063'

# ---------- чистка текста
def clean_study(t):
    R = [
        (r'Законного определения нет; это определение учебное\.', 'Законного определения нет.'),
        (r'Закон определения не содержит; оно принято в учебной литературе\.', 'Закон определения не содержит.'),
        (r'(?:Это о|О)пределение учебное; в законе такого термина нет\.', 'В законе такого термина нет.'),
        (r'Определение учебное; оно (построено|составлено)', r'Определение \1'),
        (r'Определение учебное; ', ''),
        (r'(?:Это о|О)пределение учебное\.\s?', ''),
        (r'(?:Деление учебное|Признаки учебные|Порядок учебный)\.\s?', ''),
        (r' \(понятие учебное\)', ''), (r' \(в учебной литературе\)', ''),
        (r'Как и общий надзор, это понятие учебной литературы\.\s?', ''),
        (r'Это понятие учебной литературы: им', 'Им'),
        (r'; приведённое определение[^.]*учебн[^.]*\.', '.'),
        (r'Закон не даёт раздельных определений, поэтому используются определения учебной литературы\.', 'Закон не даёт раздельных определений.'),
        (r'Поэтому используется определение учебной литературы\.\s?', ''),
        (r'; определение доктринальное\.', '.'),
    ]
    for a, b in R:
        t = re.sub(a, b, t)
    def cap(m): return m.group(1) + m.group(2).upper()
    U = r'учебн(?:ое|ая|ый|ые|ой|ую|ых|ым)'
    LIT = r'учебн(?:ой|ая|ую) литератур[аыеу]'
    R2 = [
        (r' \((?:[а-яё]+ )?(?:— )?(?:по|в|из) ' + LIT + r'\)', ''),
        (r' \((?:названия условные, )?по ' + LIT + r'\)', ''),
        (r' \(' + U + r' [а-яё]+\)', ''), (r' \([а-яё]+ ' + U + r'\)', ''),
        (r' \(([^()]*?)(?:;|,| и| —) (?:по|в) ' + LIT + r'\)', r' (\1)'),
        (r' \((?:по|в) ' + LIT + r'(?: и|;|,) ([^()]*?)\)', r' (по \1)'),
        (r' \(([^()]*?); (?:[а-яё]+ ' + U + r'|' + U + r' [а-яё]+)\)', r' (\1)'),
        (r' \((?:[а-яё]+ ' + U + r'|' + U + r' [а-яё]+)[;,:] ([^()]*?)\)', r' (\1)'),
        (r'(?m)^(?:Определени[ея]|Формулировка|Понятие) учебн(?:ое|ые|ая)[:;] (\w)', lambda m: m.group(1).upper()),
        (r'(?m)^[А-ЯЁ][а-яё]+(?: [а-яё]+)? (?:ниже )?(?:— )?' + U + r'\.\n', ''),
        (r'(?<=[.:] )[А-ЯЁ][а-яё]+(?: [а-яё]+)? ' + U + r'\. ?', ''),
        (r'[А-ЯЁ][а-яё]+ ' + U + r'; (?:он|она|оно|они) ', lambda m: m.group(0).split()[0] + ' '),
        (r'(?m)^(?:По|В) ' + LIT + r'(?: и практике)? (\w)', lambda m: m.group(1).upper()),
        (r'(?m)^- В ' + LIT + r' отмечается: (\w)', lambda m: '- ' + m.group(1).upper()),
        (r'(?m)^- В ' + LIT + r' (\w)', lambda m: '- ' + m.group(1).upper()),
        (r', выделяемые в ' + LIT, ''), (r', выделяемые в науке', ''),
        (r' в ' + LIT + r'(?=[:.])', ''),
    ]
    for a_, b_ in R2:
        t = re.sub(a_, b_, t)
    t = re.sub(r'[;,] в учебной литературе принято следующее понимание:', '; принято следующее понимание:', t)
    t = re.sub(r'(^|[.:*] |\n)В учебной литературе (\w)', cap, t)
    t = re.sub(r'(^|[.:*] |\n)В теории: (\w)', cap, t)
    t = re.sub(r'\bв учебной литературе ', '', t)
    return t

sys.path.insert(0, '/tmp/w')
from sent import split_sents
U_ = r'учебн(?:ое|ая|ый|ые|ой|ую|ых|ым)'
LIT_ = r'учебн(?:ой|ая|ую|ые) литератур[аыеу]'
MARK = re.compile(r'учебн(?!о-|ых коллектив|ое время|ый год|ых вводн|ой и эксперт|ых заведени)|на экзамене|экзаменатор|в базе источников|В ответе (?:целесообразно|достаточно)|в ответе они не цитируются|в ответе ссылок нет|твет на вопрос (?:всегда )?строится|пометку для служебного пользования|об источнике\.|ссылки даны осторожно|по этой копии|неофициальная неполная копия|изложены по открытым актам|о них — ниже|без номеров пунктов|В закрытом Наставлении|\(не опубликован\)|доктринальный;')
def up1(m): return m.group(1).upper()
SREP = [
    (r'[(]называются (федеральные целевые программы и Стратегия безопасности дорожного движения); в ответе они не цитируются[)]', r'(\1)'),
    (r'[(]неофициальная неполная копия; далее', '(далее'),
    (r' [(]в базе источников есть только карточка приказа, текста нет; пункты не приводятся[)]', ''),
    (r' — в базе источников есть только сведения о нём, без текста', ''),
    (r'; имеет пометку для служебного пользования, не опубликован', ''),
    (r' [(]не опубликован[)]', ''),
    (r'доктринальный;', 'научный;'),
    (r'^(?:Определени[ея]|Формулировка|Понятие) учебн(?:ое|ые|ая)[:;] (\w)', up1),
    (r'^Определение учебное, составлено', 'Определение составлено'),
    (r'[;,] (?:поэтому )?формулировка учебная, (составлена|построена)', r'. Формулировка \1'),
    (r'[;,] (?:поэтому )?формулировка учебная\.', '.'),
    (r'; формулировка учебная, построена на тексте статьи', ''),
    (r'— учебный([:.])', r'— собирательный\1'),
    (r' \(' + U_ + r'\)', ''),
    (r'; определение учебное, в законе его нет\)', '; в законе определения нет)'),
    (r' \(правило о приоритете специальной нормы — учебное\)', ''),
    (r'; названия приведены по ' + LIT_, ''), (r' — названия по ' + LIT_, ''),
    (r'\(по ' + LIT_ + r' — ', '('), (r'; по ' + LIT_ + r' — также', '; также'),
    (r' и ' + LIT_ + r'(?=[).])', ''), (r'состав — по ' + LIT_ + r'; ', ''),
    (r'; (?:состав|их перечень здесь) приводится по ' + LIT_, ''),
    (r'^По ' + LIT_ + r' и практике на него', 'На него'), (r'^По ' + LIT_ + r' это', 'Это'),
    (r'^(\(?)В ' + LIT_ + r' («?)(\w)', lambda m: m.group(1) + m.group(2) + m.group(3).upper()),
    (r'в теории её называют', 'её называют'),
    (r'[(]В ' + LIT_ + r' (\w)', lambda m: '(' + m.group(1).upper()),
    (r' (?:\*\*)?по ' + LIT_ + r'(?:\*\*)?,', ''),
    (r' и излагаются по ' + LIT_, ''),
    (r'^Эта классификация учебная; в', 'В'), (r'; перечень дан как учебный', ''),
    (r'^([А-ЯЁ][а-яё]+) ' + U_ + r'; (?:он|она|оно|они) ', r'\1 '),
    (r'^([А-ЯЁ][а-яё]+) ' + U_ + r':', r'\1:'),
    (r'^Группы ниже — учебное деление по задачам:', 'Группы по задачам:'),
    (r' \((?:[а-яё]+ )?(?:— )?(?:по|в|из) ' + LIT_ + r'\)', ''),
]
def clean_line(ln):
    if not MARK.search(ln): return ln
    m = re.match(r'(- |  - |> |!! |## (?:\d+\. )?)', ln)
    pre = m.group(1) if m else ''
    out = []
    for s in split_sents(ln[len(pre):]):
        if MARK.search(s):
            tail = s[len(s.rstrip()):]; s2 = s.rstrip()
            for a_, b_ in SREP: s2 = re.sub(a_, b_, s2)
            if MARK.search(s2):
                if '//' in s2 or len(s2.split()) > 30: RESID.append(s2)
                else: continue
            s = s2 + tail
        out.append(s)
    r = ''.join(out).rstrip()
    return (pre + r) if r else ''
RESID = []

def build(n, title, body, show=False):
    body = clean_study(body)
    parts = re.split(r'(?m)^(?=## )', body)
    pre = parts[0] if not parts[0].startswith('## ') else ''
    secs = [p for p in parts if p.startswith('## ')]
    keep = []
    for s in secs:
        h = s.split('\n', 1)[0]
        if DROP.search(h): continue
        keep.append(s)
    text_all = title + '\n' + body
    corp = [corpus(f) for f in files_for(text_all)]
    out = ['# Вопрос %d. %s' % (n, title), '']
    k = 0; nq = 0
    blocks = ([pre] if pre.strip() else []) + keep
    for s in blocks:
        lines = s.rstrip().split('\n')
        if lines[0].startswith('## '):
            k += 1
            h = re.sub(r'^## (\d+\.\s*)?', '', clean_line(lines[0]))
            out.append('## %d. %s' % (k, h)); lines = lines[1:]
        for ln in lines:
            if re.match(r'\*\*Пример[^*]*\*\*', ln) or re.match(r'- \*\*Пример', ln):
                continue
            if not ln.strip():
                out.append(ln); continue
            if ln.startswith('!! '):
                out.append(clean_line(ln.replace('__', ''))); continue
            ln0 = ln; ln = clean_line(ln)
            if ln0.strip() and not ln.strip(): continue
            ln = prep_line(ln.replace('__', ''), corp)
            q, c = quote_line(ln, corp); nq += c
            out.append(q)
        out.append('')
    txt = re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).rstrip() + '\n'
    return txt, nq

if __name__ == '__main__':
    Q = load_v1()
    args = sys.argv[1:]
    if args:
        n = int(args[0]); t, c = build(n, *Q[n])
        print('цитат', c, 'слов', len(t.split()), 'было', len(Q[n][1].split()))
        if len(args) > 1: print(t)
    else:
        os.makedirs('/tmp/auto', exist_ok=True)
        tot1 = tot2 = totq = 0
        for n in sorted(Q):
            if n in MANUAL: continue
            t, c = build(n, *Q[n])
            open('/tmp/auto/q%03d.txt' % n, 'w', encoding='utf-8').write(t)
            w1, w2 = len(Q[n][1].split()), len(t.split()); tot1 += w1; tot2 += w2; totq += c
            print(n, w1, w2, round(w1 / w2, 2), c)
        print('ИТОГО', tot1, tot2, round(tot1 / tot2, 2), 'цитат', totq)
        print('RESID', len(RESID))
        for r in RESID: print('  ', r[:300])
