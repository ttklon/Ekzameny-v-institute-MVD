#!/usr/bin/env python3
"""part25.py SRC [N…] — ссылки на часть и пункт статьи закона или кодекса («п. 33 ч. 1 ст. 12», «ч. 3 ст. 19», «п. 2 ст. 2»):
слова предложения ищутся в названной части (пункте) названной статьи. Печатает:
  «НЕТ ЧАСТИ» / «НЕТ ПУНКТА» — в статье нет части или пункта с таким номером;
  «МАЛО» — в названной части (пункте) меньше половины слов, а в другой части (пункте) той же статьи их заметно больше.
Текст берётся из HTML-версии акта (там сохранено деление на части «1. …» и пункты «1) …»). Блок «Главное для запоминания»
не проверяется: он повторяет ссылки текста. Это отбор мест для чтения, а не вывод об ошибке."""
import sys, os, re, io, contextlib, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = sys.argv[1]; only = [int(x) for x in sys.argv[2:]]
sys.argv = [sys.argv[0], src]
with contextlib.redirect_stdout(io.StringIO()):
    import cut25, qcheck2
import srctok25 as K
def arts(f):
    raw = open(f, encoding='utf-8', errors='replace').read(); raw = re.sub(r'<\d+>', ' ', raw); raw = K.CLEAN.sub(' ', raw)
    res = {}; ms = list(re.finditer(r'Статья\s+(\d+)(?:\.(\d+))?(?:\s(\d+)\s)?\s?\.\s+(?=[А-ЯЁ(])', raw))
    for i, m in enumerate(ms):
        num = '.'.join(x for x in m.groups() if x)
        res[num] = res.get(num, '') + raw[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(raw)]
    return res
def split(t, rx):
    ms = list(re.finditer(rx, t)); res = collections.OrderedDict()
    if not ms: return res
    res[''] = t[:ms[0].start()]
    for i, m in enumerate(ms):
        k = m.group(1) + ('.' + m.group(2) if m.group(2) else '')
        res[k] = res.get(k, '') + t[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(t)]
    return res
PART = r'(?:\s{2,}|\xa0\s*)(\d+)(?: (\d+) ?)?\.(?=[\xa0 ]+[А-ЯЁ(«])'
PUNKT = r'(?:\s{2,}|\xa0\s*)(\d+)(?: (\d+) ?)?\)(?=[\xa0 ])'
def parts(t):
    note = re.search(r'\s{2,}Примечани[ея]\s?[.:]', t)
    if note: t = t[:note.start()]
    P = split(t, PART)
    if P: return P
    return collections.OrderedDict()    # части без номеров (Закон № 103-ФЗ и др.): по HTML абзацы надёжно не делятся, такие ссылки читаются вручную
FC = {}
def files(disp):
    if disp not in FC:
        kind, pat = qcheck2.act_files(disp)
        FC[disp] = [arts(p) for rel, p in sorted(qcheck2.files.items()) if kind not in ('SKIP', 'UNK') and pat and re.search(pat, rel) and rel.endswith('.html')]
        FC[disp] = [a for a in FC[disp] if len(a) > 3]
    return FC[disp]
def cov(words, txt):
    have = set(K.tokens(txt)); return sum(1 for w in words if w in have) / (len(words) or 1)
def nums(s):
    """«1, 2», «3–5», «1.1» → список номеров"""
    out = []
    for a, b in re.findall(r'(\d+(?:\.\d+)?)(?:\s*[–—-]\s*(\d+(?:\.\d+)?))?', s):
        if b and '.' not in a + b and 0 < int(b) - int(a) < 40: out += [str(x) for x in range(int(a), int(b) + 1)]
        else: out += [a] + ([b] if b else [])
    return out
def check(t, pn, un, words):
    """('ok'|'нет части'|'нет пункта'|'мало'|'-', доля, сообщение) для статьи t"""
    P = parts(t)
    if pn:
        if not P: return '-', 1, ''             # части без номеров — не проверяется
        miss = [x for x in pn if x not in P]
        if miss: return 'нет части', -1, 'НЕТ ЧАСТИ %s; есть: %s' % (','.join(miss), ' '.join(k_ for k_ in P if k_))
        scope = {x: P[x] for x in pn}
    else: scope = {'': t}
    units = dict(scope); level = 'ч.'; allu = {k_: v for k_, v in P.items() if k_} if pn else {}
    if un:
        level = 'п.'; units = {}; allu = {}
        for x, pt in scope.items():
            U = split(pt, PUNKT)
            if not pn and P and (not U or all(u in P for u in un)): U = P   # «п. 2 ст. 32» — в статье пункты оформлены как «2. …»
            for k_, v in U.items():
                if k_: allu[k_] = v
            for u in un:
                if u in U: units[u] = U[u]
        miss = [u for u in un if u not in units]
        if miss: return 'нет пункта', -1, 'НЕТ ПУНКТА %s%s; есть: %s' % (','.join(miss), ' в ч. ' + ','.join(pn) if pn else '', ' '.join(list(allu)[:70]))
    if len(words) < 3 or len(allu) < 2: return '-', 1, ''
    c = max(cov(words, v) for v in units.values())
    alt = max(((cov(words, v), k_) for k_, v in allu.items() if k_ not in units), default=(-1, ''))
    if c < 0.5 and alt[0] > c + 0.2:
        return 'мало', c, 'МАЛО (%.2f) в %s %s; лучше %s %s (%.2f)\n      ТАМ: %s' % (c, level, ','.join(units), level, alt[1], alt[0], re.sub(r'\s+', ' ', allu[alt[1]])[:220])
    return 'ok', c, ''
LIST = []
def run(n):
    out = []; lines = open(cut25.A + 'q%03d.txt' % n, encoding='utf-8').read().split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces); st = [0, 0]
    hart = {}; ha = None                        # статья из заголовка раздела — для ссылок вида «ч. N» без статьи
    for j, l in enumerate(lines):
        if l.startswith('## '):
            m_ = re.findall(r'[Сс]т(?:\.|атья)\s*(\d+(?:\.\d+)*)', l); ha = m_[-1] if m_ else None
        hart[j] = ha
    for (i, _z), line in pieces:
        if line.startswith('#') or line.startswith('!!'): continue
        refs = list(cut25.REF.finditer(line)); pos = 0; prev = None
        for s in K.sentences(line):
            a = line.find(s[:40], pos); a = pos if a < 0 else a; b = a + len(s); pos = b
            inr = [(k, m) for k, m in enumerate(refs) if a <= m.start() < b]
            for z, (k, m) in enumerate(inr):
                r = m.group(1); act, art = res.get(((i, 0), k), (None, None)); disp = names.get(((i, 0), k))
                hasart = bool(re.search(r'[Сс]т\.', r)); cands = [art] if hasart else [x for x in dict.fromkeys([prev, hart.get(i), art]) if x]
                if hasart: prev = art
                if not disp or not art or re.search(r'подп\.|примечани', r): continue
                if len(re.findall(r'[Сс]т\.', r)) > 1 or re.search(r'[Сс]т\.\s*\d+(?:\.\d+)*\s*(?:,|и|–|—|-)\s*\d', r): continue   # несколько статей в одной ссылке
                pm = re.search(r'[Чч]\.\s*(\d+(?:\.\d+)?(?:\s*(?:,|и|–|—|-)\s*\d+(?:\.\d+)?)*)', r)
                um = re.search(r'(?:^|[\s(])пп?\.\s*(\d+(?:\.\d+)?(?:\s*(?:,|и|–|—|-)\s*\d+(?:\.\d+)?)*)', r)
                if not pm and not um: continue
                if not hasart and not pm: continue                  # «п. N» без статьи и части — пункт подзаконного акта (punkt25.py)
                pn = nums(pm.group(1)) if pm else []; un = nums(um.group(1)) if um else []
                st0 = inr[z - 1][1].end() if z else a
                seg = line[st0:m.start()]
                bare = len(K.tokens(K.strip(re.sub(r'\(далее[^()]*\)', ' ', line[st0:m.start()])))) < 3
                if bare:
                    seg = s; LIST.append((n, i + 1, r, disp, art, pn, un))
                words = sorted({w for w in K.tokens(K.strip(re.sub(r'\(далее[^()]*\)', ' ', seg))) if not w[0].isdigit()})
                best = None
                for c_ in cands:
                    A = [x for x in files(disp) if c_ in x]
                    if not A: continue
                    kind, cv, msg = check(A[-1][c_], pn, un, words)
                    rank = {'ok': 3, '-': 3, 'мало': 1, 'нет пункта': 0, 'нет части': 0}[kind] + max(cv, 0)
                    if best is None or rank > best[0]: best = (rank, kind, msg, c_)
                if best is None: continue
                st[0] += 1; st[1] += best[1] in ('ok', 'мало')
                if best[1] in ('ok', '-') or (bare and best[1] == 'мало'): continue
                out.append('q%03d:%d (%s → ст. %s, %s) %s | %s' % (n, i + 1, r[:40], best[3], disp[:30], best[2].split('\n')[0], seg.strip()[:200]) + ('\n' + best[2].split('\n', 1)[1] if '\n' in best[2] else ''))
    return out, st
if __name__ == '__main__':
    tot = [0, 0]; k = 0
    for n in (only or range(1, 150)):
        o, st = run(n); tot[0] += st[0]; tot[1] += st[1]; k += len(o)
        for x in o: print(x)
    if os.environ.get('PART25_LIST'):
        # ссылки без утверждения: печатается начало названной части (пункта) — читать и сверять с темой вопроса
        for n, i, r, disp, art, pn, un in LIST:
            A = [x for x in files(disp) if art in x]
            if not A: continue
            P = parts(A[-1][art]); sc = [P.get(x, '') for x in pn] if pn else [A[-1][art]]
            for pt in sc:
                U = split(pt, PUNKT) if un else {}
                if un and not pn and P and (not U or all(u in P for u in un)): U = P
                for u in (un or ['']):
                    txt = U.get(u, '') if un else pt
                    print('LIST q%03d:%d %s | %s%s ст. %s (%s): %s' % (n, i, r[:40], 'п. %s ' % u if u else '', 'ч. ' + ','.join(pn) if pn else '', art, disp[:22], re.sub(r'\s+', ' ', txt)[:170]))
    print('ссылок на часть или пункт статьи:', tot[0], 'сопоставлено по словам:', tot[1], 'замечаний:', k)
