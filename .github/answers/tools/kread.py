#!/usr/bin/env python3
"""kread.py ПРЕДМЕТ ПАПКА N [-l A-B] [-c ЗНАКОВ] — сплошное чтение ответа: каждая непустая строка и под ней источник.

ПРЕДМЕТ — tp (трудовое право, кодекс по умолчанию — Трудовой) или gpp (гражданское процессуальное право, по умолчанию
ГПК). ПАПКА — тексты источников из tools/kextract.py (с файлом _index.tsv). Ничего не отбирает: печатает все строки.

Под строкой:
  «·» — текст каждой нормы, названной в скобках (курсивных //(...)// и обычных): названная часть или пункт целиком,
        если не длиннее ЗНАКОВ (по умолчанию 320), иначе те предложения нормы, где больше всего слов строки («…» —
        пропуск). Части Трудового кодекса не нумерованы — считаются по абзацам статьи; номер части печатается.
        Ссылка без названия акта относится к кодексу по умолчанию; «того же …», «Закона», «постановления № N» —
        к акту, полностью названному в этом ответе раньше (помета «?», если акт подобран по догадке).
  «≈» — для строки без нормы (и для слов, приписанных пособию): самое близкое место во всех источниках папки,
        доля слов строки, найденных в этом месте, код файла, страница.
  «↑» — этот кусок нормы уже напечатан выше в том же ответе. «[нет …]» — статьи, части, пункта не нашлось;
  «[акт?]» — акт не опознан, его текст надо открыть вручную.
    python3 tools/kread.py tp /tmp/lsrc 64 -l 1-40
"""
import glob, os, pickle, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]; CAP = 320; LR = None
if '-c' in argv: i = argv.index('-c'); CAP = int(argv[i + 1]); del argv[i:i + 2]
if '-l' in argv: i = argv.index('-l'); a, b = argv[i + 1].split('-'); LR = (int(a), int(b)); del argv[i:i + 2]
SUBJ, SRC, N = argv[0], argv[1], int(argv[2])
ANS = os.path.join(HERE, '..', SUBJ, 'q%03d.txt' % N)
MAIN = {'tp': 'ТК', 'gpp': 'ГПК'}[SUBJ]

# ---------- источники
IDX = {}
for l in open(os.path.join(SRC, '_index.tsv'), encoding='utf-8'):
    f = l.rstrip('\n').split('\t')[0]
    IDX[f[:6]] = f[7:]
_raw = {}


def raw(c):
    if c not in _raw:
        if c == 'CONST':
            t = open(os.path.join(HERE, '..', 'src-text', 'Конституция РФ (распознанный текст скана).txt'), encoding='utf-8').read()
        else:
            t = open(glob.glob(os.path.join(SRC, c + '*'))[0], encoding='utf-8', errors='replace').read()
        t = t.replace('\xa0', ' ').replace('\u00ad', '')
        t = re.sub(r'\n@@ \d+ \|[^\n]*\nСтр\. \d+ из \d+\n', '\n', t)
        _raw[c] = t
    return _raw[c]


def by_name(*subs):
    for c, n in IDX.items():
        if all(s in n for s in subs):
            return c
    return None


KOD = {'ТК': by_name('Трудовой кодекс'), 'ГПК': by_name('Гражданский процессуальный кодекс'),
       'КоАП': by_name('административных правонарушениях'), 'СК': by_name('Семейный кодекс'),
       'АПК': by_name('Арбитражный процессуальный'), 'КАС': by_name('административного судопроизводства'),
       'К': 'CONST'}
GK = [(453, by_name('Гражданский кодекс', 'часть первая')), (1109, by_name('Гражданский кодекс', 'часть вторая')),
      (1224, by_name('Гражданский кодекс', 'часть третья')), (9999, by_name('Гражданский кодекс', 'часть четвёртая'))]
NAMED = [(r'Конституци', 'К'), (r'Гражданск\w+ процессуальн\w+ кодекс|ГПК', 'ГПК'), (r'Трудов\w+ кодекс', 'ТК'),
         (r'Гражданск\w+ кодекс|ГК РФ', 'ГК'), (r'Семейн\w+ кодекс', 'СК'), (r'Арбитражн\w+ процессуальн', 'АПК'),
         (r'административного судопроизводства', 'КАС'), (r'административных правонарушениях', 'КоАП'),
         (r'о нотариате', by_name('о нотариате')), (r'защите прав потребителей', by_name('защите прав потребителей')),
         (r'адвокатской деятельности', by_name('адвокатской деятельности')), (r'арбитраже \(третейском', by_name('Об арбитраже')),
         (r'Дисциплинарн\w+ устав', by_name('Дисциплинарный устав'))]
MON = dict(zip('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split(), range(1, 13)))


def by_number(text):
    """Код файла по «от 17 марта 2004 года № 2» или «№ 342-ФЗ» в тексте ссылки."""
    m = re.search(r'№ ?([\dА-Яа-я./-]+\d[\dА-Яа-ян/-]*|\d+)', text)
    if not m:
        return None
    num = m.group(1).rstrip('.,')
    d = re.search(r'от (\d{1,2}) ([а-я]+) (\d{4})', text)
    date = '%02d.%02d.%s' % (int(d.group(1)), MON.get(d.group(2), 0), d.group(3)) if d else None
    d2 = re.search(r'от (\d\d\.\d\d\.\d{4})', text)
    if d2: date = d2.group(1)
    cand = [c for c, n in IDX.items() if re.search(r'№ ?%s(?![\dА-Яа-я-])' % re.escape(num), n)]
    if date:
        c2 = [c for c in cand if date in IDX[c]]
        if c2: return c2[0]
        if len(cand) > 1: return None
    pl = [c for c in cand if 'Пленум' in IDX[c]] if re.search(r'Пленум', text) else cand
    return (pl or cand or [None])[0]


def toks(s):
    return set(w[:5] for w in re.findall(r'[а-яё]{4,}', s.lower().replace('ё', 'е')))


def window(text, lt, cap):
    text = re.sub(r'\s*\n\s*', ' ¶ ', text.strip())
    if len(text) <= cap:
        return text
    units = [u for u in re.split(r'(?<=[.;:]) (?=[А-ЯЁа-яё\d¶(«])', text) if u.strip()]
    sc = sorted(((len(toks(u) & lt), -k) for k, u in enumerate(units)), reverse=True)
    take, size = set(), 0
    for s, k in sc:
        k = -k
        if s == 0 and take: break
        if size + len(units[k]) > cap and take: continue
        take.add(k); size += len(units[k])
        if size >= cap: break
    out, prev = [], -1
    for k in sorted(take):
        u = units[k] if len(units[k]) <= cap + 250 else units[k][:cap + 250] + '…'
        out.append(('' if k == prev + 1 else '… ') + u); prev = k
    return ' '.join(out) + (' …' if prev < len(units) - 1 else '')


NOTE = re.compile(r'\(\s*(?:В\s+редакции|Дополнение|Наименование|Статья\s+в\s+редакции|Часть|Пункт|Абзац|Подпункт|Предложение|Положения|О\s+несоответствии)[^)]*\)')
_art = {}
_hix = {}


def heads(code):
    """Номер статьи → самый длинный её текст. Надстрочные номера в текстах слиты с основным («Статья 3601.» — это 360.1):
    заголовки читаются по порядку, и «31» после статьи 3 — это 3.1, а после статьи 30 — 31."""
    if code in _hix: return _hix[code]
    r = raw(code); H = {}
    if code == 'CONST':
        ms = list(re.finditer(r'(?m)^Статья (\d+)(\.\d+)?\*?[ \t]*$', r))
        keys = [m.group(1) + (m.group(2) or '') for m in ms]
    else:
        ms = list(re.finditer(r'(?m)^[ \t]*Статья (\d+(?:\.\d+)*)\. ?[^\n]*$', r))
        keys, cur = [], 0
        for m in ms:
            s = m.group(1)
            if '.' in s:                                  # «5.27» или «5.271» (5.27.1) — как в КоАП
                keys.append(s); continue
            v = int(s)
            done = False
            if cur and v != cur + 1:                      # «61» после статьи 6 — это 6.1; «3751» после 335.1 — это 375.1
                for k in range(len(s) - 1, 0, -1):
                    base, sup = int(s[:k]), s[k:]
                    if sup[0] != '0' and (base == cur or (cur < base <= cur + 60 and v - cur > 60)):
                        keys.append('%d.%s' % (base, sup)); cur = base; done = True; break
            if done: continue
            if v < cur and cur - v > 3: cur = v           # оглавление или новая часть текста — счёт начинается заново
            elif v >= cur: cur = v
            keys.append(s)
    for k, m in zip(keys, ms):
        m2 = re.search(r'(?m)^[ \t]*(Статья \d+[\d.]*\*?\.? ?[А-ЯЁ]?|Глава \d+|ГЛАВА |Раздел |РАЗДЕЛ |ЧАСТЬ |§ ?\d)', r[m.end():])
        b = r[m.start():m.end() + (m2.start() if m2 else 9000)]
        if k not in H or len(b) > len(H[k]): H[k] = b
    _hix[code] = H
    return H


def article(code, num):
    """Список (номер части, текст) статьи; номер части — из текста («1. …») или по счёту абзацев."""
    key = (code, num)
    if key in _art: return _art[key]
    H = heads(code)
    best = H.get(num)
    if best is None and num.count('.') == 2:              # 5.27.1 → «5.271»
        best = H.get(num[:num.rindex('.')] + num[num.rindex('.') + 1:])
    if best is None:
        _art[key] = None; return None
    b = NOTE.sub('', best)
    lines = [l.strip() for l in b.split('\n')]
    # заголовок: до первой пустой строки
    k = 0
    while k < len(lines) and lines[k]: k += 1
    if code == 'CONST': k = 1
    title = ' '.join(lines[:k]); paras, cur = [], ''
    for l in lines[k:]:
        if not l or re.fullmatch(r'\d+', l): continue
        if re.fullmatch(r'\d+(\.\d+)?\.', l) and not cur:      # номер части стоит на отдельной строке
            cur = l; continue
        cur = (cur + ' ' + l).strip()
        if re.search(r'[.;:]\)?$', l) or re.search(r'\(Утратил[аи]? силу[^)]*\)$', cur): paras.append(cur); cur = ''
    if cur: paras.append(cur)
    numbered = sum(1 for p in paras if re.match(r'\d+(\.\d+)?\. ', p)) >= 1 or len(paras) == 1 and False
    parts, kk, prev = [], 0, '.'
    for p in paras:
        m = re.match(r'(\d+)(\d)?\. (?=[А-ЯЁ(«])', p) if numbered else None
        if numbered:
            m = re.match(r'(\d+(?:\.\d+)?)\. ', p)
            if m: parts.append([m.group(1), p])
            elif parts: parts[-1][1] += '\n' + p
            else: parts.append(['', p])
        else:
            if prev.rstrip(')').endswith('.') or 'тратил' in prev[-80:]:
                kk += 1; parts.append([str(kk), p])
            else: parts[-1][1] += '\n' + p
            prev = p
    _art[key] = (title, parts, numbered)
    return _art[key]


def point(txt, pt):
    m = re.search(r'(?:^|\n)%s\) .*?(?=\n(?:\d+(?:\.\d+)?|[а-я])\) |\Z)' % re.escape(pt), txt, flags=re.S)
    return m.group(0).strip() if m else None


_flat = {}


def flat(c):
    if c not in _flat:
        _flat[c] = re.sub(r'\s+', ' ', NOTE.sub('', re.sub(r'(\w)-\n(\w)', r'\1\2', raw(c))))
    return _flat[c]


def punkt(code, n, lt):
    t = flat(code)
    ms = list(re.finditer(r'(?<=[ .;:)»]) ?%s\. (?=[А-ЯЁ«(])' % re.escape(n), t))
    if not ms: return '[нет пункта]'
    best = ''
    for m in ms:
        nx = str(int(n) + 1) if n.isdigit() else None
        m2 = re.search(r' %s\. (?=[А-ЯЁ«(])' % re.escape(nx), t[m.end():]) if nx else None
        b = t[m.start():m.end() + (m2.start() if m2 and m2.start() < 12000 else 2500)]
        if len(toks(b) & lt) > len(toks(best) & lt) or not best: best = b
    return window(best.strip(), lt, CAP)


ORD = {w: i + 1 for i, w in enumerate('первая вторая третья четвёртая пятая шестая седьмая восьмая девятая десятая одиннадцатая двенадцатая тринадцатая четырнадцатая пятнадцатая'.split())}
ORD.update({w[:-2] + 'ой': i for w, i in list(ORD.items())}); ORD.update({'третьей': 3, 'первую': 1, 'вторую': 2, 'третью': 3, 'четвертая': 4, 'четвертой': 4, 'четвёртую': 4, 'пятую': 5})
ORD.update({w[:-2] + 'ые': i for w, i in list(ORD.items()) if w.endswith('ая')})


def nums(s):
    out = []
    for x in re.split(r',| и |;', s):
        x = x.strip().rstrip('.')
        m = re.match(r'(\d+)\s*[–-]\s*(\d+)$', x)
        if m and int(m.group(2)) - int(m.group(1)) < 40: out += [str(k) for k in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif m: out += [m.group(1), m.group(2)]
        elif re.match(r'\d+(\.\d+)?(–\d+(\.\d+)?)?$', x): out += x.split('–')
        elif x in ORD: out.append(str(ORD[x]))
        elif re.match(r'«?[а-я]»?$', x): out.append(x.strip('«»'))
    return out


SEEN = set()


def show(label, text):
    k = (label, text)
    if k in SEEN:
        print('     ↑ %s' % label); return
    SEEN.add(k); print('     · %s: %s' % (label, text))


def norm(code, art, ps, pts, lt, q=''):
    a = article(code, art)
    name = q + (IDX.get(code, 'Конституция')[:28] if code != KOD[MAIN] else '')
    if a is None:
        show('ст. %s %s' % (art, name), '[нет статьи]'); return
    title, parts, numbered = a
    lab = 'ст. %s %s' % (art, name)
    if not ps and not pts:
        body = '\n'.join(('(%s) ' % p if not numbered else '') + t for p, t in parts)
        if '↳' in q: show(lab.strip(), window(body, lt, min(CAP, 200))); return
        show(lab.strip(), title + ' ¶ ' + window(body, lt, CAP)); return
    D = dict((p, t) for p, t in parts)
    if not ps:
        whole = '\n'.join(t for p, t in parts)
        for pt in pts:
            t = D.get(pt) if numbered and pt in D and not point(whole, pt) else point(whole, pt)
            show('п. %s %s' % (pt, lab), window(t, lt, CAP) if t else '[нет пункта] ' + title)
        return
    for p in ps:
        t = D.get(p)
        if t is None: t = D.get(p.replace('.', ''))        # часть 1.1 в тексте записана как «11.»
        if t is None and not numbered and len(parts) == 1:  # статья без деления на части: читается целиком
            t = parts[0][1]
        if t is None:
            show('ч. %s %s' % (p, lab), '[нет части] %s; частей: %s' % (title, ', '.join(x for x, _ in parts))); continue
        if pts:
            for pt in pts:
                x = point(t, pt) or point(t, pt.replace('.', ''))
                show('п. %s ч. %s %s' % (pt, p, lab), (t.split('\n')[0][:140] + ' ¶ ' + window(x, lt, CAP)) if x else '[нет пункта] ' + window(t, lt, 300))
        else:
            show('ч. %s %s' % (p, lab), window(t, lt, CAP))


# ---------- литература: ближайшее место
PK = '/tmp/kread_%s.pkl' % SUBJ


def build():
    chunks, inv, df = [], {}, {}
    seen_names = set()
    for c, n in IDX.items():
        if n in seen_names: continue
        seen_names.add(n)
        try: t = open(glob.glob(os.path.join(SRC, c + '*'))[0], encoding='utf-8', errors='replace').read()
        except Exception: continue
        t = t.replace('\xa0', ' ').replace('\u00ad', '')
        segs = re.split(r'(?m)^@@ (\d+) \|[^\n]*\n', t)
        pages = [(0, segs[0])] + [(int(segs[i]), segs[i + 1]) for i in range(1, len(segs) - 1, 2)]
        for pg, body in pages:
            body = re.sub(r'\s+', ' ', re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', body))
            sents = re.split(r'(?<=[.;!?]) (?=[А-ЯЁ«\d(–-])', body)
            cur = ''
            for s in sents + ['']:
                if cur and (len(cur) + len(s) > 330 or not s):
                    i = len(chunks); chunks.append((c, pg, cur)); tk = toks(cur)
                    for w in tk: inv.setdefault(w, []).append(i)
                    cur = s
                else: cur = (cur + ' ' + s).strip()
    return chunks, inv


def lit():
    if os.path.exists(PK): return pickle.load(open(PK, 'rb'))
    d = build(); pickle.dump(d, open(PK, 'wb')); return d


_L = None


def nearest(line, only=None):
    global _L
    if _L is None: _L = lit()
    chunks, inv = _L
    lt = toks(line)
    if len(lt) < 3: return None
    import math
    sc = {}; tot = 0.0
    for w in lt:
        ids = inv.get(w, ())
        wt = math.log(len(chunks) / (1 + len(ids)))
        tot += wt
        for i in ids:
            if only and chunks[i][0] not in only: continue
            sc[i] = sc.get(i, 0) + wt
    if not sc: return None
    i = max(sc, key=lambda k: (sc[k], -len(chunks[k][2])))
    c, pg, tx = chunks[i]
    return sc[i] / tot, c, pg, tx


AUTH = {}
for c, n in IDX.items():
    m = re.match(r'([А-ЯЁ][а-яё]+)(?=,|\.| и др)', n)
    if m and not re.match(r'(ФЗ|ФКЗ|Закон|Постановление|Приказ|Указ|Конвенция|Кодекс|Гражданский|Трудовой|Семейный|Арбитражный|Основы|Обзор|Декларация|Рекомендация|Международный|Конституция|Определение|Всеобщая|Устав|Положение)', n):
        AUTH.setdefault(m.group(1)[:6].lower(), set()).add(c)

# ---------- разбор ссылок
CIT = re.compile(r'(?:(?:подпункт\w*|пункт\w*|абзац\w*) (?P<pt>(?:«?[\dа-я.]+»?)(?:(?:, | и |–)«?[\dа-я.]+»?)*) )?'
                 r'(?:част\w+ (?P<ps>(?:[\d.]+|[а-яё]+)(?:(?:, | и |–)(?:[\d.]+|[а-яё]+))*) )?'
                 r'стат(?:ья|ьи|ей|ье|ью|ьях|ьями) (?P<art>\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*)')
PCIT = re.compile(r'пункт\w* (?P<pt>\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*)(?! (?:част|стат))(?P<rest>[^;)]*)')

text = open(ANS, encoding='utf-8').read()
# акты, полностью названные в ответе: № → код
FULL = {}
for m in re.finditer(r'(?:от \d{1,2} [а-я]+ \d{4} года |от \d\d\.\d\d\.\d{4} )№ ?[\dА-Яа-ян./-]+', text):
    c = by_number(m.group(0))
    num = re.search(r'№ ?([\dА-Яа-ян./-]+)', m.group(0)).group(1).rstrip('.,')
    if c: FULL.setdefault(num, c)
FIRST_LAW = None
m = re.search(r'(?:Федеральн\w+ (?:конституционн\w+ )?закон\w*|Закон\w* Российской Федерации)[^№\n]{0,90}№ ?[\dА-Яа-я./-]+', text)
if m: FIRST_LAW = by_number(m.group(0))


def act(fragment, last):
    """(код, помета) для хвоста ссылки после номера статьи."""
    fragment = re.sub(r';[^;]*(введен|в редакции|утратил)[^;]*', '', fragment)
    for pat, key in NAMED:
        if key and re.search(pat, fragment):
            return (KOD.get(key, key) if key != 'ГК' else 'ГК'), ''
    if re.search(r'того же|этого (закона|кодекса)|названного', fragment):
        return last, '?'
    if '№' in fragment:
        c = by_number(fragment)
        if not c:
            num = re.search(r'№ ?([\dА-Яа-ян./-]+)', fragment).group(1).rstrip('.,')
            c = FULL.get(num)
        return c, '' if c else ''
    if re.search(r'\bЗакона\b', fragment):
        return (last if last and last not in KOD.values() else FIRST_LAW), '?'
    return KOD[MAIN], ''


lines = text.split('\n')
last_act = KOD[MAIN]; last_post = None; npar = 0; CTX = None; CTXN = []
for ln, l in enumerate(lines, 1):
    if not l.strip(): continue
    npar += 1
    if LR and not (LR[0] <= ln <= LR[1]): continue
    print('[%d] %s' % (ln, l))
    if l.startswith('#'):
        CTX = None; CTXN = []; continue
    lt = toks(re.sub(r'\((?:[^()]|\([^()]*\))*\)', ' ', l))
    groups = []
    for m_ in re.finditer(r'\(((?:[^()]|\([^()]*\))*)\)', l):
        g_ = m_.group(1)
        italic = l[max(0, m_.start() - 2):m_.start()] == '//'
        if not italic and not any(re.search(p_, g_) for p_, k_ in NAMED) and '№' not in g_ and not re.search(r'того же|Закона', g_):
            sent = re.split(r'(?<=[.;!?]) ', l[:m_.start()])[-1]      # акт назван в самом предложении до скобки
            hit = [(mm.start(), k_) for p_, k_ in NAMED if k_ for mm in re.finditer(p_, sent)]
            if hit: g_ = g_ + ' ' + {'К': 'Конституции', 'ГПК': 'ГПК', 'ТК': 'Трудового кодекса', 'ГК': 'ГК РФ', 'СК': 'Семейного кодекса',
                                     'АПК': 'Арбитражного процессуального', 'КАС': 'административного судопроизводства',
                                     'КоАП': 'административных правонарушениях'}.get(max(hit)[1], '')
        groups.append(g_)
    had = False; NOWN = []
    bare = re.sub(r'\((?:[^()]|\([^()]*\))*\)', ' ', l)        # акт назван в тексте строки, пункты — в скобках ниже
    for m_ in re.finditer(r'(?:постановлени\w+|приказ\w*)[^.;]{0,90}?от \d\d\.\d\d\.\d{4} № ?[\dА-Яа-я/-]+', bare):
        c_ = by_number(m_.group(0))
        if c_: last_post = c_
    m0 = re.match(r'Стать[яи] ([\d., –и]+)\.$', l.strip())
    if m0:
        for a_ in nums(m0.group(1)): NOWN.append((KOD[MAIN], a_, [], []))
        had = True
    if l.rstrip().endswith(':') and not re.search(r'\([^()]*стат', l):
        for m in re.finditer(r'стать(?:е|и|ёй|ей|ью|я) (\d+(?:\.\d+)?)([^,;:(]{0,80})', l):
            code_, q_ = act(m.group(2), last_act)
            if code_ == 'ГК': code_ = next(c for lim, c in GK if float(m.group(1)) <= lim)
            if code_: norm(code_, m.group(1), [], [], lt, q_); NOWN.append((code_, m.group(1), [], [])); had = True
    for g in groups:
        if not re.search(r'стать|пункт|част[ьи]|постановлени|глав', g): continue
        pos = 0; ms = list(CIT.finditer(g)); used = []
        for k, m in enumerate(ms):
            tail = g[m.end():ms[k + 1].start() if k + 1 < len(ms) else len(g)]
            code, q = act(tail, last_act)
            if code == KOD[MAIN] and k + 1 < len(ms):      # «статьи 3 и 4 Закона»: акт назван после последней статьи
                pass
            arts = nums(m.group('art')); ps = nums(m.group('ps')) if m.group('ps') else []
            pts = nums(m.group('pt')) if m.group('pt') else []
            had = True; used.append((m.start(), m.end()))
            if code is None:
                print('     · %s: [акт?]' % m.group(0)); continue
            last_act = code
            for a in arts:
                c2 = code
                if code == 'ГК': c2 = next(c for lim, c in GK if float(a) <= lim)
                norm(c2, a, ps if len(arts) == 1 else [], pts if len(arts) == 1 else [], lt, q)
                NOWN.append((c2, a, ps if len(arts) == 1 else [], pts if len(arts) == 1 else []))
        g2 = g
        for a, b in reversed(used): g2 = g2[:a] + ' ' * (b - a) + g2[b:]
        for m in PCIT.finditer(g2):
            rest = m.group('rest'); had = True
            if '№' in rest or re.search(r'постановлени|приказ|Положени|Правил|Обзор|Устав', rest):
                c = by_number(rest) if '№' in rest else None
                mnum = re.search(r'№ ?([\dА-Яа-ян./-]+)', rest)
                if mnum and last_post and not re.search(r'от \d', rest) and \
                        re.search(r'№ ?%s(?![\dА-Яа-я-])' % re.escape(mnum.group(1).rstrip('.,')), IDX[last_post]):
                    c = last_post                  # «постановление № 15» — краткая ссылка на акт, уже названный в ответе с датой
                if not c and '№' in rest:
                    num = re.search(r'№ ?([\dА-Яа-ян./-]+)', rest).group(1).rstrip('.,'); c = FULL.get(num)
                if not c and re.search(r'того же|Положени|Правил|Обзор|Устав', rest): c = last_post
                q = ''
            else:
                c, q = last_post, '?'
            if not c:
                print('     · %s: [акт?]' % m.group(0)[:70]); continue
            last_post = c
            for p in nums(m.group('pt')):
                show('%sп. %s %s' % (q, p, IDX[c][:34]), punkt(c, p, lt))
    if NOWN and (l.rstrip().endswith(':') or re.match(r'Стать[яи] [\d., –и]+\.$', l.strip())):
        CTXN = NOWN                                 # вводная строка со ссылкой: пункты под ней читаются по той же норме
    elif NOWN or not re.match(r'(- |\d+\. )', l):
        if not re.match(r'(- |\d+\. )', l): CTXN = []
    weak = False
    if not had and CTXN and re.match(r'(- |\d+\. )', l):
        for code_, a_, ps_, pts_ in CTXN: norm(code_, a_, ps_, pts_, lt, '↳')
        had = True
        full = ' '.join(t_ for code_, a_, _p, _q in CTXN for _x, t_ in (article(code_, a_) or ('', [], 0))[1])
        weak = len(lt & toks(full)) < 0.6 * max(1, len(lt))
    only = set()
    for w in re.findall(r'[А-ЯЁ][а-яё]{4,}', l):
        if w[:6].lower() in AUTH and re.search(r'пособи|учебник|отмечает|пишет|называет|по мнению|\(«|\d{4}\)', l): only |= AUTH[w[:6].lower()]
    if only and len(lt) <= 6 and re.search(r'[.:]$', l.strip()) and not l.startswith('- '):
        CTX = only; continue                       # вводная строка «По пособию …»: следующие пункты ищутся в нём
    if not only and CTX and l.startswith(('- ', '1', '2', '3', '4', '5', '6', '7', '8', '9')): only = CTX
    elif not l.startswith(('- ', '1', '2', '3', '4', '5', '6', '7', '8', '9')): CTX = None
    if (not had or only or weak) and not l.startswith('!!'):
        body = re.sub(r'\((?:[^()]|\([^()]*\))*\)', ' ', l)
        sents = [s for s in re.split(r'(?<=[.!?]) (?=\*{0,2}[А-ЯЁ])', body) if len(toks(s)) >= 3] or [body]
        prevk = None
        for s in sents:
            r = nearest(s, only or None)
            if r:
                sc, c, pg, tx = r
                if (c, pg, tx) == prevk:
                    print('     ≈ %d%% то же место' % round(sc * 100)); continue
                prevk = (c, pg, tx)
                print('     ≈ %d%% [%s с.%s %s] %s' % (round(sc * 100), c, pg, IDX[c][:26], tx[:CAP + 60]))
print('-- абзацев: %d' % npar)
