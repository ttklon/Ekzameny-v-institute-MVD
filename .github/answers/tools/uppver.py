#!/usr/bin/env python3
"""uppver.py [N1 N2] [--all] [--norm] — строгая сверка ответов по уголовно-процессуальному праву с текстом норм.

Ответ режется на утверждения: текст перед ссылкой относится к этой ссылке; строки списка без своей ссылки —
к ссылке строки-заголовка списка или заголовка раздела. Для каждого утверждения берётся текст названных частей
и пунктов (УПК, УК, Конституция — из папки источников) и печатаются слова и числа утверждения, которых в этом
тексте нет:
  !слово  — нет ни в названной норме, ни в остальном тексте тех же статей и норм раздела;
  ~слово  — нет в названной части (пункте), но есть в другой части той же статьи или в норме раздела
            (возможна неверная часть или пункт в ссылке).
Строка «БЕЗ ССЫЛКИ» — утверждение, которое не привязано ни к одной норме (сверяется по указателям srcsent).
Блок «Главное для запоминания» сверяется с текстом самого ответа и названными в блоке нормами.
С ключом --norm под каждым замечанием печатается текст нормы (самые близкие предложения).
Это отбор мест для чтения: вывод об ошибке делается только после чтения нормы.
"""
import sys, os, re, glob, html
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import srctok25 as K
SRC = os.path.join(HERE, '..', '..', '..', 'Уголовно-процессуальное право', '2. Источники', '1. Нормативные правовые акты')
TXT = os.environ.get('UPP_SRC', '/tmp/usrc')          # тексты extract_src.py (для Конституции)

STOP = set('котор также может могут должн после если иных иные этого этом либо только случа числе лицо лица лицу лицом '
           'уголо дела делу делам делом деле насто кодек стать части пункт таких такие такой такого такое этих этой '
           'быть было были будет будут имеет имеют являе явля данно данны свои своих свое своей него нему '
           'других друго другой другие между через перед когда тогда этим всех всем всеми весь всего иной иного иным '
           'иначе далее более менее затем значи означ назыв понят опред закон норма нормы норм прави поряд '
           'основ основа случае прямо важно именн общий общее общая общие общим особе особы отдел тако самим '
           'самом самого сама само кажды каждо каждая любой любое любая любые любых '
           'следу указа назва перечис преду устан учебн литер поэто напри смысл итог главн терми суть приме '
           'вывод говор таким образ считае групп класс делят виды запом обычн типич ключе регул разъя плену '
           'верхо россий федер росс росси'.split())
_acts = {}


def load_html(key):
    """Кодекс из HTML официальной публикации: {номер статьи: {'title', 'lines'}}, порядок статей."""
    if key in _acts:
        return _acts[key]
    pat = {'УПК': 'процессуальный', 'УК': 'Уголовный кодекс'}[key]
    f = [p for p in glob.glob(os.path.join(SRC, '2. Кодексы', '**', '*.html'), recursive=True) if pat in os.path.basename(p)][0]
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
        if cur and not re.match(r'(Глава|ГЛАВА|Раздел|РАЗДЕЛ|ЧАСТЬ)\b', line):
            arts[cur]['lines'].append(line)
    _acts[key] = (arts, order)
    return _acts[key]


def load_const():
    if 'К' in _acts:
        return _acts['К']
    # в папке источников Конституция — скан без текстового слоя; текст распознан и лежит в src-text
    f = os.path.join(HERE, '..', 'src-text', 'Конституция РФ (распознанный текст скана).txt')
    t = open(f, encoding='utf-8').read()
    t = re.sub(r'\n\s*\n', '\n', t)
    t = re.sub(r'[ \t\xa0\r]+', ' ', t)
    arts, order, cur = {}, [], None
    for line in t.split('\n'):
        line = line.strip()
        m = re.match(r'Статья (\d+)\s*$', line)
        if re.match(r'Статья \d+[^\d\s]', line):          # статьи с надстрочным номером (67.1 и др.) отдельно не разбираются
            cur = None
            continue
        if m:
            cur = m.group(1)
            if cur not in arts:
                arts[cur] = {'title': '', 'lines': []}
                order.append(cur)
            continue
        if cur and line and not re.match(r'ГЛАВА|РАЗДЕЛ', line):
            arts[cur]['lines'].append(line)
    _acts['К'] = (arts, order)
    return _acts['К']


def load(act):
    return load_const() if act == 'К' else load_html(act)


def clean(s):
    s = re.sub(r'\^(\d+)\^', r'.\1', s)
    s = re.sub(r'\((?:В редакции|Дополнение|Часть|Наименование|Пункт|Абзац|Статья|Утратил|Утратила|Дополнен|Подпункт)[^)]*'
               r'(?:[Фф]едеральн|Закон)[^)]*\)', '', s)
    return s.strip()


_parts = {}


def parts(act, num):
    """Части статьи: {'1': текст, …}; ключ '' — текст до первой нумерованной части. Строки PDF Конституции склеены."""
    if (act, num) in _parts:
        return _parts[(act, num)]
    arts, _ = load(act)
    res, key = {'': ''}, ''
    for l in arts[num]['lines']:
        l = clean(l)
        m = re.match(r'(\d+(?:\.\d+)?)\. ', l)
        if m and (act != 'К' or len(m.group(1)) < 3):
            key = m.group(1)
            res[key] = ''
        res[key] += l + ('\n' if act != 'К' else ' ')
    _parts[(act, num)] = res
    return res


def art_text(act, num):
    arts, _ = load(act)
    return arts[num]['title'] + '\n' + '\n'.join(parts(act, num).values())


def punkt(txt, pt):
    """Текст пункта «N) …» внутри части (до следующего пункта того же уровня)."""
    m = re.search(r'(?m)^%s\) ' % re.escape(pt), txt)
    if not m:
        m = re.search(r'(?<=[ ;:])%s\) ' % re.escape(pt), txt)      # Конституция из PDF: пункты в одну строку
        if not m:
            return None
    rest = txt[m.end():]
    e = re.search(r'(?m)^\d+(?:\.\d+)?\) ', rest)
    return txt[m.start():m.end() + (e.start() if e else len(rest))]


def items(s):
    res = []
    for bit in re.split(r', | и ', s):
        if '–' in bit:
            a, b = bit.split('–')
            res.append((a.strip(), b.strip()))
        else:
            res.append(bit.strip())
    return res


def expand(it, pool):
    if not isinstance(it, tuple):
        return [it]
    a, b = it
    if a in pool and b in pool:
        return pool[pool.index(a):pool.index(b) + 1]
    if '.' not in a + b and a.isdigit() and b.isdigit():
        return [str(x) for x in range(int(a), int(b) + 1)]
    return [a, b]


NUMS = r'\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*'
REF = re.compile(r'(?:(?:подп|п)\. (?P<pt>%s) )?(?:ч\. (?P<ch>%s) )?ст\. (?P<st>%s)(?=(?P<tail>[^()/]{0,160}))' % (NUMS, NUMS, NUMS))
BARE = re.compile(r'(?:(?:подп|п)\. (?P<pt>%s) ?)?(?:ч\. (?P<ch>%s))?' % (NUMS, NUMS))
CHAP = re.compile(r'гл\. (\d+(?:\.\d+)?)')


SERIES = r'(?:(?:, | и |; )(?:(?:подп|п)\. [\d., и–]+ )?(?:ч\. [\d., и–]+ )?(?:ст\. )?[\d.–]+)*'


def act_of(tail):
    m = re.match(SERIES + r'\s*(УК|Конституци)(?![А-Яа-я]{3})', tail)       # «ст. 116, ч. 1 ст. 128.1, … УК»
    if m:
        return 'УК' if m.group(1) == 'УК' else 'К'
    if re.match(r'\s*(УК|Уголовного кодекса)(?![А-Яа-я])', tail):
        return 'УК'
    if re.match(r'\s*Конституци', tail):
        return 'К'
    if re.match(r'\s*(УИК|Закона|Федерального|ГК|ГПК|КоАП|Пакта|Конвенци|закона|Европейск)', tail):
        return None
    return 'УПК'


def resolve(s, ctx):
    """Ссылки строки s → [(метка, акт, статья, текст нормы)] и список ошибок; ctx — (акт, статья, часть) раздела."""
    out, bad = [], []
    spans = []
    for m in REF.finditer(s):
        spans.append((m.start(), m.end('st')))
        act = act_of(m.group('tail'))
        if act is None:
            continue
        arts, order = load(act)
        # акт взят из конца перечня («ч. 3 ст. 8, ч. 1 ст. 47 Конституции»): если такой статьи, части, пункта в нём нет — это УПК
        if act != 'УПК' and not re.match(r'\s*(УК|Уголовного кодекса|Конституци)', m.group('tail')):
            st0 = items(m.group('st'))[0]
            st0 = st0[0] if isinstance(st0, tuple) else st0
            ok = st0 in arts
            if ok and m.group('ch'):
                c0 = items(m.group('ch'))[0]
                ok = (c0[0] if isinstance(c0, tuple) else c0) in parts(act, st0)
            if ok and m.group('pt'):
                p0 = items(m.group('pt'))[0]
                ok = punkt('\n'.join(parts(act, st0).values()), p0[0] if isinstance(p0, tuple) else p0) is not None
            if not ok:
                act = 'УПК'
                arts, order = load(act)
        sts = []
        for it in items(m.group('st')):
            sts += expand(it, order)
        for k, st in enumerate(sts):
            if st not in arts:
                bad.append('НЕТ ст. %s %s' % (st, act))
                continue
            ps = parts(act, st)
            keys = [x for x in ps if x]
            chs, pts = [], []
            if m.group('ch') and k == 0:
                for it in items(m.group('ch')):
                    chs += expand(it, keys)
            if m.group('pt') and k == 0:
                for it in items(m.group('pt')):
                    pts += expand(it, [])
            name = 'ст. %s%s' % (st, '' if act == 'УПК' else ' ' + act)
            if chs:
                for ch in chs:
                    if ch not in ps:
                        bad.append('НЕТ ч. %s %s' % (ch, name))
                        continue
                    if pts:
                        for pt in pts:
                            x = punkt(ps[ch], pt)
                            if x is None:
                                bad.append('НЕТ п. %s ч. %s %s' % (pt, ch, name))
                            else:
                                head = ps[ch].split('\n')[0] if act != 'К' else ''
                                out.append(('п. %s ч. %s %s' % (pt, ch, name), act, st, head + '\n' + x))
                    else:
                        out.append(('ч. %s %s' % (ch, name), act, st, ps[ch]))
            elif pts:
                whole = '\n'.join(ps.values())
                for pt in pts:
                    x = punkt(whole, pt)
                    if x is None:
                        bad.append('НЕТ п. %s %s' % (pt, name))
                    else:
                        out.append(('п. %s %s' % (pt, name), act, st, x))
            else:
                out.append((name, act, st, art_text(act, st)))
    # голые «(ч. 1)», «(п. 3)» — относительно статьи раздела
    if ctx and ctx[1]:
        rest = s
        for a, b in reversed(spans):
            rest = rest[:a] + ' ' * (b - a) + rest[b:]
        for m in re.finditer(r'\((?:(?:подп|п)\. (?P<pt>%s))?(?: ?ч\. (?P<ch>%s))?\)' % (NUMS, NUMS), rest):
            if not (m.group('pt') or m.group('ch')):
                continue
            act, st, cch = ctx
            ps = parts(act, st)
            keys = [x for x in ps if x]
            chs = []
            if m.group('ch'):
                for it in items(m.group('ch')):
                    chs += expand(it, keys)
            elif cch:
                chs = [cch]
            pts = []
            if m.group('pt'):
                for it in items(m.group('pt')):
                    pts += expand(it, [])
            name = 'ст. %s%s' % (st, '' if act == 'УПК' else ' ' + act)
            for ch in chs or ['*']:
                txt = ps.get(ch) if ch != '*' else '\n'.join(ps.values())
                if txt is None:
                    bad.append('НЕТ ч. %s %s' % (ch, name))
                    continue
                if pts:
                    for pt in pts:
                        x = punkt(txt, pt)
                        if x is None:
                            bad.append('НЕТ п. %s%s %s' % (pt, '' if ch == '*' else ' ч. ' + ch, name))
                        else:
                            out.append(('п. %s%s %s' % (pt, '' if ch == '*' else ' ч. ' + ch, name), act, st, txt.split('\n')[0] + '\n' + x))
                else:
                    out.append(('ч. %s %s' % (ch, name), act, st, txt))
    return out, bad


def first_ctx(s):
    """Статья (и часть, если одна) из ссылки заголовка: контекст для голых «(ч. N)»."""
    m = REF.search(s)
    if not m:
        return None
    act = act_of(m.group('tail'))
    if act is None:
        return None
    arts, order = load(act)
    st = items(m.group('st'))[0]
    if isinstance(st, tuple) or st not in arts or re.search(r'[,и–]', m.group('st')):
        return (act, None, None) if isinstance(st, tuple) or st not in arts else (act, st, None)
    ch = m.group('ch')
    return (act, st, ch if ch and not re.search(r'[,и–]', ch) else None)


def toks(s):
    """[(основа или число, слово как в тексте)] без служебных слов, ссылок, дат и номеров перечисления."""
    s = re.sub(r'\*\*|__', '', s)
    s = re.sub(r'//', ' ', s)
    s = re.sub(r'\((?:(?:подп|п|ч|ст|гл)\. [^)]*)\)', ' ', s)
    s = K.REFNUM.sub(' ', s)
    s = re.sub(r'\d{1,2}\.\d{2}\.\d{4}', ' ', s)
    s = re.sub(r'№ ?\d+(?:-[А-Яа-я]+)?', ' ', s)
    s = re.sub(r'(?<![\d.])\d{1,2}\) ', ' ', s)
    s = re.sub(r'\b(?:19|20)\d\d\s*(?:г\.|год[а-я]*)', ' ', s)
    p = K.prep(s)
    out = []
    for st, pos in K.tokens(s, pos=True):
        if st in STOP:
            continue
        m = re.match(r'[а-яa-z]+|\d+', p[pos:])
        w = m.group() if m else st
        if st.isdigit():
            w = p[pos:pos + 22].split(',')[0].split(';')[0].strip()
        out.append((st, w))
    return out


def tokset(txt):
    return set(K.tokens(txt))


def near(txt, miss_stems, claim_stems, n=2, width=420):
    """Предложения нормы, ближайшие к утверждению."""
    sents = [x.strip() for x in re.split(r'(?<=[.;:])\s+|\n', txt) if len(x.strip()) > 15]
    sc = []
    for i, x in enumerate(sents):
        t = tokset(x)
        sc.append((len(t & claim_stems), -i, x))
    sc.sort(reverse=True)
    return [x[2][:width] for x in sc[:n] if x[0] > 0]


def check(n, show_all=False, norm=False):
    path = os.path.join(HERE, '..', 'upp', 'q%03d.txt' % n)
    lines = open(path, encoding='utf-8').read().split('\n')
    res = []           # (ln, вид, метка, покрытие, [!], [~], текст, [нормы])
    sec_units, sec_ctx = [], None          # нормы заголовка раздела
    lst_units = []                         # нормы строки, после которой идёт список
    body_tok = set()
    stats = {'утв': 0, 'ок': 0}
    for ln, line in enumerate(lines, 1):
        if not line.strip() or line.startswith('# '):
            if not line.strip():
                lst_units = lst_units       # пустая строка не обрывает раздел
            continue
        if line.startswith('!! '):
            continue
        body_tok |= tokset(line)
        kind = 'H' if line.startswith('## ') else 'L' if line.startswith('- ') else 'D' if line.startswith('> ') else 'P'
        text = re.sub(r'^(## |- |> )', '', line)
        if kind == 'H':
            u, bad = resolve(text, None)
            sec_units, sec_ctx, lst_units = u, first_ctx(text), []
            for b in bad:
                res.append((ln, 'НЕТ', b, 0, [], [], text, []))
            continue
        if kind != 'L':
            lst_units = []
        # отрезки: текст перед каждой ссылкой в //…//
        spans = [(m.start(), m.end()) for m in re.finditer(r'//.+?//', text)]
        segs = []
        prev = 0
        for a, b in spans:
            segs.append([text[prev:a], text[a:b]])
            prev = b
        tail = text[prev:]
        if segs:
            if len(toks(tail)) >= 3:
                segs.append([tail, segs[-1][1]])
        else:
            segs.append([text, ''])
        line_units = []
        for claim, ref in segs:
            # ссылки внутри самого утверждения («по ст. 91, 97», «(ст. 61 Конституции)») — тоже нормы
            u1, bad1 = resolve(ref, sec_ctx)
            u2, bad2 = resolve(claim, sec_ctx)
            for b in bad1 + bad2:
                res.append((ln, 'НЕТ', b, 0, [], [], claim.strip()[:200], []))
            own = u1 + u2
            ct = toks(claim)
            if len(ct) < 2:
                line_units += own
                continue
            stats['утв'] += 1
            if not own:
                own = lst_units if (kind == 'L' and lst_units) else sec_units
                via = 'раздел' if own else ''
            else:
                via = ''
            line_units += u1 + u2
            if not own:
                res.append((ln, 'БЕЗ ССЫЛКИ', '', 0, [], [], claim.strip(), []))
                continue
            own_tok = set()
            for x in own:
                own_tok |= tokset(x[3])
            wide_tok = set()
            for x in own + sec_units + lst_units:
                wide_tok |= tokset(art_text(x[1], x[2]))
            miss, soft = [], []
            seen = set()
            for st, w in ct:
                if st in own_tok or st in seen:
                    continue
                seen.add(st)
                (soft if st in wide_tok else miss).append((st, w))
            cov = 1 - (len(miss) + len(soft)) / max(1, len({s for s, _ in ct}))
            label = ', '.join(dict.fromkeys(x[0] for x in own))
            if len(label) > 60:
                label = label[:57] + '…'
            if via:
                label = '[' + label + ']'
            if miss or soft or show_all:
                nt = []
                if norm and (miss or soft):
                    cs = {s for s, _ in ct}
                    for x in own[:4]:
                        for y in near(x[3], None, cs):
                            nt.append('%s: %s' % (x[0], y))
                res.append((ln, 'СВЕРИТЬ' if (miss or soft) else 'ок', label, cov, miss, soft, claim.strip(), nt))
            if not (miss or soft):
                stats['ок'] += 1
        if text.rstrip().endswith(':') and kind != 'L':
            lst_units = line_units or sec_units
    # блок «Главное для запоминания»
    for ln, line in enumerate(lines, 1):
        if not line.startswith('!! '):
            continue
        text = re.sub(r'^!! \*\*Главное для запоминания\.\*\* ?', '', line)
        for sent in K.sentences(text):
            u, bad = resolve(sent, None)
            for b in bad:
                res.append((ln, 'НЕТ', b, 0, [], [], sent[:200], []))
            ok_tok = set(body_tok)
            for x in u:
                ok_tok |= tokset(x[3])
            miss = []
            seen = set()
            for st, w in toks(sent):
                if st not in ok_tok and st not in seen:
                    seen.add(st)
                    miss.append((st, w))
            stats['утв'] += 1
            if miss:
                res.append((ln, 'БЛОК', ', '.join(dict.fromkeys(x[0] for x in u))[:60], 0, miss, [], sent, []))
            else:
                stats['ок'] += 1
    return res, stats


def marked(text, miss, soft):
    """Текст утверждения, в котором слова без опоры помечены: «!слово» и «~слово»."""
    ms = {s for s, _ in miss}
    ss = {s for s, _ in soft}
    nums_m = {s for s in ms if s.isdigit()}
    nums_s = {s for s in ss if s.isdigit()}
    s = re.sub(r'\*\*|__', '', text)
    s = re.sub(r'//', '', s).strip(' .;')

    def rep(m):
        w = m.group()
        if w[0].isdigit():
            return ('!' if w in nums_m else '~' if w in nums_s else '') + w
        st = K.stem(w.lower().replace('ё', 'е'))
        if len(w) < 4:
            return w
        return ('!' if st in ms else '~' if st in ss else '') + w
    out = re.sub(r'[А-Яа-яЁё]+|\d+', rep, s)
    # числа словами («двух», «трёх») распознаются как числа: пометить отдельно, если не нашлись
    left = [w for st, w in miss + soft if st.isdigit() and ('!' + st) not in out and ('~' + st) not in out]
    return out + (' {число: %s}' % '; '.join(left) if left else '')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    have = sorted(int(os.path.basename(p)[1:4]) for p in glob.glob(os.path.join(HERE, '..', 'upp', 'q*.txt')))
    a, b = (int(args[0]), int(args[1])) if len(args) == 2 else (int(args[0]), int(args[0])) if len(args) == 1 else (have[0], have[-1])
    tot = {'утв': 0, 'ок': 0}
    width = 230
    for x in sys.argv:
        if x.startswith('--w='):
            width = int(x[4:])
    for n in have:
        if not a <= n <= b:
            continue
        res, st = check(n, '--all' in sys.argv, '--norm' in sys.argv)
        for k in tot:
            tot[k] += st[k]
        print('=== %d: утверждений %d, без замечаний %d' % (n, st['утв'], st['ок']))
        for ln, kind, label, cov, miss, soft, text, nt in res:
            if kind == 'ок':
                continue
            if kind == 'СВЕРИТЬ':
                print('%d:%d %s | %s' % (n, ln, label, marked(text, miss, soft)[:width]))
            elif kind == 'БЛОК':
                print('%d:%d БЛОК | %s' % (n, ln, marked(text, miss, soft)[:width]))
            elif kind == 'НЕТ':
                print('%d:%d %s | %s' % (n, ln, label, text[:width]))
            elif '--noref' not in sys.argv:
                print('%d:%d БЕЗ ССЫЛКИ | %s' % (n, ln, text[:width]))
            for x in nt:
                print('      ▸ ' + x)
    print('всего утверждений %d, без замечаний %d' % (tot['утв'], tot['ок']))
