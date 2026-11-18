#!/usr/bin/env python3
"""fit25.py sim | show N… | apply — сокращение варианта 2 до 25 часов (150 тыс. слов) целыми единицами текста.

Единица — абзац, отдельный пункт-факт («- **Срок:** …») либо перечень целиком (вводная строка с двоеточием и все её
пункты; ряд «ч. 1, ч. 2…»; ряд «термин — определение»; ряд «по …»; нумерованный список). Перечень не режется по частям,
строка не режется внутри. Не трогаются: определения («> »), раздел «Правовая основа», строки с «(далее — …)», блок
«Главное для запоминания» и те единицы, на которые опирается каждое предложение блока. Остальные единицы возвращаются
по убыванию оценки (связь с формулировкой вопроса и с блоком, наличие нормы), пока ответ укладывается в свой объём.
Неполные ссылки («ч. 2», «ст. 17»), у которых после сокращения пропал задающий акт или статью текст, дописываются до полных.
Ручные поправки — в fit25_over.txt: «N + начало строки» (оставить), «N - начало строки» (убрать)."""
import os, sys, re, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(os.path.join(HERE, '..'))
import cut25 as C
TOTAL = 146300                      # слов в txt (единый docx добавляет около 2 150 слов заголовков и оглавления)
wc = lambda s: len(s.split())
ST = lambda s: {w[:6] for w in re.findall(r'[а-яё]{5,}', s.lower().replace('ё', 'е'))}
ARTS = lambda s: {'#' + a for a in re.findall(r'(?:ст|п|ч)\. (\d+(?:\.\d+)*)', s)} | {'#' + a for a in re.findall(r'\b(\d{2,}(?:[ .]\d{3})*)\b', s)}
STOP = ST('полиции полиция российской федерации закона закон федерального федеральный статья также которые которых является могут может должен должны лица лицо органов органы внутренних дел сотрудник сотрудника сотрудники административного административных административной правонарушениях правонарушения кодекса главное запоминания далее только случае случаях порядке порядок числе россии')
PERI = re.compile(r'отграничен|отлич|смежн|взаимодейств|гаранти|проблем|практическ|значени|соотношен|обжалован|оформлен|история|перспектив|статистик|последстви|ошибк|разъяснени|пример|иные |другие |други[хм] ', re.I)
SEQ = re.compile(r'(?:- |\d+\. )?\*\*(//)?(Ч\.|Ст\.|П\.|Подп\.|Гл\.|Часть|Статья|Пункт|Глава|Перв|Втор|Трет|Четв|Пят|Шест|Седьм|Восьм|Девят|Десят|\d)')
PB = re.compile(r'равовая основа|равовое регулирование|ормативн\w+ (основ|закреплен)|онституционн\w+ (и законодательн\w+ )?основ')
def kind(l):
    if l.startswith('> '): return 'def'
    if l.startswith('  - '): return 'sub'
    if l.startswith('- '): return 'li'
    if re.match(r'\d+\. ', l): return 'num'
    return 'p'
def litype(l):
    b = l[2:] if l.startswith('- ') else l
    if kind(l) == 'num': return 'S'
    if SEQ.match(l): return 'S'
    if re.match(r'\*\*[^*]{1,60}\*\* —', b): return 'T'
    if re.match(r'\*\*По ', b): return 'B'
    if b.rstrip().endswith(';') or (b[:1].islower() or b[:1] == '«') and not b.startswith('**'): return 'E'
    return 'F'
class U:
    def __init__(s, lines, sec, grp): s.lines = lines; s.sec = sec; s.grp = grp; s.keep = False; s.why = ''
    @property
    def text(s): return ' '.join(s.lines)
    @property
    def w(s): return wc(s.text)
def parse(q):
    L = [l for l in open('adp2/q%03d.txt' % q, encoding='utf-8').read().split('\n')]
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
                if l.rstrip().endswith(':') or (C.COUNT.search(l.lower()) and j < len(ls) and kind(ls[j]) != 'p'):
                    while j < len(ls) and kind(ls[j]) in ('li', 'sub', 'num'): j += 1
                    if j > i + 1: units.append(U(ls[i:j], si, 'list')); i = j; continue
                units.append(U([l], si, 'p')); i += 1; continue
            j = i                                              # ряд пунктов без вводной строки
            while j < len(ls) and kind(ls[j]) in ('li', 'sub', 'num'): j += 1
            run = ls[i:j]
            if counted and not any(u.sec == si and u.grp != 'def' for u in units): units.append(U(run, si, 'list')); i = j; continue
            a = 0
            while a < len(run):
                t = litype(run[a]); b = a + 1
                while b < len(run) and kind(run[b]) == 'sub': b += 1
                if t == 'F': units.append(U(run[a:b], si, 'fact')); a = b; continue
                while b < len(run) and (kind(run[b]) == 'sub' or litype(run[b]) == t): b += 1
                units.append(U(run[a:b], si, 'list' if b - a > 1 else 'fact')); a = b
            i = j
    return title, secs, units, blk
def over():
    o = {}
    p = os.path.join(HERE, 'fit25_over.txt')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            m = re.match(r'(\d+) ([+-]) (.+)', l.rstrip('\n'))
            if m: o.setdefault(int(m.group(1)), []).append((m.group(2), m.group(3)))
    return o
OVER = over()
def targets():
    body = {}
    for q in range(1, 150):
        t = open('adp2/q%03d.txt' % q, encoding='utf-8').read(); body[q] = wc(t)
    mean = sum(body.values()) / 149; raw = {q: math.sqrt(body[q] * mean) for q in body}; k = TOTAL / sum(raw.values())
    return {q: raw[q] * k for q in body}
def plan(q, target):
    title, secs, units, blk = parse(q)
    tt = (ST(re.sub(r'^# Вопрос \d+\.', '', title)) - STOP)
    df = {}
    toks = []
    for u in units:
        t = (ST(u.text) - STOP) | ARTS(u.text); toks.append(t)
        for x in t: df[x] = df.get(x, 0) + 1
    wt = lambda x: 1.0 / df.get(x, 1)
    pbsec = {si for si, (h, _) in enumerate(secs) if PB.search(h)}
    # 1) неприкосновенное
    for i, u in enumerate(units):
        if u.grp == 'def': u.keep = True; u.why = 'опр'
        elif u.sec in pbsec: u.keep = True; u.why = 'ПО'
        elif '(далее —' in u.text: u.keep = True; u.why = 'далее'
    # 2) опоры блока
    bs = [s for s in C.split_sent(re.sub(r'^!! \*\*Главное для запоминания\.\*\*\s*', '', blk)) if s.strip()]
    btok = set()
    for s in bs:
        need = (ST(s) - STOP) | ARTS(s); btok |= need
        need = {x for x in need if x in df}; tot = sum(wt(x) for x in need) or 1
        for _ in range(3):
            best = max(range(len(units)), key=lambda i: sum(wt(x) for x in need & toks[i]) / (1 + 0.002 * units[i].w), default=None)
            if best is None: break
            got = sum(wt(x) for x in need & toks[best])
            if got < 0.22 * tot or got == 0: break
            if not units[best].keep: units[best].keep = True; units[best].why = 'блок'
            need -= toks[best]
    # 3) оценка остальных
    secanch = {u.sec for u in units if u.why == 'блок'}
    first = {}
    for i, u in enumerate(units): first.setdefault(u.sec, i)
    sc = {}
    for i, u in enumerate(units):
        t = toks[i]; n = len(t) or 1; h = secs[u.sec][0]
        s = 2.0 * len(t & tt) / max(len(tt), 1) + 1.5 * len(t & btok) / n
        s += 0.25 * ('«' in u.text) + 0.2 * ('//' in u.text) + 0.3 * (first[u.sec] == i) + 0.25 * (u.sec in secanch) + 0.3 * (u.sec == 0)
        s += 0.6 * len(ST(h) & tt) / max(len(tt), 1)
        if PERI.search(h) or PERI.search(u.text[:60]): s -= 0.5
        if u.grp == 'list': s += 0.15
        sc[i] = s
    for sign, pref in OVER.get(q, []):
        hit = [i for i, u in enumerate(units) if any(l.startswith(pref) for l in u.lines)]
        assert hit, 'q%03d: нет строки «%s»' % (q, pref)
        for i in hit:
            if sign == '+': units[i].keep = True; units[i].why = 'руч'
            else: units[i].keep = False; units[i].why = 'руч−'
    head = wc(title) + sum(wc(h) for h, _ in secs) + wc(blk)
    used = head + sum(u.w for u in units if u.keep)
    ana = lambda u: bool(C.ANA.match(re.sub(r'^(- |\d+\. )?(\*\*)?', '', u.lines[0])))
    for i in sorted((i for i, u in enumerate(units) if not u.keep and u.why != 'руч−'), key=lambda i: -sc[i]):
        u = units[i]; need = [i]; j = i
        while ana(units[j]) and j > 0 and units[j - 1].sec == u.sec and not units[j - 1].keep: j -= 1; need.append(j)
        add = sum(units[k].w for k in need)
        if used + add <= target:
            for k in need: units[k].keep = True; units[k].why = units[k].why or 'оц'
            used += add
    # 4) зависимые: оставленная анафора тянет предыдущую единицу; раздел без содержания убирается
    for i, u in enumerate(units):
        if u.keep and ana(u) and i > 0 and units[i - 1].sec == u.sec and not units[i - 1].keep and units[i - 1].why != 'руч−':
            units[i - 1].keep = True; units[i - 1].why = 'связь'
    for si in range(len(secs)):
        ks = [u for u in units if u.sec == si and u.keep]
        if ks and si not in pbsec and si != 0 and sum(u.w for u in ks) < 18 and not any(u.why in ('блок', 'опр', 'руч', 'далее') for u in ks):
            for u in ks: u.keep = False; u.why = 'обрывок'
    return title, secs, units, blk, sc
def build(q, target):
    title, secs, units, blk, sc = plan(q, target)
    # ссылки: контекст до и после
    pieces = []; skip = set()
    for si, (h, _) in enumerate(secs):
        pieces.append((('h', si), h))
        for i, u in enumerate(units):
            if u.sec != si: continue
            for k, l in enumerate(u.lines):
                pieces.append(((i, k), l))
                if not u.keep: skip.add((i, k))
    r0, n0 = C.resolve(pieces); r1, n1 = C.resolve(pieces, frozenset(skip)); fixes = []
    newline = {}
    for pid, l in pieces:
        if pid in skip or pid[0] == 'h': continue
        refs = list(C.REF.finditer(l)); out = l
        for k in range(len(refs) - 1, -1, -1):
            a0 = r0[(pid, k)]; a1 = r1[(pid, k)]
            if a0 == a1: continue
            ref = refs[k].group(1); add = ''
            if not re.search(r'[Сс]т\.\s*\d', ref) and a0[1] and re.match(r'(ч|п|подп|абз|примечани)', ref.lower()) and not C.ref_ctx(ref)[0]: add += ' ст. ' + a0[1]
            if not C.ref_ctx(ref)[0] and n0[(pid, k)]: add += ' ' + gen(n0[(pid, k)])
            if add:
                out = out[:refs[k].start(1)] + ref + add + out[refs[k].end(1):]; fixes.append((ref, ref + add))
        if out != l: newline[pid] = out
    res = [title, '']; n = 0; cutlog = []
    for si, (h, _) in enumerate(secs):
        us = [(i, u) for i, u in enumerate(units) if u.sec == si]
        if not any(u.keep for _, u in us):
            cutlog.append('РАЗДЕЛ ' + h[3:] + ' (%d)' % sum(u.w for _, u in us)); continue
        if h:
            n += 1; res += [re.sub(r'^## \d+\.', '## %d.' % n, h), '']
        prev = None
        for i, u in us:
            if not u.keep:
                cutlog.append('%s: %s… (%d)' % (re.sub(r'^\d+\. ', '', h[3:])[:28], u.lines[0][:110], u.w)); continue
            for k, l in enumerate(u.lines):
                l = newline.get((i, k), l); kd = kind(l)
                if prev is not None and not (kd in ('li', 'sub', 'num') and prev in ('li', 'sub', 'num')): res.append('')
                res.append(l); prev = kd
        res.append('')
    if blk: res += [blk, '']
    return '\n'.join(res).rstrip('\n') + '\n', cutlog, fixes, units
GENMAP = [('Федеральный конституционный закон', 'Федерального конституционного закона'), ('Федеральный закон', 'Федерального закона'), ('Закон', 'Закона'), ('Уголовный кодекс', 'Уголовного кодекса'),
          ('Уголовно-процессуальный кодекс', 'Уголовно-процессуального кодекса'), ('Трудовой кодекс', 'Трудового кодекса'), ('Гражданский кодекс', 'Гражданского кодекса'), ('Семейный кодекс', 'Семейного кодекса'),
          ('Воздушный кодекс', 'Воздушного кодекса'), ('Лесной кодекс', 'Лесного кодекса'), ('Водный кодекс', 'Водного кодекса'), ('Кодекс', 'Кодекса'), ('Указ', 'Указа'), ('Типовое положение', 'Типового положения'),
          ('Примерное положение', 'Примерного положения'), ('Положение', 'Положения'), ('Наставление', 'Наставления'), ('Инструкция', 'Инструкции'), ('Правила', 'Правил'), ('Порядок', 'Порядка'), ('Приказ', 'приказа'),
          ('приказ', 'приказа'), ('Постановление', 'постановления'), ('постановление', 'постановления'), ('Устав', 'Устава'), ('Административный регламент', 'Административного регламента'), ('Требования', 'Требований'),
          ('Концепция', 'Концепции'), ('Перечень', 'Перечня'), ('Конституция', 'Конституции'), ('Основы', 'Основ'), ('Руководство', 'Руководства'), ('Стратегия', 'Стратегии'), ('Доктрина', 'Доктрины'), ('Пленум', 'постановления Пленума')]
def gen(d):
    for a, b in GENMAP:
        if d.startswith(a + ' ') or d == a: return b + d[len(a):]
    return d
if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'sim'; only = {int(x) for x in sys.argv[2:] if x.isdigit()}
    T = targets(); tot = 0; over_t = []; nfix = 0
    for q in range(1, 150):
        txt, cutlog, fixes, units = build(q, T[q]); w = wc(txt); tot += w; nfix += len(fixes)
        if w > T[q] * 1.08: over_t.append((q, w, int(T[q])))
        if mode == 'show' and (not only or q in only):
            print('\n=== q%03d %d → %d (цель %d) %s' % (q, wc(open('adp2/q%03d.txt' % q, encoding='utf-8').read()), w, T[q], txt.split('\n')[0][2:120]))
            for c in cutlog: print('  − ' + c)
            for a, b in fixes: print('  ~ //%s// → //%s//' % (a, b))
        if mode == 'apply' and (not only or q in only): open('adp2/q%03d.txt' % q, 'w', encoding='utf-8').write(txt)
    print('итого слов', tot, '| дописано ссылок', nfix, '| выше цели более чем на 8%:', len(over_t))
    if mode == 'sim':
        for q, w, t in over_t: print('  q%03d %d при цели %d' % (q, w, t))
