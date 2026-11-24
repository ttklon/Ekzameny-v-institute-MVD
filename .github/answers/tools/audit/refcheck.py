#!/usr/bin/env python3
"""refcheck.py ПАПКА_ОТВЕТОВ ПАПКА_ТЕКСТОВ [-d КОД] [-q РЕГ] [-a] [-w N] [-s N] [-t ДОЛЯ] [-o ПОМЕТКА]

Сверка ответов с нормами, на которые они ссылаются. Ссылка в ответе — текст между «//» («//ч. 1 ст. 4 Закона о полиции//»).
Для каждого предложения со ссылкой программа находит норму в текстах источников (папка от kextract.py, имена файлов —
«код название.txt») и сравнивает:
  ЧИСЛО   — число из предложения, которого нет в названной норме (числа словами и цифрами приводятся к одному виду);
  НЕТ     — названной статьи, части или пункта в акте нет;
  СЛОВА   — доля значимых слов предложения, найденных в норме, ниже порога (-t, по умолчанию 0.2);
  СПИСОК  — то же для пунктов списка под строкой со ссылкой, оканчивающейся двоеточием;
  ДРУГОЙ  — число нашлось не в том акте, к которому ссылка отнесена по порядку упоминания, а в другом акте, названном в ответе
            (печатается одной строкой в конце — для просмотра).
Акт ссылки: названный в ней самой (кодекс, «№ …», сокращение из «далее — …»); если не назван — последний упомянутый в ответе;
для статьи без акта — ещё и кодекс по умолчанию (-d: koap, uk, upk, gpk, tk, kas, gk). Акты, которых нет среди текстов,
перечисляются в конце; предложения с такими ссылками не сверяются.
  -q РЕГ   только файлы ответов, имя которых подходит под выражение;   -a   печатать все сверенные предложения;
  -c       в заголовке блока печатать долю значимых слов предложения, найденных в норме («{57%}»);
  -w N     длина печатаемого отрывка нормы (300);   -s N   длина печатаемого предложения (400);   -o   только блоки с этой пометкой.
Пометка — повод прочитать норму, а не ошибка: предложение может опираться на учебник или на другую норму.
"""
import re, sys, os, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawtext as L

def opt(k, d=None, flag=False):
    if k in sys.argv:
        i = sys.argv.index(k)
        if flag: sys.argv.pop(i); return True
        v = sys.argv[i + 1]; del sys.argv[i:i + 2]; return v
    return False if flag else d
DEF = opt('-d'); QRE = opt('-q'); ALL = opt('-a', flag=True); WIN = int(opt('-w', 300)); SLEN = int(opt('-s', 400)); THR = float(opt('-t', 0.2)); ONLY = opt('-o'); COVP = opt('-c', flag=True)
ANS, SRC = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- указатель актов ----------
ACTS = []
for p in sorted(glob.glob(os.path.join(SRC, '*.txt'))):
    name = os.path.basename(p)[7:-4]
    if name.startswith('_'): continue
    size = os.path.getsize(p)
    if name.startswith('Конституция РФ') and size < 5000:
        alt = glob.glob(os.path.join(HERE, '..', '..', 'src-text', 'Конституция РФ*.txt'))
        if alt: p = alt[0]; size = os.path.getsize(p)
    d = re.search(r'от (\d{2}\.\d{2}\.\d{4})', name); n = re.search(r'№ ?([\w./-]+)', name)
    ACTS.append(dict(path=p, name=name, code=os.path.basename(p)[:6], date=d and d.group(1), num=n and n.group(1).rstrip('.').upper(), size=size))
ARTICLED = re.compile(r'^(ФЗ |ФКЗ |Закон РФ|Закон |Конституция|Основы|КоАП|КАС |[А-ЯЁа-яё -]*[Кк]одекс)')
def articled(a): return bool(ARTICLED.match(a['name'])) and 'Кодекс этики' not in a['name']
def best(cands):
    """из копий одного акта: действующая редакция, затем та, где больше статей, затем больший текст"""
    if not cands: return None
    return max(cands, key=lambda a: ('действующая' in a['name'], 'официальное опубликование' not in a['name'], len(L.articles(a['path'])) if articled(a) else 0, a['size']))
CODERX = [('koap', r'^КоАП РФ|^Кодекс РФ об административных'), ('uk', r'^Уголовный кодекс'), ('upk', r'^Уголовно-процессуальный кодекс'),
          ('uik', r'^Уголовно-исполнительный'), ('kas', r'^КАС РФ|^Кодекс административного судопроизводства'), ('gpk', r'^Гражданский процессуальный'),
          ('apk', r'^Арбитражный процессуальный'), ('tk', r'^Трудовой кодекс'), ('sk', r'^Семейный кодекс'), ('zhk', r'^Жилищный кодекс'),
          ('nk', r'^Налоговый кодекс'), ('const', r'^Конституция РФ'), ('gk1', r'^Гражданский кодекс РФ \(часть первая'), ('gk2', r'^Гражданский кодекс РФ \(часть вторая'),
          ('gk3', r'^Гражданский кодекс РФ \(часть третья'), ('gk4', r'^Гражданский кодекс РФ \(часть четв'), ('pol', r'^ФЗ от 07\.02\.2011 № 3-ФЗ'),
          ('sl', r'^ФЗ от 30\.11\.2011 № 342-ФЗ')]
CODE = {}
for k, rx in CODERX:
    b = best([a for a in ACTS if re.search(rx, a['name'])])
    if b: CODE[k] = b
HCODE = [('koap', r'КоАП|об административных правонарушениях'), ('upk', r'УПК|Уголовно-процессуальн\w+ кодекс'), ('uik', r'УИК|Уголовно-исполнительн\w+ кодекс'), ('uk', r'(?<![А-ЯЁа-яё])УК(?![А-ЯЁа-яё])|Уголовн\w+ кодекс'),
         ('gpk', r'ГПК|Гражданск\w+ процессуальн\w+ кодекс'), ('apk', r'АПК|Арбитражн\w+ процессуальн'), ('kas', r'КАС|административного судопроизводства'), ('gk', r'Гражданск\w+ кодекс'), ('sk', r'Семейн\w+ кодекс'), ('zhk', r'Жилищн\w+ кодекс'),
         ('gk', r'(?<![А-ЯЁа-яё])ГК(?![А-ЯЁа-яё])'), ('tk', r'(?<![А-ЯЁа-яё])ТК(?![А-ЯЁа-яё])|Трудов\w+ кодекс'), ('sk', r'(?<![А-ЯЁа-яё])СК РФ'), ('zhk', r'(?<![А-ЯЁа-яё])ЖК(?![А-ЯЁа-яё])'),
         ('nk', r'(?<![А-ЯЁа-яё])НК(?![А-ЯЁа-яё])'), ('const', r'Конституци'), ('pol', r'[Зз]акон\w* о полиции|«О полиции»')]
def gkpart(art):
    try: n = int(str(art).split('.')[0])
    except ValueError: return 'gk1'
    return 'gk1' if n <= 453 else 'gk2' if n <= 1109 else 'gk3' if n <= 1224 else 'gk4'
BYNUM = collections.defaultdict(list)
for a in ACTS:
    if a['num']: BYNUM[a['num']].append(a)
COPIES = collections.defaultdict(list)
for a in ACTS: COPIES[(a['date'], a['num'], a['name'][:40])].append(a)
def copies(a): return [a] + [b for b in COPIES[(a['date'], a['num'], a['name'][:40])] if b is not a]
def short(a):
    if a is None: return '—'
    if isinstance(a, str): return a
    return a['code'] + ' ' + a['name'][:46]

KIND = re.compile(r'[Зз]акон|[Пп]равил|[Пп]оложени|[Пп]орядк|[Пп]орядо|[Нн]аставлени|[Ии]нструкци|[Рр]уководств|[Уу]став|[Рр]егламент|Пленум|[Оо]бзор|[Уу]каз|[Кк]онцепци|[Сс]тратеги|[Кк]онвенци|[Оо]снов|[Кк]одекс|[Пп]еречн|[Дд]октрин|[Пп]остановлени|[Пп]риказ|[Дд]екларац|[Пп]акт|[Тт]ипов')
SAME = re.compile(r'(того же|этого|этой|названн|указанн|данн|настоящ|той же|этих)', re.I)
GENERIC = {'росси', 'федер', 'закон', 'утвер', 'прика', 'поста', 'далее', 'прави', 'указа', 'плену', 'верхо', 'прези', 'мвд', 'минис', 'кодек'}
ABR = re.compile(r'(?<![А-ЯЁа-яё])[А-ЯЁ]{2,}(?![а-яё])')
def hstems(s): return L.stems(s) | (set(ABR.findall(s)) - {'РФ', 'РСФСР', 'СССР'})
def resolve(h, named):
    """акт по тексту: кодекс, «№ …» (с датой), сокращение, введённое в ответе; None — акт не назван; 'unk:…' — назван, но не найден"""
    h = h.strip(' ,;:.()—–-')
    if not h: return None
    for k, rx in HCODE:
        if re.search(rx, h): return CODE.get(k) or (k if k == 'gk' else 'unk:' + k)
    d = re.search(r'от (\d{2}\.\d{2}\.\d{4})', h); d = d and d.group(1)
    ns = [x.rstrip('.,').upper() for x in re.findall(r'№ ?([0-9A-Za-zА-Яа-яёЁ.-]+(?:/[0-9А-Яа-яёЁ.-]+)?)', h)]
    hs = hstems(h)
    if ns or d:
        cands = []
        for n in ns:
            cands += BYNUM.get(n, [])
            if not cands and '/' in n:
                for part in n.split('/'): cands += BYNUM.get(part, [])
        if not ns: cands = [a for a in ACTS if a['date'] == d and (('Пленум' in h) == ('Пленум' in a['name'])) and (('Обзор' in h) == ('Обзор' in a['name']))]
        if d and any(a['date'] == d for a in cands): cands = [a for a in cands if a['date'] == d]
        elif d and ns and cands: cands = []                                  # номер тот же, дата другая — другой акт
        if cands:
            groups = collections.defaultdict(list)
            for a in cands: groups[(a['date'], a['num'], a['name'][:12])].append(a)
            if len(groups) > 1:                                               # один номер у разных актов: по упоминанию в ответе, затем по словам
                for act, st in named[::-1]:
                    if not isinstance(act, str) and any(act in g for g in groups.values()): return act
                key = max(groups, key=lambda k: (len(hs & L.stems(groups[k][0]['name'])), 'МВД' in k[2]))
                return best(groups[key])
            return best(cands)
        return 'unk:' + (' '.join('№ ' + n for n in ns) or h[:50])
    ab = set(ABR.findall(h)) - {'РФ', 'МВД', 'РСФСР'}
    if ab:
        for act, st in named[::-1]:
            if not isinstance(act, str) and ab & ALIAS.get(id(act), set()): return act
    for a_, rx in (('КВВТ', r'^Кодекс внутреннего водного'), ('ВзК', r'^Воздушный кодекс'), ('ЛК', r'^Лесной кодекс'), ('ЗК', r'^Земельный кодекс'), ('КТМ', r'^Кодекс торгового мореплавания')):
        if a_ in ab:
            b_ = best([a for a in ACTS if re.search(rx, a['name'])])
            return b_ or 'unk:' + a_
    if not KIND.search(h): return None
    hk = hs - GENERIC
    if SAME.search(h) and len(hk) <= 1: return None
    if not hs: return None
    bestn = None; law = bool(re.search(r'[Зз]акон', h)); km = KIND.search(h); kw = km.group().lower()[:6] if km and not law else None
    for act, st in named[::-1]:
        if not isinstance(act, str):
            if law != bool(re.match(r'ФЗ |ФКЗ |Закон', act['name'])): continue
            raw_ = RAWN.get(id(act), '') + ' ' + act['name']
            if kw and not re.search(kw, raw_, re.I): continue
        al_ = ALIAS.get(id(act), set()) if not isinstance(act, str) else set()
        sc = len(hk & st) * 2 + len(hs & st) + (10 if hk and hk <= al_ else 0) + (20 if hk and hk == al_ else 0)
        if (hk & st or (not hk and (hs & st or kw))) and (bestn is None or sc > bestn[0]): bestn = (sc, act)
    if bestn: return bestn[1]
    if hk:
        cands = [a for a in ACTS if hk <= L.stems(a['name'])]
        if cands: return best([a for a in cands if a['name'] == min(cands, key=lambda a: len(a['name']))['name']])
        return 'unk:' + h[:50]
    return None

# ---------- разбор ссылки ----------
VAL = r'(?:«[а-яё]»|\d+(?:\.\d+)*(?:\(\d+\))?)'
LVL = re.compile(r'(?<![А-ЯЁа-яё])(?P<k>подп\.|подпункт[а-я]*|пп\.|п\.|пункт[а-я]*|ч\.|част[ьию]|частями|ст\.|стать[яиеюй]|статьями|статьях|абз\.)\s*(?P<v>%s(?:\s*(?:,|–|—|-| и )\s*%s)*)' % (VAL, VAL), re.I)
ORDER = {'абз.': -1, 'подп.': 0, 'пп.': 0, 'п.': 1, 'ч.': 2, 'ст.': 3}
def vlist(v):
    out = []
    for piece in re.split(r'\s*(?:,| и )\s*', v):
        m = re.fullmatch(r'(\d+)\s*[–—-]\s*(\d+)', piece)
        if m and 0 < int(m.group(2)) - int(m.group(1)) <= 40: out += [str(x) for x in range(int(m.group(1)), int(m.group(2)) + 1)]
        else: out += [x.strip('«»') for x in re.split(r'\s*[–—-]\s*', piece) if x]
    return out
def items(chunk):
    """ссылка → [(уровни {ст, ч, п, подп}, хвост — название акта), …], текст до первой нормы"""
    ms = list(LVL.finditer(chunk)); out = []; cur = None; prev = None
    for i, m in enumerate(ms):
        k = m.group('k').lower(); k = 'подп.' if k.startswith('подп') else 'п.' if k.startswith(('п.', 'пп', 'пункт')) else 'ч.' if k.startswith('ч') else 'ст.' if k.startswith('ст') else k; o = ORDER[k]
        if cur is None or o <= prev or chunk[ms[i - 1].end():m.start()].strip(' ,'):
            cur = {'s': m.start(), 'e': m.end(), 'lv': {}}; out.append(cur)
        cur['lv'].setdefault({-1: 'абз', 0: 'подп', 1: 'п', 2: 'ч', 3: 'ст'}[o], []).extend(vlist(m.group('v'))); cur['e'] = m.end(); prev = o
    for i in range(len(out) - 2, -1, -1):                                  # «п. 21 ч. 1 и ч. 2 ст. 11»: статья общая
        if 'ст' not in out[i]['lv'] and 'ст' in out[i + 1]['lv'] and chunk[out[i]['e']:out[i + 1]['s']].strip(' ,') in ('', 'и'):
            out[i]['lv']['ст'] = out[i + 1]['lv']['ст']
    res = []
    for i, it in enumerate(out):
        tail = chunk[it['e']:out[i + 1]['s'] if i + 1 < len(out) else len(chunk)]
        res.append((it['lv'], tail))
    if re.search(r'[Пп]римечани', chunk) and res:
        for lv, tail in res: lv['прим'] = True
    return res, (chunk[:out[0]['s']] if out else chunk)

def get_units(act, lv, ctxart, st, ctxpt=None):
    """норма ищется в выбранной копии акта, а если там её нет — в других копиях того же акта"""
    if isinstance(act, str): return get_units1(act, lv, ctxart, st, ctxpt)
    r = None
    for c in copies(act):
        r = get_units1(c, lv, ctxart, st, ctxpt)
        if r: return r
    return r
def get_units1(act, lv, ctxart, st, ctxpt=None):
    """тексты нормы; None — нормы в акте нет; [] — определить нельзя (нет статьи для части или пункта)"""
    if isinstance(act, str) and act == 'gk':
        act = CODE.get(gkpart((lv.get('ст') or [ctxart or '1'])[0]))
        if not act: return None
    arts = lv.get('ст'); ps = lv.get('п') or []; cs = lv.get('ч') or []; ss = lv.get('подп') or []
    if articled(act):
        A = L.articles(act['path'])
        if not arts:
            if not ctxart: return []
            arts = [ctxart]
        us = []
        for a in arts:
            b = A.get(a)
            if b is None: return None
            if len(arts) > 1: us.append(b); continue
            if lv.get('прим'):
                P = L.parts(b); us.append(P.get('прим') or b); continue
            if not (cs or ps or ss): us.append(b); continue
            P = L.parts(b); numbered = [k for k in P if k != 'прим']
            level1 = []
            if cs:
                for c in cs:
                    if c in P: level1.append(P[c])
                    elif not numbered: level1.append(b)
                    else: return None
            else: level1 = [b]
            if ps:
                l2 = []
                for u in level1:
                    for p in ps:
                        pu = L.point(u, p); pp = P.get(p) if not cs else None  # «п. 2 ст. 21» закона, где пункты нумеруются «2.»
                        if pp is not None and (ss or pu is None): l2.append(pp)
                        elif pu is not None:
                            l2.append(pu)
                            if pp is not None: l2.append(pp)
                        else: return None
                level1 = l2
            if ss:
                l3 = []
                for u in level1:
                    for s_ in ss:
                        su = L.point(u, s_)
                        if su is None: return None
                        l3.append(su)
                level1 = l3
            us += level1
            if 'прим' in P and len(P['прим']) < 6000: us.append(P['прим'])     # размеры и сроки часто раскрыты в примечаниях к статье
        return us
    if arts or cs: return None
    us = []
    if ss and not ps:
        if not ctxpt: return []
        ps = [ctxpt]
    for p in ps or ss:
        cands = L.act_points(act['path'], p)
        if not cands: return None
        if ps and ss:
            ok_ = [c for c in cands if all(L.point(c, s_) for s_ in ss)]
            if ok_: cands = ok_
        u = max(cands, key=lambda c: len(st & L.stems(c)) / (1 + len(c) / 6000.0))
        if ps and ss:
            for s_ in ss:
                su = L.point(u, s_)
                if su is None:
                    c2 = L.act_points(act['path'], p + '.' + s_)
                    su = max(c2, key=lambda c: len(st & L.stems(c))) if c2 else None
                if su is None: return None
                us.append(su)
        else: us.append(u)
    return us

def window(u, st, w):
    if len(u) <= w: return u
    bestp, bests = 0, -1
    for p in range(0, max(1, len(u) - w + 1), 80):
        sc = len(st & L.stems(u[p:p + w]))
        if sc > bests: bestp, bests = p, sc
    return ('…' if bestp else '') + u[bestp:bestp + w] + '…'

CH = re.compile(r'//(.+?)//')
PLAIN = re.compile(r'от \d{2}\.\d{2}\.\d{4}(?: г\.)? № ?[\w./-]+')
MONTHS = {'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04', 'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08', 'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'}
ORDW = {'перв': 1, 'втор': 2, 'трет': 3, 'четв': 4, 'пят': 5, 'шест': 6, 'седьм': 7, 'восьм': 8, 'девят': 9, 'десят': 10, 'одиннадцат': 11, 'двенадцат': 12, 'тринадцат': 13, 'четырнадцат': 14, 'пятнадцат': 15}
def wordform(s):
    """словесная запись → краткая: «17 марта 2004 года» → «17.03.2004», «части первой» → «ч. 1» (число строк не меняется)"""
    s = re.sub(r'(?<!\d)(\d{1,2}) (%s) (\d{4}) года' % '|'.join(MONTHS), lambda m: '%02d.%s.%s' % (int(m.group(1)), MONTHS[m.group(2)], m.group(3)), s)
    def o(m):
        w = m.group(2).lower()
        for k in sorted(ORDW, key=len, reverse=True):
            if w.startswith(k): return 'ч. %d' % ORDW[k]
        return m.group(0)
    return re.sub(r'(?<![А-ЯЁа-яё])(част[ьию]|частью|частями) ((?:перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|десят|одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат)[а-яё]{2,3})(?![а-яё])', o, s)


PLAIN2 = re.compile(r'Конституци\w+|КоАП РФ|УПК РФ|(?<![А-ЯЁа-яё])УК РФ|ГПК РФ|(?<![А-ЯЁа-яё])ТК РФ|КАС РФ|(?<![А-ЯЁа-яё])ГК РФ|Закон\w* о полиции|(?:[Зз]акон|[Пп]равил|[Нн]аставлени|[Ии]нструкци|[Пп]орядк|[Пп]оложени|[Пп]риказ|[Уу]каз|[Пп]остановлени|[Рр]егламент|[Уу]став)\w*\s(?:[^.;()№]{0,60}?)№ ?\d[\w./-]*')
ABBR = re.compile(r'(?:^|[\s(«])(?:ст|п|ч|т|д|г|гг|руб|подп|утв|см|др|пр|абз|рис|им|ред|тыс|млн|стр|с|ср|напр)\.$')
def sentences(line):
    parts = re.split(r'(?<=[.!?…;])\s+(?=[А-ЯЁ«*\x00"(])|(?<=;)\s+', line); out = []; buf = ''
    for p in parts:
        buf = (buf + ' ' + p) if buf else p
        if ABBR.search(buf) and not buf.endswith(';'): continue
        out.append(buf); buf = ''
    if buf: out.append(buf)
    return out
def clean(s):
    s = CH.sub(' ', s); s = re.sub(r'\d{2}\.\d{2}\.\d{4}', ' ', s); s = re.sub(r'№ ?[\w./-]+', ' ', s)
    s = re.sub(r'(?<![А-ЯЁа-яё])(?:ст|п|ч|гл|подп|абз|разд|пп)\.\s*\d[\d.,–\- и]*', ' ', s, flags=re.I)
    s = re.sub(r'^\s*(?:[-*>]\s*)?(?:\*\*)?\d+[.)]\s', ' ', s); s = re.sub(r'\b(?:19|20)\d\d\s*(?=г\.|год)', ' ', s)
    return s

RAWN = {}; ALIAS = {}
stat = collections.Counter(); unk = collections.Counter(); other = []; blocks = []
files = sorted(glob.glob(os.path.join(ANS, '*.txt')))
if QRE: files = [f for f in files if re.search(QRE, os.path.basename(f))]
for f in files:
    fid = os.path.basename(ANS.rstrip('/')) + '/' + os.path.basename(f)[:-4]
    named = []                         # [(акт, основы слов названия и сокращения)]
    RAWN.clear(); ALIAS.clear(); PTMEM = {}
    secart = None; leadart = None; lastkind = None; FIRST = []   # FIRST: акты в порядке первого упоминания
    ctx = None; ctxart = None; lead = None; ARTMEM = []   # ARTMEM: [(акт, последняя названная статья)]
    def note(act, txt):
        st = hstems(txt) | {x.upper() for x in re.findall(r'№ ?([\w./-]+)', txt)}
        if not isinstance(act, str):
            RAWN[id(act)] = RAWN.get(id(act), '') + ' ' + txt
            al_ = re.search(r'далее\s*[—–-]\s*(.+)', txt)
            if al_: ALIAS[id(act)] = ALIAS.get(id(act), set()) | (hstems(al_.group(1)) - GENERIC)
        for i, (a, s_) in enumerate(named):
            if a is act or (isinstance(a, str) and a == act): st |= s_; named.pop(i); break
        named.append((act, st))
        if not isinstance(act, str) and all(act is not f_ for f_ in FIRST): FIRST.append(act)
    for ln, line in enumerate(wordform(open(f, encoding='utf-8').read()).split('\n'), 1):
        raw = line.strip()
        if not raw: continue
        ishead = raw.startswith('#'); n0 = len(ARTMEM)
        if ishead: lead = None; leadart = None
        firstact = None
        for ch_ in CH.findall(raw):
            its_, head_ = items(ch_)
            for t_ in [head_] + [t2 for l2, t2 in its_]:
                r_ = resolve(t_, named) if t_.strip() else None
                if r_ is not None and not (isinstance(r_, str) and r_.startswith('unk:')) and firstact is None: firstact = r_
        islist = bool(re.match(r'^(?:[-*•]|\d+[.)])\s', raw)) and not raw.startswith('**')
        if not islist: lead = None; leadart = None
        lineunits = []; linerefs = False
        chunks = CH.findall(raw); body = CH.sub(lambda m: '\x00', raw)
        ci = 0
        for sent in sentences(body):
            k = sent.count('\x00'); mine = chunks[ci:ci + k]; ci += k
            it_ = iter(mine); full = re.sub('\x00', lambda m: '//' + next(it_) + '//', sent)
            st = L.stems(clean(full)); refs = []; sunits = []; bad = False; missing = []; alts = []
            # события по порядку: ссылки и упоминания актов в обычном тексте
            ev = [(m.start(), 'c', m.group(1)) for m in CH.finditer(full)]
            plain = CH.sub(lambda m: ' ' * len(m.group()), full)
            ev += [(m.start(), 'p', plain[max(0, m.start() - 90):m.end() + 60]) for m in PLAIN.finditer(plain)]
            seen_ = [e[0] for e in ev if e[1] == 'p']
            for m in PLAIN2.finditer(plain):
                if not any(m.start() <= s_ <= m.end() + 12 for s_ in seen_): ev.append((m.start(), 'p', m.group()))
            for pos, kind, txt in sorted(ev):
                after = full[pos:][len(txt) + 4 if kind == 'c' else 0:][:160]
                al = re.search(r'\(далее\s*[—–-]\s*([^)]{2,90})\)', after if kind == 'c' else txt + after)
                if kind == 'p':
                    act = resolve(txt, named)
                    if act is not None:
                        note(act, txt + (' далее — ' + al.group(1) if al else '')); ctx = act; ctxart = None; lastkind = 'act'
                    continue
                its, head = items(txt)
                if not its:
                    act = resolve(txt, named)
                    if act is not None:
                        note(act, txt + (' далее — ' + al.group(1) if al and al.start() < 6 else '')); ctx = act; ctxart = None; lastkind = 'act'
                        if isinstance(act, str) and act.startswith('unk:'): unk[act[4:]] += 1
                    continue
                headact = resolve(head, named) if head.strip() else None
                racts = [resolve(tail, named) for lv, tail in its]
                for i_ in range(len(racts) - 2, -1, -1):
                    if racts[i_] is None and racts[i_ + 1] is not None and not its[i_][1].strip(' ,;и'): racts[i_] = racts[i_ + 1]
                for (lv, tail), act in zip(its, racts):
                    if act is None and headact is not None: act = headact
                    explicit = act is not None
                    label = ' '.join('%s %s' % (k_, ','.join(v)) for k_, v in [(x, lv[x]) for x in ('подп', 'п', 'ч', 'ст') if x in lv])
                    if explicit:
                        note(act, tail if tail.strip() else head)
                        if isinstance(act, str) and act.startswith('unk:'):
                            unk[act[4:]] += 1; bad = True; ctx = act; ctxart = None; lastkind = 'act'; refs.append(label + ' ← ' + act); continue
                        cands = [(act, next((a2 for (c2, a2, p2) in ARTMEM[::-1] if c2 is act), None), None)]
                    else:
                        cands = []; isunk = isinstance(ctx, str) and ctx.startswith('unk:')
                        def add(c, a2=None, p2=None):
                            if c is None or (isinstance(c, str) and c.startswith('unk:')): return
                            if all(not (c is x_[0] and a2 == x_[1]) for x_ in cands): cands.append((c, a2, p2))
                        mem = []
                        for c2, a2, p2 in ARTMEM[::-1]:
                            if all(not (c2 is m_[0] and a2 == m_[1]) for m_ in mem): mem.append((c2, a2, p2))
                        if 'ст' in lv:
                            add(ctx); add(CODE.get(DEF) if DEF != 'gk' else 'gk')
                            for a_, s_ in named[::-1]: add(a_)
                        elif 'ч' in lv:
                            if len(ARTMEM) > n0: add(*mem[0])                # статья, названная в этой же строке
                            for m_ in (leadart, secart): 
                                if m_: add(*m_)
                            for m_ in mem[:5]: add(*m_)
                        else:
                            if isunk and lastkind != 'art':
                                unk[ctx[4:]] += 1; bad = True; refs.append(label + ' ← ' + ctx); continue
                            c0 = ctx if ctx is not None else firstact
                            if lastkind != 'art' and c0 is not None and not isinstance(c0, str) and not articled(c0): add(c0)
                            if len(ARTMEM) > n0: add(*mem[0])
                            for m_ in (leadart, secart):
                                if m_: add(*m_)
                            if c0 is not None and not isinstance(c0, str) and articled(c0):
                                m0 = next((m_ for m_ in mem if m_[0] is c0), None)
                                if m0: add(*m0)
                            elif c0 is not None: add(c0)
                            for m_ in mem[:3]: add(*m_)
                            for a_, s_ in named[::-1]:
                                if not isinstance(a_, str) and not articled(a_): add(a_)
                    tried = []
                    for c, ca, cp in cands:
                        us = None
                        if cp and 'ч' not in lv and 'ст' not in lv and ('п' in lv or 'подп' in lv):
                            lv2 = dict(lv); lv2['ч'] = [cp]; us = get_units(c, lv2, ca, st, PTMEM.get(id(c)))
                        if not us: us = get_units(c, lv, ca, st, PTMEM.get(id(c)))
                        tried.append((c, us))
                    def score(us_): return sum(len(st & L.stems(u)) / (1 + len(u) / 6000.0) for u in us_)
                    ex = [(c, us) for c, us in tried if us]; prim = None
                    if ex:
                        prim = ex[0]
                        if not explicit:                                       # из первых трёх подходящих — та, где слов предложения заметно больше
                            for cand_ in ex[1:3]:
                                if score(cand_[1]) >= score(prim[1]) + 2: prim = cand_
                    if prim is None:
                        if any(us == [] for c, us in tried[:1]): bad = True; refs.append(label + ' ← ? (нет статьи для части или пункта)'); stat['без привязки'] += 1
                        else: missing.append(label + ' ← ' + short(tried[0][0] if tried else None)); refs.append(label + ' ← ' + short(tried[0][0] if tried else None))
                        continue
                    act, us = prim
                    if 'ст' in lv and len(lv['ст']) == 1:
                        ctxart = lv['ст'][0]; ARTMEM.append((act if not isinstance(act, str) else CODE.get(gkpart(ctxart)), ctxart, lv['ч'][0] if len(lv.get('ч', [])) == 1 else None))
                    elif 'ч' in lv and len(lv['ч']) == 1 and not isinstance(act, str):
                        a0 = next((m_ for m_ in ARTMEM[::-1] if m_[0] is act), None)
                        if a0: ARTMEM.append((act, a0[1], lv['ч'][0]))
                    ctx = act; lastkind = 'art' if (not isinstance(act, str) and articled(act)) or isinstance(act, str) else 'act'
                    if 'п' in lv and len(lv['п']) == 1 and not isinstance(act, str): PTMEM[id(act)] = lv['п'][0]
                    sunits += us; refs.append(label + ' ← ' + short(act))
                    if not explicit: alts.append([(c, u2) for c, u2 in tried if u2 and c is not act])
            if ishead: continue
            if not refs:
                if islist and lead and lead[0]:
                    an = L.nums(clean(full), True) - {1}
                    if an:
                        stat['пунктов списка'] += 1
                        un = set().union(*[L.nums(L.strip_marks(u)) for u in lead[0]])
                        if an - un:
                            stat['пунктов списка с пометкой'] += 1
                            blocks.append((fid, ln, 'СПИСОК ЧИСЛО ' + ' '.join(map(str, sorted(an - un))), lead[1], full, lead[0], st))
                continue
            linerefs = True; lineunits += sunits
            if bad and not sunits: stat['не сверено: акт не найден'] += 1; continue
            stat['предложений'] += 1
            flags = []; covs = ''
            if missing: flags.append('НЕТ ' + '; '.join(missing))
            if sunits and not bad:
                an = L.nums(clean(full), True) - {1}
                un = set().union(*[L.nums(L.strip_marks(u)) for u in sunits])
                miss = an - un
                if miss:
                    found = None
                    for alt in alts:
                        for c, u2 in alt:
                            if miss <= set().union(*[L.nums(L.strip_marks(u)) for u in u2]): found = c; break
                        if found: break
                    if found is not None and not isinstance(found, str): other.append('%s:%d  %s  числа %s — в %s' % (fid, ln, '; '.join(refs)[:150], ' '.join(map(str, sorted(miss))), short(found))); stat['ДРУГОЙ'] += 1
                    else: flags.append('ЧИСЛО ' + ' '.join(map(str, sorted(miss))))
                if len(st) >= 6:
                    us_ = set().union(*[L.stems(u) for u in sunits]); cov = len(st & us_) / len(st)
                    if cov < THR: flags.append('СЛОВА %d%%' % round(cov * 100))
                    covs = ' {%d%%}' % round(cov * 100)
            if flags: stat['предложений с пометкой'] += 1
            if flags or ALL: blocks.append((fid, ln, (' | '.join(flags) or 'ок') + (covs if COVP else ''), '; '.join(refs), full, sunits, st))
        if ishead:                                                     # статья в заголовке раздела — основная для «ч. N» без статьи в этом разделе
            hits_ = []
            for lv_, tail_ in items(raw.replace('//', ''))[0]:
                if 'ст' in lv_:
                    a_ = resolve(tail_, named)
                    cs_ = [a_] if (a_ is not None and not isinstance(a_, str)) else [ctx, CODE.get(DEF)] + FIRST
                    for s_ in lv_['ст']:
                        for c_ in cs_:
                            if c_ is not None and not isinstance(c_, str) and get_units(c_, {'ст': [s_]}, None, set()):
                                hits_.append((c_, s_, lv_['ч'][0] if len(lv_.get('ч', [])) == 1 else None)); break
            secart = hits_[0] if len(hits_) == 1 else None
            if secart: ARTMEM.append(secart); ctx = secart[0]; ctxart = secart[1]; lastkind = 'art'
            continue
        if raw.endswith(':') and linerefs:
            lead = (lineunits, 'под строкой %d' % ln)
            if len(ARTMEM) > n0: leadart = ARTMEM[-1]
        elif not islist: lead = None

for fid, ln, fl, refs, full, us, st in blocks:
    if ONLY and ONLY not in fl: continue
    print('%s:%d  %s  [%s]' % (fid, ln, fl, refs[:230]))
    print('   ' + full[:SLEN])
    for u in us[:4]: print('      → ' + window(L.strip_marks(u) if len(u) > WIN else u, st, WIN))
    print()
if other:
    print('== ДРУГОЙ: число найдено в другом акте, названном в ответе')
    for o in other: print(o)
print('-- сверено предложений: %d; с пометкой: %d; пунктов списков: %d, с пометкой: %d; число в другом акте: %d; без привязки: %d; не сверено (акта нет среди текстов): %d'
      % (stat['предложений'], stat['предложений с пометкой'], stat['пунктов списка'], stat['пунктов списка с пометкой'], stat['ДРУГОЙ'], stat['без привязки'], stat['не сверено: акт не найден']))
if unk: print('-- акты, не найденные среди текстов: ' + '; '.join('%s ×%d' % kv for kv in unk.most_common()))
