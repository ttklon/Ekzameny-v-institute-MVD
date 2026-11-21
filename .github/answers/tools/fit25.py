#!/usr/bin/env python3
"""fit25.py sim | show N… | apply [N…] | propose — сокращение варианта 2 до 25 часов (150 тыс. слов в едином документе).

Исходник — всегда редакция REV (по умолчанию 4b36cfb, проверенный текст на 36 часов), поэтому apply можно повторять;
после apply запускается fit25_hand.py.

Единица текста:
  • абзац; отдельный пункт-факт («- **Срок:** …»);
  • перечень целиком — вводная строка с двоеточием и все её пункты, ряд «ч. 1, ч. 2…», ряд «термин — определение»,
    ряд «по …», нумерованный список, ряд «Первое… Второе…». Перечень остаётся со всеми членами или убирается целиком.
Внутри единицы допускается одно: оставить начало строки (первые целые предложения) и снять концовку целыми предложениями.

Порядок отбора в каждом ответе:
  1. остаются определения («> »), предложения с «(далее — …)», блок «Главное для запоминания» без изменений;
  2. ручные решения fit25_over.txt («N ! ## заголовок» — начала всех пунктов раздела; «N + строка»; «N - строка или раздел»);
  3. опоры блока: пункт, где стоит ссылка блока (статья + часть/пункт); полное название каждого акта; слова и числа
     каждого предложения блока; предложение блока с опорой меньше BSUP получает ещё один опорный пункт;
  4. возврат остального до цели ответа «по уровню»: каждый раз берётся лучший пункт раздела, от которого осталась
     наименьшая доля (второстепенным разделам и «Правовой основе» доля меньше);
  5. ни один раздел не пропадает целиком, кроме второстепенных, которых нет ни в вопросе, ни в блоке.
Связи: предложение-отсылка («Это», «Такие»…) тянет предыдущее; неполная ссылка («ч. 2», «ст. 17») тянет текст, который
задаёт ей акт и статью; абзац без заголовка тянет абзац с заголовком; перечень тянет строку, под которой стоит.
Цель ответа: размер^TPOW × средний^(1−TPOW) × k; k подбирается так, чтобы сумма равнялась TOTAL (слов в исходниках)."""
import os, sys, re, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(os.path.join(HERE, '..'))
import cut25 as C
TOTAL = float(os.environ.get('TOTAL', 148200))   # слов в txt; единый docx добавляет около 2 150 слов (титул, оглавление)
BSUP = float(os.environ.get('BSUP', 0.5)); ALEN = float(os.environ.get('ALEN', 0.002)); ATHR = float(os.environ.get('ATHR', 0.22)); NANCH = int(os.environ.get('NANCH', 0)); TPOW = float(os.environ.get('TPOW', 0.5)); PBKEEP = int(os.environ.get('PBKEEP', 0)); FLOOR = float(os.environ.get('FLOOR', 0))
REV = os.environ.get('REV', '4b36cfb')              # исходник — проверенная редакция на 36 часов; apply всегда строит заново от неё
import subprocess, functools
@functools.lru_cache(None)
def src(q): return subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (REV, q)], capture_output=True, text=True).stdout
wc = lambda s: len(s.split())
ST = lambda s: {w[:6] for w in re.findall(r'[а-яё]{5,}', s.lower().replace('ё', 'е'))}
ARTS = lambda s: {'#' + a for a in re.findall(r'(?:ст|п|ч)\. (\d+(?:\.\d+)*)', s)} | {'#' + a for a in re.findall(r'\b(\d{2,}(?:[ .]\d{3})*)\b', s)}
STOP = ST('полиции полиция российской федерации закона закон федерального федеральный статья также которые которых является могут может должен должны лица лицо органов органы внутренних дел сотрудник сотрудника сотрудники административного административных административной правонарушениях правонарушения кодекса главное запоминания далее только случае случаях порядке порядок числе россии')
PERI = re.compile(r'отграничен|отлич|смежн|взаимодейств|гаранти|проблем|практическ|(?<![Нн]а)значени|соотношен|обжалован|оформлен|история|перспектив|статистик|последстви|ошибк|разъяснени|пример|иные |другие |други[хм] ', re.I)
CORE = re.compile(r'(основани|порядок|срок|вид[ыа]? |понят|признак|субъект|объект|состав|полномочи|права|право |обязанност|запрет|услови|цел[ьи]|задач|функци|принцип|кто |структур|систем|форм|мер[ыа] |содержани)')
SEQ = re.compile(r'(?:- |\d+\. )?\*\*(//)?(Ч\.|Ст\.|П\.|Подп\.|Гл\.|Часть|Статья|Пункт|Глава|Перв|Втор|Трет|Четв|Пят|Шест|Седьм|Восьм|Девят|Десят|\d)')
PB = re.compile(r'равовая основа|равовое регулирование|ормативн\w+ (основ|закреплен)|онституционн\w+ (и законодательн\w+ )?основ')
PRE = re.compile(r'^(\s*- |\d+\. )?(.*)$', re.S)
ORD = re.compile(r'\*\*(Перв|Втор|Трет|Четв[её]рт|Пят|Шест|Седьм|Восьм|Девят|Десят)\w*[.:*]')
def kind(l):
    if l.startswith('> '): return 'def'
    if l.startswith('  - '): return 'sub'
    if l.startswith('- '): return 'li'
    if re.match(r'\d+\. ', l): return 'num'
    return 'p'
def litype(l):
    b = l[2:] if l.startswith('- ') else l
    if kind(l) == 'num' or SEQ.match(l): return 'S'
    if re.match(r'\*\*[^*]{1,60}\*\* —', b): return 'T'
    if re.match(r'\*\*По ', b): return 'B'
    if b.rstrip().endswith(';') or (b[:1].islower() or b[:1] == '«') and not b.startswith('**'): return 'E'
    return 'F'
def sents(line):
    """(префикс, [предложения]) — предложения сцеплены так, чтобы кавычки, скобки и ссылки были парными"""
    m = PRE.match(line); pre = m.group(1) or ''; raw = [x.strip() for x in C.split_sent(m.group(2))]; out = []
    for s in raw:
        if out and (re.fullmatch(r'\*\*[^*]+\*\*[:.]?', out[-1]) or out[-1].count('«') != out[-1].count('»') or out[-1].count('//') % 2
                    or out[-1].count('(') != out[-1].count(')') or out[-1].count('**') % 2 or wc(s) < 5 or re.match(r'\(//', s)):
            out[-1] += ' ' + s
        else: out.append(s)
    return pre, out
def headlen(ss):
    tot = sum(wc(s) for s in ss)
    if tot <= 22 or len(ss) < 2: return len(ss)
    n = 0; k = 0
    for s in ss:
        k += 1; n += wc(re.sub(r'^\*\*[^*]+\*\*', '', s))
        if n >= 10: break
    if tot - sum(wc(s) for s in ss[:k]) < 8: return len(ss)
    return k
class U:
    def __init__(s, lines, sec, grp): s.lines = lines; s.sec = sec; s.grp = grp; s.par = None
    @property
    def text(s): return ' '.join(s.lines)
class It:
    """head — начала всех строк единицы; tail — одно предложение концовки строки"""
    def __init__(s, u, kd, parts): s.u = u; s.kd = kd; s.parts = parts; s.keep = False; s.why = ''; s.deps = set()
    @property
    def text(s): return ' '.join(t for _, _, t in s.parts)
    @property
    def w(s): return wc(s.text)
def parse(q):
    L = src(q).split('\n')
    title = L[0]; blk = next((l for l in L if l.startswith('!! ')), ''); secs = []
    for l in L[1:]:
        if l.startswith('!! ') or not l.strip(): continue
        if l.startswith('## '): secs.append((l, [])); continue
        if not secs: secs.append(('', []))
        secs[-1][1].append(l)
    units = []
    for si, (h, ls) in enumerate(secs):
        counted = bool(C.COUNT.search(h.lower())); i = 0
        while i < len(ls):
            l = ls[i]; k = kind(l)
            if k == 'def': units.append(U([l], si, 'def')); i += 1; continue
            if k == 'p':
                j = i + 1
                if l.rstrip().rstrip('*').rstrip().endswith(':') or (C.COUNT.search(l.lower()) and j < len(ls) and kind(ls[j]) != 'p'):
                    while j < len(ls) and kind(ls[j]) in ('li', 'sub', 'num'): j += 1
                    if j > i + 1: units.append(U(ls[i:j], si, 'list')); i = j; continue
                if ORD.match(l):                            # «Первое… Второе…» — один перечень, из середины не режется
                    while j < len(ls) and kind(ls[j]) == 'p' and ORD.match(ls[j]): j += 1
                    if j > i + 1: units.append(U(ls[i:j], si, 'list')); i = j; continue
                units.append(U([l], si, 'p')); i += 1; continue
            j = i; n0 = len(units); par = n0 - 1 if i and kind(ls[i - 1]) == 'p' and units and units[-1].sec == si and units[-1].grp == 'p' else None
            while j < len(ls) and kind(ls[j]) in ('li', 'sub', 'num'): j += 1
            run = ls[i:j]; i = j
            if counted and not any(u.sec == si and u.grp != 'def' for u in units): units.append(U(run, si, 'list')); continue
            items = []; a = 0
            while a < len(run):
                b = a + 1
                while b < len(run) and kind(run[b]) == 'sub': b += 1
                items.append((litype(run[a]), run[a:b])); a = b
            typed = [k for k, (t, _) in enumerate(items) if t != 'F']
            lo, hi = (typed[0], typed[-1]) if len(typed) >= 2 else (None, None); k = 0
            while k < len(items):
                if lo is not None and k == lo:
                    units.append(U([x for _, ls_ in items[lo:hi + 1] for x in ls_], si, 'list')); k = hi + 1; continue
                units.append(U(items[k][1], si, 'fact')); k += 1
            for u in units[n0:]: u.par = par                # перечень без двоеточия во вводной строке всё равно держит строку, под которой стоит
    return title, secs, units, blk
def over():
    o = {}; p = os.path.join(HERE, 'fit25_over.txt')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            m = re.match(r'(\d+) ([+-]) (.+)', l.rstrip('\n'))
            if m: o.setdefault(int(m.group(1)), []).append((m.group(2), m.group(3)))
    return o
OVER = over()
def secprio():                                             # строки «N ! ## заголовок» (главный раздел) и «N ? ## заголовок» (второстепенный)
    o = {}; p = os.path.join(HERE, 'fit25_over.txt')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            m = re.match(r'(\d+) ([!?]) ## (.+)', l.rstrip('\n'))
            if m: o.setdefault(int(m.group(1)), []).append((m.group(3), 2.2 if m.group(2) == '!' else 0.3))
    return o
SECPRIO = secprio()
hm = lambda h, p: h == p[:-1] if p.endswith('$') else h.startswith(p)      # «$» в конце — заголовок целиком
for _q, _l in SECPRIO.items():
    _h = [re.sub(r'^## \d+\.\s*', '', l) for l in src(_q).split('\n') if l.startswith('## ')]
    for _p, _v in _l: assert sum(1 for h in _h if hm(h, _p)) == 1, 'q%03d: раздел «%s» найден %d раз' % (_q, _p, sum(1 for h in _h if hm(h, _p)))
def targets(total):
    body = {q: wc(src(q)) for q in range(1, 150)}
    mean = sum(body.values()) / 149; raw = {q: body[q] ** TPOW * mean ** (1 - TPOW) for q in body}; k = total / sum(raw.values())
    return {q: raw[q] * k for q in body}
def plan(q, target):
    title, secs, units, blk = parse(q)
    pbsec = {si for si, (h, _) in enumerate(secs) if PB.search(h)}
    # элементы
    items = []; head = {}; order = []                       # order: (id элемента, текст предложения) в порядке текста
    lines = {}                                               # (u, k) -> (pre, [предложения], длина начала)
    for ui, u in enumerate(units):
        hp = []; tails = []
        for k, l in enumerate(u.lines):
            if u.grp == 'def': pre, ss = PRE.match(l).group(1) or '', [PRE.match(l).group(2)]; h = 1
            elif u.sec in pbsec:
                pre, ss = sents(l); h = 1 if len(ss) > 1 and sum(wc(x) for x in ss[1:]) >= 8 else len(ss)
            else: pre, ss = sents(l); h = headlen(ss)
            lines[(ui, k)] = (pre, ss, h)
            for j in range(h): hp.append((k, j, ss[j]))
            for j in range(h, len(ss)): tails.append((k, j, ss[j]))
        hi = len(items); items.append(It(ui, 'head', hp)); head[ui] = hi
        prev = {}
        for k, j, s in tails:
            ti = len(items); it = It(ui, 'tail', [(k, j, s)]); it.deps.add(prev.get(k, hi)); prev[k] = ti; items.append(it)
    idx = {}
    for ii, it in enumerate(items):
        for k, j, s in it.parts: idx[(it.u, k, j)] = ii
    for ui, u in enumerate(units):
        for k in range(len(u.lines)):
            for j, s in enumerate(lines[(ui, k)][1]): order.append((idx[(ui, k, j)], s, ui))
    # связи: ссылки, отсылки, абзац без заголовка
    sec = None
    for ii, s, ui in order:
        if units[ui].sec != sec: sec = units[ui].sec; act_set = art_set = None
        for m in C.REF.finditer(s):
            a, s_, d = C.ref_ctx(m.group(1))
            if a: act_set = ii; art_set = ii if s_ else None
            else:
                if act_set is not None and act_set != ii: items[ii].deps.add(act_set)
                if s_: art_set = ii
                elif art_set is not None and art_set != ii: items[ii].deps.add(art_set)
    ana = lambda s: bool(C.ANA.match(re.sub(r'^(\*\*)?', '', s)))
    lab = None
    for ui, u in enumerate(units):
        if ui and units[ui - 1].sec != u.sec: lab = None
        first = lines[(ui, 0)][1][0]
        if ui and units[ui - 1].sec == u.sec and ana(first) and units[ui - 1].grp != 'def': items[head[ui]].deps.add(head[ui - 1])
        if u.par is not None: items[head[ui]].deps.add(head[u.par])
        if u.grp == 'p':
            if first.startswith('**'): lab = ui
            elif lab is not None: items[head[ui]].deps.add(head[lab])
        else: lab = None
    def closure(i):
        seen = set(); st = [i]
        while st:
            k = st.pop()
            if k in seen: continue
            seen.add(k); st += list(items[k].deps)
        return seen
    # токены
    tt = ST(re.sub(r'^# Вопрос \d+\.', '', title)) - STOP; df = {}; toks = []
    for it in items:
        t = (ST(it.text) - STOP) | ARTS(it.text); toks.append(t)
        for x in t: df[x] = df.get(x, 0) + 1
    wt = lambda x: 1.0 / df.get(x, 1)
    for ii, it in enumerate(items):
        u = units[it.u]
        if u.grp == 'def': it.keep = True; it.why = 'опр'
        elif PBKEEP and u.sec in pbsec and it.kd == 'head': it.keep = True; it.why = 'ПО'
        elif '(далее —' in it.text: it.keep = True; it.why = 'далее'
    banned = set(); manual = set()
    for sign, pref in OVER.get(q, []):
        if pref.startswith('## '): hit = [i for i, it in enumerate(items) if re.sub(r'^## \d+\.\s*', '', secs[units[it.u].sec][0]).startswith(pref[3:])]
        else: hit = [i for i, it in enumerate(items) if any(l.startswith(pref) for l in units[it.u].lines)]
        assert hit, 'q%03d: нет строки «%s»' % (q, pref)
        for i in hit:
            if sign == '+': manual.add(i)
            elif units[items[i].u].grp != 'def' and '(далее —' not in items[i].text: banned.add(i)
    for i in banned: items[i].keep = False; items[i].why = 'руч−'
    for si, (h, _) in enumerate(secs):                     # «!» — от главного раздела остаются начала всех пунктов
        if any(v > 1 and hm(re.sub(r'^## \d+\.\s*', '', h), pref) for pref, v in SECPRIO.get(q, [])):
            for i, it in enumerate(items):
                if units[it.u].sec == si and it.kd == 'head' and i not in banned: it.keep = True; it.why = it.why or 'руч!'
    # опоры блока — среди того, что не убрано вручную
    bs = [s for s in C.split_sent(re.sub(r'^!! \*\*Главное для запоминания\.\*\*\s*', '', blk)) if s.strip()]; btok = set()
    for s in bs:
        need = (ST(s) - STOP) | ARTS(s); btok |= need
        need = {x for x in need if x in df}; tot = sum(wt(x) for x in need) or 1
        for _ in range(NANCH):
            val = lambda i: sum(wt(x) for x in need & toks[i]) / (1 + ALEN * items[i].w)
            best = max((i for i in range(len(items)) if i not in banned and units[items[i].u].sec not in pbsec), key=val, default=None)
            if best is None or sum(wt(x) for x in need & toks[best]) < ATHR * tot:      # в тексте опоры нет — ищем в «Правовой основе»
                best = max((i for i in range(len(items)) if i not in banned), key=val, default=None)
            if best is None: break
            got = sum(wt(x) for x in need & toks[best])
            if got < ATHR * tot or got == 0: break
            if not items[best].keep: items[best].keep = True; items[best].why = 'блок'
            need -= toks[best]
    for i in manual: items[i].keep = True; items[i].why = 'руч'
    for i in range(len(items)):
        if items[i].keep:
            for k in closure(i):
                if not items[k].keep and k not in banned: items[k].keep = True; items[k].why = 'связь'
    secw = {}; ancw = {}
    for it in items:
        s_ = units[it.u].sec; secw[s_] = secw.get(s_, 0) + it.w
        if it.why in ('блок', 'руч'): ancw[s_] = ancw.get(s_, 0) + it.w
    # ссылка блока (статья + часть/пункт) должна остаться и в тексте: возвращаем самый короткий пункт, где она стояла
    def refkeys(lns):
        pieces = [((i, 0), l) for i, l in enumerate(lns) if l.strip()]; res, _ = C.resolve(pieces); out = {}
        for (i, _z), line in pieces:
            for k, m in enumerate(C.REF.finditer(line)):
                act, art = res[((i, 0), k)]; r = m.group(1)
                arts = re.findall(r'[Сс]т\.\s*(\d+(?:\.\d+)*)', r) or ([art] if art else [])
                parts = re.findall(r'(?:[Чч]|[Пп]|подп|Подп)\.\s*([\dа-я«»., и–-]+?)(?=\s*(?:ст\.|ч\.|п\.|$|[А-ЯЁа-яё]{3}))', r); ns = set()
                for p_ in parts: ns |= set(re.findall(r'\d+(?:\.\d+)*', p_))
                for a_ in arts:
                    for x in (ns or {''}): out.setdefault((a_, x), []).append((line, r))
        return out
    if blk:
        srcl = [l for l in src(q).split('\n') if not l.startswith('!! ')]; ko = refkeys(srcl); kk = refkeys([blk[3:]])
        where = {}
        for ui, u in enumerate(units):
            for k, l in enumerate(u.lines): where.setdefault(l, []).append((ui, k))
        for key in sorted(kk):
            if not key[1] or key not in ko: continue
            its = set()
            for line, r in ko[key]:
                for ui, k in where.get(line, []):
                    for j, sn in enumerate(lines[(ui, k)][1]):
                        if r in sn: its.add(idx[(ui, k, j)])
            if not its or any(items[i].keep for i in its): continue
            cand = []
            for i in its:
                need = [k for k in closure(i) if not items[k].keep]
                if i in banned or any(k in banned for k in need): continue
                cand.append((sum(items[k].w for k in need), i, need))
            if cand:
                for k in min(cand)[2]: items[k].keep = True; items[k].why = items[k].why or 'ссылка'
    # акт, названный в ответе, не должен исчезнуть совсем: оставляем самый короткий пункт, где он упомянут
    NUM = re.compile(r'№\s?(\d[\d/.\-]*(?:-?[А-Яа-яA-Z]{1,4})?\d*)')
    nums = [{m.group(1).rstrip('.-/') for m in NUM.finditer(it.text)} for it in items]
    dated = lambda a, t: bool(re.search(r'от \d{1,2}[. ][\d.а-я]+ ?\d{4}(?: г\.)? № ?' + re.escape(a) + r'(?![\d\-])', t))
    for a in sorted(set().union(*nums) if nums else ()):
        full = [i for i, it in enumerate(items) if a in nums[i] and dated(a, it.text)]   # полное название акта (с датой) должно остаться, если оно было
        if any(items[i].keep for i in full) or (not full and (any(it.keep and a in nums[i] for i, it in enumerate(items)) or a in title)): continue
        cand = []
        for i, it in enumerate(items):
            if a not in nums[i] or i in banned or (full and i not in full): continue
            need = [k for k in closure(i) if not items[k].keep]
            if any(k in banned for k in need): continue
            cand.append((sum(items[k].w for k in need), i, need))
        if cand:
            for k in min(cand)[2]: items[k].keep = True; items[k].why = items[k].why or 'акт'
    # блок не должен сообщать того, чего в тексте нет: слова блока, пропавшие из оставленного текста, возвращаем вместе с пунктом
    bst = lambda w: w[:5] if len(w) > 6 else w[:4]
    bwords = lambda t: [w for w in re.findall(r'[а-яё]+', re.sub(r'//.*?//', ' ', t).lower().replace('ё', 'е')) if len(w) >= 5]
    bnums = lambda t: {'#' + x.replace(' ', '') for x in re.findall(r'(?<![\d.,№/])\b\d+(?: \d{3})*\b(?![.,]\d)', re.sub(r'//.*?//', ' ', t))}   # числа вне ссылок: сроки, суммы, количества
    itst = [set(bst(w) for w in bwords(it.text)) | bnums(it.text) for it in items]
    def blockwords():
        for sn in bs:
            ws = set(bwords(sn)) - {'главное', 'запоминания'}; nb = bnums(sn)
            if len(ws) < 4 and not nb: continue
            for _ in range(12):
                keptst = set(bst(w) for w in bwords(title + ' ' + ' '.join(secs[si][0] for si in {units[it.u].sec for it in items if it.keep})))
                allst = set().union(*itst) if itst else set()
                for i, it in enumerate(items):
                    if it.keep: keptst |= itst[i]
                miss = {bst(w) for w in ws if bst(w) not in keptst}; mnum = {x for x in nb if x not in keptst and x in allst}
                if not (mnum or len(miss) >= 3 or (len(miss) >= 2 and len(miss) / max(len(ws), 1) > 0.25)): break
                miss |= mnum
                cand = []
                for i, it in enumerate(items):
                    if it.keep or i in banned or not (miss & itst[i]): continue
                    need = [k for k in closure(i) if not items[k].keep]
                    if any(k in banned for k in need): continue
                    got = set().union(*[itst[k] for k in need]) & miss
                    cand.append((len(got) / (12.0 + sum(items[k].w for k in need)), i, need))
                if not cand: break
                _, i, need = max(cand)
                for k in need: items[k].keep = True; items[k].why = items[k].why or 'блок2'
    blockwords()
    def blocksupport():                                    # предложение блока, у которого в тексте осталось меньше 60 % опоры, получает опорный пункт
        for sn in bs:
            need = {x for x in ((ST(sn) - STOP) | ARTS(sn)) if x in df}; tot = sum(wt(x) for x in need)
            if not tot: continue
            for _ in range(2):
                kept = set()
                for i, it in enumerate(items):
                    if it.keep: kept |= toks[i]
                if sum(wt(x) for x in need & kept) >= BSUP * tot: break
                miss = need - kept; cand = []
                for i, it in enumerate(items):
                    if it.keep or i in banned or not (miss & toks[i]): continue
                    nd = [k for k in closure(i) if not items[k].keep]
                    if any(k in banned for k in nd): continue
                    got = set().union(*[toks[k] for k in nd]) & miss
                    cand.append((sum(wt(x) for x in got) / (12.0 + sum(items[k].w for k in nd)), i, nd))
                if not cand: break
                for k in max(cand)[2]: items[k].keep = True; items[k].why = items[k].why or 'блок3'
    blocksupport()
    ssc = {}
    for si, (h, _) in enumerate(secs):
        s = -0.6 if PERI.search(h) else 0.0
        if si == 0: s += 0.5
        s += 0.8 * len((ST(h) - STOP) & tt) / max(len(ST(h) - STOP), 1)     # раздел назван словами вопроса — это часть вопроса
        if si in pbsec: s = -0.2                              # цитаты «Правовой основы» — после текста: норма обычно повторена в разделах
        ssc[si] = s
    firstu = {}
    for ui, u in enumerate(units):
        if u.grp != 'def': firstu.setdefault(u.sec, ui)
    sc = {}
    for i, it in enumerate(items):
        u = units[it.u]; t = toks[i]; n = len(t) or 1
        s = 1.5 * len(t & tt) / max(len(tt), 1) + 1.2 * len(t & btok) / n + 0.2 * ('«' in it.text) + 0.15 * ('//' in it.text)
        if it.kd == 'head':
            s += 1.0 * (firstu.get(u.sec) == it.u) + 0.4 * (u.grp == 'list')
            if CORE.match(re.sub(r'^(- |\d+\. )?(\*\*)?(//)?', '', u.lines[0]).lower()): s += 0.3
            if PERI.search(u.text[:60]): s -= 0.5
            s += 0.25 * (it.w <= 20)                              # короткий пункт дёшев — его выгоднее оставить
        else: s -= 0.35 + 0.1 * it.parts[0][1]
        sc[i] = ssc[u.sec] + s
    headw = wc(title) + wc(blk)
    size = lambda: headw + sum(it.w for it in items if it.keep) + sum(wc(secs[si][0]) for si in {units[it.u].sec for it in items if it.keep})
    cur = size()
    target = max(target, cur + FLOOR * sum(it.w for i, it in enumerate(items) if not it.keep and i not in banned))   # большому обязательному ядру — ещё доля остального
    # возврат текста «по уровню»: каждый раз добавляем лучший пункт того раздела, от которого осталась наименьшая доля, —
    # так ни одна часть вопроса не выпадает, пока другая стоит целиком; второстепенным разделам и «Правовой основе» доля меньше
    secw = {}; prio = {}
    for i, it in enumerate(items): secw[units[it.u].sec] = secw.get(units[it.u].sec, 0) + it.w
    for si, (h, _) in enumerate(secs):
        hs = ST(h) - STOP
        prio[si] = 0.4 if si in pbsec else 0.55 if PERI.search(h) else 1.0 + 0.5 * len(hs & tt) / max(len(hs), 1)
    for si, (h, _) in enumerate(secs):
        for pref, v in SECPRIO.get(q, []):
            if hm(re.sub(r'^## \d+\.\s*', '', h), pref): prio[si] = v
    keptw = {si: sum(it.w for it in items if it.keep and units[it.u].sec == si) for si in secw}
    cand = {si: sorted((i for i, it in enumerate(items) if units[it.u].sec == si and not it.keep and i not in banned), key=lambda i: sc[i]) for si in secw}
    while True:
        live = [si for si in cand if cand[si] and prio[si] > 0]
        if not live: break
        si = min(live, key=lambda si: keptw[si] / max(secw[si], 1) / prio[si])
        i = cand[si].pop()
        if items[i].keep: continue
        need = [k for k in closure(i) if not items[k].keep]
        if any(k in banned for k in need): continue
        cost = sum(items[k].w for k in need) + sum(wc(secs[x][0]) for x in {units[items[k].u].sec for k in need} - {units[it.u].sec for it in items if it.keep})
        if cur + cost <= target:
            for k in need: items[k].keep = True; items[k].why = items[k].why or 'оц'; keptw[units[items[k].u].sec] += items[k].w
            cur += cost
    # ни один раздел не пропадает целиком (кроме убранных вручную): остаётся первый пункт, а если он длинный — самый короткий
    for si in range(len(secs)):
        hs_ = [head[ui] for ui, u in enumerate(units) if u.sec == si]
        if not hs_ or any(items[i].keep for i, it in enumerate(items) if units[it.u].sec == si) or all(i in banned for i in hs_): continue
        if PERI.search(secs[si][0]) and not ((ST(secs[si][0]) - STOP) & tt): continue      # второстепенный раздел, которого нет ни в вопросе, ни в блоке, уходит целиком
        ok = [i for i in hs_ if i not in banned and not any(k in banned for k in closure(i))]
        if not ok: continue
        cst = lambda i: sum(items[k].w for k in closure(i) if not items[k].keep)
        i = ok[0] if cst(ok[0]) <= 45 else min(ok, key=cst)
        for k in closure(i):
            if not items[k].keep: items[k].keep = True; items[k].why = 'разд'
    blockwords()
    plan.ssc = ssc; plan.pbsec = pbsec; plan.bs = bs; plan.toks = toks; plan.df = df
    return title, secs, units, blk, items, head, lines, idx
def build(q, target):
    title, secs, units, blk, items, head, lines, idx = plan(q, target)
    res = [title, '']; n = 0; log = []
    for si, (h, _) in enumerate(secs):
        us = [ui for ui, u in enumerate(units) if u.sec == si]
        if not any(items[head[ui]].keep for ui in us):
            log.append('РАЗДЕЛ ' + h[3:] + ' (%d)' % sum(it.w for it in items if units[it.u].sec == si)); continue
        if h: n += 1; res += [re.sub(r'^## \d+\.', '## %d.' % n, h), '']
        prev = None; nk = sum(1 for ui in us if items[head[ui]].keep)
        for ui in us:
            u = units[ui]
            if not items[head[ui]].keep:
                log.append('%s [ост. %d из %d]: %s… (%d)' % (re.sub(r'^\d+\. ', '', h[3:])[:24], nk, len(us), u.lines[0][:95], wc(u.text))); continue
            for k, l in enumerate(u.lines):
                pre, ss, hl = lines[(ui, k)]; kept = [s for j, s in enumerate(ss) if items[idx[(ui, k, j)]].keep]
                out = pre + ' '.join(kept)
                if len(kept) < len(ss):
                    if l.rstrip().endswith(';') and out.endswith('.'): out = out[:-1] + ';'
                    log.append('   хвост: …%s ║ %s (%d)' % (kept[-1][-45:], ' '.join(ss[len(kept):])[:80], sum(wc(x) for x in ss[len(kept):])))
                kd = kind(l)
                if prev is not None and not (kd in ('li', 'sub', 'num') and prev in ('li', 'sub', 'num')): res.append('')
                res.append(out); prev = kd
        res.append('')
    if blk:
        kept = set(); df = plan.df
        for i, it in enumerate(items):
            if it.keep: kept |= plan.toks[i]
        out = []
        for s in plan.bs:
            need = {x for x in ((ST(s) - STOP) | ARTS(s)) if x in df}; tot = sum(1.0 / df[x] for x in need)
            got = sum(1.0 / df[x] for x in need & kept)
            if tot and got < 0.5 * tot: log.append('   БЛОК −: %s (%d)' % (s[:110], wc(s)))
            else: out.append(s)
        res += ['!! **Главное для запоминания.** ' + ' '.join(out), '']
    return '\n'.join(res).rstrip('\n') + '\n', log
def run(total):
    T = targets(total); out = {}
    for q in range(1, 150): out[q] = build(q, T[q]) + (T[q],)
    return out
if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'sim'; only = {int(x) for x in sys.argv[2:] if x.isdigit()}
    if mode == 'propose':                                      # сводка разделов для ручного выбора: слова, число опор блока, оценка
        T = targets(TOTAL)
        for q in range(1, 150):
            title, secs, units, blk, items, head, lines, idx = plan(q, 10 ** 9); ssc = plan.ssc
            w = {si: sum(it.w for it in items if units[it.u].sec == si) for si in range(len(secs))}
            an = {si: sum(1 for it in items if units[it.u].sec == si and it.why == 'блок') for si in range(len(secs))}
            tot = wc(src(q)); drop = set(); cur = tot
            for si in sorted((si for si in range(len(secs)) if si and si not in plan.pbsec and secs[si][0]), key=lambda si: ssc[si]):
                if cur <= T[q] * 1.07: break
                if cur - w[si] < T[q] * 0.93: continue
                drop.add(si); cur -= w[si]
            print('q%03d %d→%d (после %d) | %s' % (q, tot, T[q], cur, title[2:210]))
            print('   ' + ' | '.join('%s%s(%d,б%d)' % ('−' if si in drop else '+', re.sub(r'^## ', '', secs[si][0])[:52], w[si], an[si]) for si in range(len(secs))))
        sys.exit()
    lo, hi = TOTAL * 0.3, TOTAL * 1.1                         # подбор внутренних целей под общий объём
    for _ in range(14):
        mid = (lo + hi) / 2; out = run(mid); tot = sum(wc(out[q][0]) for q in out)
        if tot > TOTAL: hi = mid
        else: lo = mid
    out = run(lo); tot = sum(wc(out[q][0]) for q in out)
    for q in range(1, 150):
        txt, log, t = out[q]
        if mode == 'show' and (not only or q in only):
            print('\n=== q%03d %d → %d (цель %d) %s' % (q, wc(src(q)), wc(txt), t, txt.split('\n')[0][2:120]))
            for c in log: print('  − ' + c)
        if mode == 'apply' and (not only or q in only): open('adp2/q%03d.txt' % q, 'w', encoding='utf-8').write(txt)
    ov = [(q, wc(out[q][0]), int(out[q][2])) for q in out if wc(out[q][0]) > out[q][2] * 1.08]
    nb = sum(1 for q in out for c in out[q][1] if 'БЛОК −' in c)
    print('итого слов', tot, '| из блоков снято предложений', nb, '| внутренняя цель', int(lo), '| выше своей цели более чем на 8%:', len(ov))
    if mode == 'sim':
        for q, w, t in ov: print('  q%03d %d при цели %d' % (q, w, t))
        nsec = sum(1 for q in out for c in out[q][1] if c.startswith('РАЗДЕЛ')); ntail = sum(1 for q in out for c in out[q][1] if c.startswith('   хвост'))
        nun = sum(1 for q in out for c in out[q][1] if not c.startswith(('РАЗДЕЛ', '   хвост')))
        print('убрано разделов', nsec, '| единиц', nun, '| концовок строк', ntail)
