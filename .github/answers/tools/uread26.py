#!/usr/bin/env python3
"""uread26.py N [-l A-B] [-c ЗНАКОВ] — ответ УПП № N целиком, строка за строкой, с текстом каждой названной нормы под строкой.

Для сплошной сверки глазами (журнал full-read.md): ничего не отбирает и не оценивает, печатает все непустые строки.
Ссылка без названия акта считается ссылкой на УПК РФ (tools/upk26.py); «Конституции» — распознанный текст скана
из src-text/, «УК» — Уголовный кодекс из той же папки (диспозиция и начало санкции); так же, как Конституция, читается ссылка в круглых скобках без курсива, если в том же предложении названа Конституция.
«гл. N» — название главы УПК, «ст. A–B» — названия статей диапазона. Ссылка без статьи («ч. 3», «п. 2 ч. 1») относится
к статье из заголовка раздела (или вводной строки с двоеточием), а если её там нет — к последней названной статье; помечается «?».
Под строкой: названная часть (пункт) целиком, если она не длиннее ЗНАКОВ (по умолчанию 520), иначе те её предложения,
в которых больше всего слов строки («…» — пропуск). «{2025}» — часть менялась в этом году. Норма, уже напечатанная
в этом ответе тем же куском, заменяется пометкой «↑». «[нет …]» — такой статьи, части или пункта в акте не нашлось;
«[акт?]» — ссылка на иной акт, его текст печатается вручную.
    python3 tools/uread26.py 31 -l 1-40
"""
import glob, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import upk26

argv = sys.argv[1:]; CAP = 520; LR = None
if '-c' in argv: i = argv.index('-c'); CAP = int(argv[i + 1]); del argv[i:i + 2]
if '-l' in argv: i = argv.index('-l'); a, b = argv[i + 1].split('-'); LR = (int(a), int(b)); del argv[i:i + 2]
N = int(argv[0])
ARTS, _ = upk26.load()
ORDER = _


def toks(s):
    return set(w[:5] for w in re.findall(r'[а-яё]{4,}', s.lower().replace('ё', 'е')))


def nums(s):
    out = []
    for x in re.split(r',| и ', s):
        x = x.strip().rstrip('.')
        m = re.match(r'(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)$', x)
        if m and '.' not in m.group(1) and '.' not in m.group(2):
            out += [str(k) for k in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif m:
            out += [m.group(1), m.group(2)]
        elif re.match(r'[\d.]+$', x) and x:
            out.append(x)
        elif re.match(r'«?[а-я]»?$', x):
            out.append(x.strip('«»'))
    return out


def window(text, lt, cap):
    text = re.sub(r'\s*\n\s*', ' ¶ ', text.strip())
    if len(text) <= cap:
        return text
    units = [u for u in re.split(r'(?<=[.;:]) (?=[А-ЯЁа-яё\d¶(])', text) if u.strip()]
    sc = sorted(((len(toks(u) & lt), -k) for k, u in enumerate(units)), reverse=True)
    take, size = set(), 0
    for s, k in sc:
        k = -k
        if s == 0 and take:
            break
        if size + len(units[k]) > cap and take:
            continue
        take.add(k); size += len(units[k])
        if size >= cap:
            break
    out, prev = [], -1
    for k in sorted(take):
        u = units[k] if len(units[k]) <= cap + 200 else units[k][:cap + 200] + '…'
        out.append(('' if k == prev + 1 else '… ') + u); prev = k
    return ' '.join(out) + (' …' if prev < len(units) - 1 else '')


def point(txt, pt):
    m = re.search(r'(?m)^%s\) .*?(?=^\d+(?:\.\d+)?\) |\Z)' % re.escape(pt), txt, flags=re.S)
    return m.group(0).strip() if m else None


def upk(art, ps, pts, lt):
    """[(метка, текст)] для ссылки на УПК."""
    if art not in ARTS:
        return [('ст. %s' % art, '[нет статьи]')]
    P = upk26.parts(art, notes=True)
    title = 'Ст. %s. %s' % (art, upk26.clean(ARTS[art]['title'], False))
    res = []
    if not ps and not pts:
        body = '\n'.join(v for v in P.values() if v.strip())
        return [('ст. %s' % art, title + ' ¶ ' + window(body, lt, CAP))]
    if not ps:
        whole = '\n'.join(P.values())
        for pt in pts:
            t = point(whole, pt)
            res.append(('п. %s ст. %s' % (pt, art), window(t, lt, CAP) if t else '[нет пункта]'))
        return res
    for p in ps:
        t = P.get(p)
        if t is None:
            res.append(('ч. %s ст. %s' % (p, art), '[нет части] ' + title + '; части: ' + ', '.join(k for k in P if k)))
            continue
        if pts:
            head = t.split('\n')[0]
            for pt in pts:
                x = point(t, pt)
                res.append(('п. %s ч. %s ст. %s' % (pt, p, art),
                            (head[:160] + ' ¶ ' + window(x, lt, CAP)) if x else '[нет пункта] ' + window(t, lt, 300)))
        else:
            res.append(('ч. %s ст. %s' % (p, art), window(t, lt, CAP)))
    return res


CH = {}
for _n in _:
    for _l in ARTS[_n]['lines']:
        _m = re.match(r'@@ГЛАВА (\d+)(?:\^(\d+)\^)?\. ?(.*)', _l)
        if _m: CH[_m.group(1) + ('.' + _m.group(2) if _m.group(2) else '')] = _m.group(3)
# глава 1 стоит до первой статьи и в разборе не видна
CHREF = re.compile(r'гл\. ?(\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*)')

def other(key, name, art, ps, lt):
    """Статья УК или Конституции (читает tools/uppver.py): названные части, у УК — диспозиция и начало санкции."""
    import uppver
    A, _o = uppver.load('К' if key == 'К' else 'УК')
    if art not in A and key == 'К':      # статьи в редакции 2020 года помечены в скане звёздочкой, uppver их пропускает
        raw = open(os.path.join(HERE, '..', 'src-text', 'Конституция РФ (распознанный текст скана).txt'), encoding='utf-8').read()
        m = re.search(r'(?m)^Статья %s\*\s*$(.*?)(?=^Статья \d|^ГЛАВА|\Z)' % re.escape(art), raw, flags=re.S)
        if m:
            A = {art: {'title': '', 'lines': [x.strip() for x in m.group(1).split('\n') if x.strip() and not re.fullmatch(r'\d+', x.strip())]}}
    if art not in A:
        return [('ст. %s %s' % (art, name), '[нет статьи]')]
    title = uppver.clean(A[art]['title'])
    P, k = {'': ''}, ''
    for x in A[art]['lines']:
        x = uppver.clean(x)
        if not x:
            continue
        m = re.match(r'(\d+(?:\.\d+)?)\. ', x)
        if m:
            k = m.group(1); P[k] = ''
        if key == 'УК' and x.startswith('наказыва'):
            x = '→ ' + x[:150] + ('…' if len(x) > 150 else '')
        P[k] += x + (' ' if key == 'К' else '\n')
    res = []
    for p in ps or [None]:
        if p is None:
            body = '\n'.join(v for v in P.values() if v.strip())
            res.append(('ст. %s %s' % (art, name), (title + ' ¶ ' if title else '') + window(body, lt, CAP)))
        elif p in P:
            res.append(('ч. %s ст. %s %s' % (p, art, name), (title + ' ¶ ' if title else '') + window(P[p], lt, CAP)))
        else:
            res.append(('ч. %s ст. %s %s' % (p, art, name), '[нет части] ' + title + '; части: ' + ', '.join(q for q in P if q)))
    return res


REF = re.compile(r'гл\. ?(\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*)')

_cons = None


def cons(art, ps, lt):
    global _cons
    if _cons is None:
        f = [p for p in glob.glob(os.path.join(HERE, '..', 'src-text', '*.txt')) if 'Конституц' in p][0]
        _cons = re.sub(r'\s+', ' ', open(f, encoding='utf-8').read())
    i = _cons.find('Статья %s ' % art)
    if i < 0:
        return [('ст. %s Конституции' % art, '[нет статьи]')]
    j = _cons.find('Статья %d ' % (int(art) + 1), i)
    t = _cons[i:j if j > 0 else i + 3000]
    res = []
    for p in ps or [None]:
        if p:
            m = re.search(r'(?<= )%s\. .*?(?= \d+\. [А-Я]|$)' % p, t)
            res.append(('ч. %s ст. %s Конституции' % (p, art), window(m.group(0), lt, CAP) if m else '[нет части] ' + t[:300]))
        else:
            res.append(('ст. %s Конституции' % art, window(t, lt, CAP)))
    return res


REF = re.compile(r'((?:(?:подп|п|ч|абз)\. ?[^()/;]*?)?)ст\. ?(\d+(?:\.\d+)?(?:(?:, | и |–)\d+(?:\.\d+)?)*)'
                 r'( (?:УК|Конституции|УИК|ГК|ГПК|КоАП|Закона|Федерального|Уголовного кодекса|постановления)[^,;)/]*)?')
BARE = re.compile(r'\(((?:(?:п|ч)\. ?[\d., и–«»а-я]+?)+)\)')


def split_prefix(pre):
    ps = pts = []
    m = re.search(r'ч\. ?([\d., и–]+)', pre)
    if m: ps = nums(m.group(1))
    m = re.search(r'(?<!од)п\. ?([\d., и–«»а-я]+?)(?= ч\.|$| ст)', pre.strip())
    if m: pts = nums(m.group(1))
    return ps, pts


seen, ctx, head, headp = set(), None, None, None      # head — статья из заголовка раздела или вводной строки с двоеточием
for i, l in enumerate(open(os.path.join(HERE, '..', 'upp', 'q%03d.txt' % N), encoding='utf-8').read().split('\n'), 1):
    hm = [x for x in REF.finditer(l) if not x.group(3)]
    if l.startswith('#') or l.rstrip().endswith(':'):
        if len(hm) == 1 and re.fullmatch(r'\d+(?:\.\d+)?', hm[0].group(2)):
            head = hm[0].group(2)
            hp = re.search(r'\(ч\. (\d+(?:\.\d+)?) ст\. ' + re.escape(head) + r'\)', l)
            headp = hp.group(1) if hp else None      # «## Права //(ч. 4 ст. 46)//» → «(п. 3)» ниже = п. 3 ч. 4 ст. 46
        elif l.startswith('#'):
            head = headp = None
    if not l.strip() or (LR and not LR[0] <= i <= LR[1]):
        if l.strip():
            m = [x for x in REF.finditer(l) if not x.group(3)]
            if m: ctx = re.findall(r'\d+(?:\.\d+)?', m[-1].group(2))[-1]
        continue
    print('%d| %s' % (i, l))
    lt = toks(re.sub(r'//[^/]+//', '', l))
    out = []
    ms = sorted([(m.start(), 0, m) for m in REF.finditer(l)] + [(m.start(), 1, m) for m in CHREF.finditer(l)]
                + [(m.start(), 2, m) for m in BARE.finditer(l)], key=lambda x: x[:2])
    spans = [m.span() for _, k, m in ms if k == 0]
    for _, kind, m in ms:
        if kind == 1:
            for x in re.split(r', | и ', m.group(1)):
                r = re.match(r'(\d+)–(\d+)$', x)
                for k in ([str(q) for q in range(int(r.group(1)), int(r.group(2)) + 1)] if r else [x]):
                    out.append(('гл. %s' % k, CH.get(k, '[нет главы]' if k != '1' else 'ОСНОВНЫЕ ПОЛОЖЕНИЯ (глава 1)')))
            continue
        if kind == 2:
            if any(a <= m.start() < b for a, b in spans) or 'ст.' in m.group(1):
                continue
            ps, pts = split_prefix(m.group(1))
            if (head or ctx) and (ps or pts):
                if head and headp and pts and not ps:
                    ps = [headp]
                out += [(k + ' ?', v) for k, v in upk(head or ctx, ps, pts, lt)]
            continue
        # «ч. 1 ст. 50, ч. 2 ст. 51»: префикс берём после последней запятой перед «ч.»/«п.»
        pre = re.split(r'(?:ст\. ?[\d.]+,? ?)', m.group(1))[-1]
        ps, pts = split_prefix(pre)
        arts = []
        act = (m.group(3) or '').strip()
        for x in re.split(r', | и ', m.group(2)):
            r = re.match(r'(\d+(?:\.\d+)?)–(\d+(?:\.\d+)?)$', x)
            if r and not act and r.group(1) in ARTS and r.group(2) in ARTS:
                seq = ORDER[ORDER.index(r.group(1)):ORDER.index(r.group(2)) + 1]
                if len(seq) > 2:      # диапазон статей — только названия
                    out.append(('ст. %s' % x, '; '.join('%s %s' % (k, upk26.clean(ARTS[k]['title'], False)) for k in seq)))
                    ctx = r.group(2)
                    continue
                arts += seq
            else:
                arts += re.findall(r'\d+(?:\.\d+)?', x)
        ital = l[:m.start()].count('//') % 2 == 1
        sent = re.split(r'(?<=[.;]) ', l[:m.start()])[-1]
        if not act and not ital and 'Конституц' in sent and 'УПК' not in sent and '.' not in m.group(2):
            act = 'Конституции (по строке)'
        if not act:      # «ч. 1 ст. 115, ч. 1 ст. 116.1 УК» — название акта стоит после последней статьи перечня
            rest = [x for _, k2, x in ms if k2 == 0 and x.start() >= m.end()]
            end = m.end()
            for x in rest:
                if not re.fullmatch(r',? ?(?:и |или )?', l[end:x.start()]):
                    break
                if x.group(3):
                    act = x.group(3).strip(); break
                end = x.end()
        for a in arts:
            if act.startswith('Конституции'):
                out += other('К', 'Конституции', a, ps if len(arts) == 1 else [], lt)
            elif re.match(r'УК\b|Уголовного кодекса', act):
                out += other('УК', 'УК', a, ps if len(arts) == 1 else [], lt)
            elif act:
                out.append(('%sст. %s %s' % (m.group(1), a, act), '[акт?]'))
            else:
                out += upk(a, ps if len(arts) == 1 else [], pts if len(arts) == 1 else [], lt)
                ctx = a
    for k, v in out:
        key = (k.rstrip(' ?'), v)
        if key in seen:
            print('      ↑ %s' % k)
        else:
            seen.add(key)
            print('      [%s] %s' % (k, v))
