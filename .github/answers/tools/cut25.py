#!/usr/bin/env python3
"""cut25.py — сокращение варианта 2 до заданной доли объёма (правка файлов adp2 на месте).
  cut25.py stat [F]      — сколько даёт каждый шаг
  cut25.py show N [F]    — что будет удалено в ответе N (с 4-м аргументом — и итоговый текст)
  cut25.py apply [F]     — применить ко всем ответам
Порядок: второстепенные разделы → хвостовые предложения без ссылки и цитаты → хвостовые блоки разделов
(блок = абзац или перечень целиком с вводной строкой) → хвостовые предложения со ссылкой, с цитатой.
Перечни не разрываются. Не трогаются: определение, первый блок раздела, «Правовая основа», «Главное для запоминания».
Удаление отменяется, если: в удаляемом вводится сокращение («далее —»), которое используется ниже;
после удаления неполная ссылка ниже (например, «ч. 2») стала бы относиться к другой статье или акту."""
import re, sys, os, glob
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2') + '/'
F_DEF = 0.598
PERI = ['отграничен', 'отлич', 'смежн', 'ответственност', 'взаимодейств', 'гаранти', 'проблем', 'практическ', 'значени', 'соотношен', 'обжалован', 'оформлен',
        'контроль', 'надзор', 'особенност', 'иные ', 'другие ', 'други', 'история', 'зарубеж', 'перспектив', 'статистик', 'последстви', 'связь', 'оценк', 'пределы', 'ошибк', 'итог', 'вывод', 'краткий']
ABBR = {'ст', 'ч', 'п', 'подп', 'абз', 'гл', 'разд', 'утв', 'г', 'гг', 'т', 'см', 'др', 'пр', 'им', 'ул', 'руб', 'тыс', 'млн', 'е', 'д', 'н', 'э', 'ред', 'рис', 'табл', 'прим', 'стр'}
EXC = re.compile(r'не допуска|запрещ|исключени|кроме |однако|нельзя|не вправе|не может|только ')
PRAV = re.compile(r'[Пп]равов\w+ (основ|регулир|база)|[Нн]ормативн\w+ (основ|база|правов|закрепл)|[Ии]сточники|[Кк]онституционн\w+ (и законодательн\w+ )?основ')
REF = re.compile(r'//(.+?)//')
SEQ = re.compile(r'- \*\*(//)?(Ч|Ст|П|Подп|Гл|Часть|Статья|Пункт|Глава|Перв|Втор|Трет|Четв|Пят|Шест|Седьм|Восьм|Девят|Десят|\d)')
COUNT = re.compile(r'\b(два|две|двух|три|трёх|четыре|четырёх|пять|шесть|семь|восемь|девять|десять|одиннадцать|двенадцать|тринадцать|перечень|структура|система|виды|классификац)\b')
ANA = re.compile(r'(Его|Её|Их|Ему|Ей|Им|Эти|Этот|Эта|Это|Этим|Этой|Этого|Этих|Такой|Такие|Такое|Такая|Таким|При этом|Кроме того|Также|Он|Она|Они|Оно|Там же|Тот же|Те же|Та же|То же|В этом|В этих|В таком|В таких|Для этого|Поэтому|Однако|Но|А|И|Вместе с тем|Наряду с этим|Указанн\w+|Названн\w+|Данн\w+|Последн\w+|Иначе|Тогда|Здесь|Отсюда|Остальн\w+|В остальн\w+|Помимо этого|Например|Так|В частности|То есть|Исключени\w+|Следовательно|Значит|Соответственно|Тем самым|В обоих|Оба|Обе|Второй|Вторая|Второе|Третий|Третья|Третье)[ ,:—]')
DROP = {}; SKIP = []
_d = os.path.join(HERE, 'drop25.txt')
if os.path.exists(_d):
    for _l in open(_d, encoding='utf-8'):
        _m = re.match(r'(\d+):\s*([\d,\s]*)$', _l.strip())
        if _m: DROP[int(_m.group(1))] = [int(x) for x in _m.group(2).replace(' ', '').split(',') if x]
def wc(s): return len(s.split())
def stems(s): return {w[:5] for w in re.findall(r'[а-яё]{5,}', s.lower())}
def split_sent(t):
    out = []; d1 = d2 = 0; sl = False; start = 0; i = 0; n = len(t)
    while i < n:
        ch = t[i]
        if ch == '«': d1 += 1
        elif ch == '»': d1 = max(0, d1 - 1)
        elif ch == '(': d2 += 1
        elif ch == ')': d2 = max(0, d2 - 1)
        elif ch == '/' and i + 1 < n and t[i + 1] == '/': sl = not sl; i += 1
        elif ch in '.!?' and d1 == 0 and d2 == 0 and not sl and i + 1 < n and t[i + 1] == ' ':
            j = i + 1
            while j < n and t[j] == ' ': j += 1
            nx = t[j:j + 2]
            m = re.search(r'([А-Яа-яёA-Za-z№]+)$', t[start:i]); w = m.group(1).lower() if m else ''
            if j < n and (nx[:1].isupper() or nx[:1] in '«*/') and not (ch == '.' and (w in ABBR or len(w) == 1)):
                out.append(t[start:i + 1]); start = j; i = j; continue
        i += 1
    if t[start:].strip(): out.append(t[start:])
    return out
TXT = ('p', 'li', 'sub', 'num')
LST = ('li', 'sub', 'num')
class Unit:
    def __init__(s, line, sec, kind):
        s.line = line; s.sec = sec; s.kind = kind; s.dead = False; s.prot = False; s.block = None
        m = re.match(r'^(\s*- |> |!! |\d+\. )?(.*)$', line, re.S); s.pre = m.group(1) or ''; body = m.group(2)
        s.sents = split_sent(body) if kind in TXT else [body]
    def text(s): return s.pre + ' '.join(x.strip() for x in s.sents)
    def words(s): return 0 if s.dead else wc(s.text())
def parse(txt):
    units = []; sec = 0; heads = {}
    for line in txt.split('\n'):
        if not line.strip(): continue
        if line.startswith('# '): k = 'title'
        elif line.startswith('## '): sec += 1; k = 'head'; heads[sec] = line
        elif line.startswith('> '): k = 'def'
        elif line.startswith('!! '): k = 'bang'
        elif line.startswith('- '): k = 'li'
        elif line.startswith('  - '): k = 'sub'
        elif re.match(r'\d+\. ', line): k = 'num'
        else: k = 'p'
        units.append(Unit(line, sec, k))
    return units, heads
def ref_ctx(r):
    """(акт, статья) из текста ссылки; None — нет"""
    m = re.search(r'[А-ЯЁA-Z№]', r[1:]); act = None
    if m:
        a = r[1 + m.start():]
        if not re.match(r'(Ч|П|Ст|Гл|Подп|Абз)\.', a): act = re.sub(r'[^а-яёa-z0-9№]', '', a.lower())[:14]
    arts = re.findall(r'[Сс]т\.\s*([\d.]+\d)', r)
    return act, (arts[-1] if arts else None)
def resolve(pieces, skip=frozenset()):
    """pieces: [(id, текст)] по порядку; возвращает {(id, k): (акт, статья)} для ссылок вне skip"""
    act = art = None; res = {}
    for pid, t in pieces:
        if pid in skip: continue
        for k, m in enumerate(REF.finditer(t)):
            a, s = ref_ctx(m.group(1))
            if a: act = a; art = s
            elif s: art = s
            res[(pid, k)] = (act, art)
    return res
def cut(txt, F, log=None):
    units, heads = parse(txt); title = units[0].line; tst = stems(title)
    w0 = wc(txt); target = int(w0 * F)
    cur = lambda: sum(u.words() for u in units)
    prav = {k for k, h in heads.items() if PRAV.search(h)}
    match = {k: bool(stems(re.sub(r'^## \d+\. ', '', h)) & tst) for k, h in heads.items()}
    # защита абзаца «Правовая основа» и перечня под ним
    for i, u in enumerate(units):
        if u.kind == 'p' and PRAV.search(u.line[:70]):
            u.prot = True; j = i + 1
            while j < len(units) and units[j].kind in LST: units[j].prot = True; j += 1
    # блоки: абзац; перечень целиком с вводной строкой; перечень самостоятельных тезисов делится на «атомы» (пункт с подпунктами)
    def is_intro(u): return u.kind == 'p' and (u.line.rstrip().rstrip('*').endswith(':') or re.match(r'\(//[^/]+//\)$', u.line.strip()))
    blocks = []; atoms = {}; i = 0
    while i < len(units):
        u = units[i]
        if u.kind in ('title', 'head', 'bang'): i += 1; continue
        b = [u]; j = i + 1
        if u.kind in LST or is_intro(u):
            while j < len(units) and units[j].kind in LST and units[j].sec == u.sec: b.append(units[j]); j += 1
        i = j
        tops = [x for x in b if x.kind == 'li']
        thesis = u.kind == 'li' and all(x.kind != 'num' for x in b) and not any(x.line.rstrip().endswith(';') for x in tops)
        if thesis and sum(1 for x in tops if SEQ.match(x.line)) >= max(2, 0.6 * len(tops)): thesis = False   # структура статьи, нумерованные элементы
        if thesis and COUNT.search(heads.get(u.sec, '').lower()): thesis = False                           # «три этапа», «двенадцать оснований»
        if thesis:
            grp = None; par = None
            for x in b:
                low = re.match(r'- [а-яё«(/]', x.line) is not None
                if x.kind == 'sub' or (par is not None and x.kind == 'li' and low): grp.append(x)
                elif grp is not None and ANA.match(re.sub(r'^- (\*\*)?', '', x.line)): grp.append(x); par = None
                else:
                    grp = [x]; blocks.append(grp)
                    par = x if x.line.rstrip().rstrip('*').endswith(':') else None
        elif u.kind == 'p' and len(b) == 1 and blocks and blocks[-1][0].sec == u.sec and blocks[-1][-1].kind == 'p' and ANA.match(re.sub(r'^(\*\*)?', '', u.line)): blocks[-1].append(u)
        else: blocks.append(b)
    for b in blocks:
        for x in b: x.block = b
    def pieces():
        res = []
        for u in units:
            if u.dead: continue
            if u.kind in TXT:
                for k, s in enumerate(u.sents): res.append(((id(u), k), s))
            else: res.append(((id(u), 0), u.line))
        return res
    def safe(skip_ids, removed_text):
        ps = pieces(); skip = frozenset(skip_ids)
        rest = ' '.join(t for pid, t in ps if pid not in skip)
        for ab in re.findall(r'далее —\s+([^)/;»]+?)[)/;»]', removed_text):
            ab = ab.strip(' .'); key = ab[:-1] if len(ab) > 6 else ab
            if key and key in rest: return False
        if '//' not in removed_text: return True
        a = resolve(ps); b = resolve(ps, skip)
        return all(a[k] == v for k, v in b.items())
    def kill_units(us, name, label):
        ids = [(id(u), k) for u in us for k in range(len(u.sents) if u.kind in TXT else 1)]
        t = ' '.join(u.text() for u in us)
        if not safe(ids, t): return False
        for u in us: u.dead = True
        if log is not None: log.append('%s −%d: %s' % (name, wc(t), label[:80]))
        return True
    stat = {}
    # 1. разделы, выбранные вручную (drop25.txt); если списка для ответа нет — по ключевым словам заголовка
    qn = int(re.search(r'Вопрос (\d+)', title).group(1))
    if qn in DROP:
        for k in sorted(DROP[qn], reverse=True):
            if k not in heads or k == 1 or k in prav: SKIP.append((qn, k, 'нет/защищён')); continue
            us = [u for u in units if u.sec == k and not u.dead]
            if not kill_units(us, 'РАЗДЕЛ', heads[k]): SKIP.append((qn, k, 'небезопасно'))
    else:
        for k in sorted(heads, reverse=True):
            if k == 1 or k in prav or cur() <= target: continue
            hs = re.sub(r'^## \d+\. ', '', heads[k].lower())
            if not [p for p in PERI if p in hs and not any(p.strip()[:5] in w for w in re.findall(r'[а-яё]+', title.lower()))]: continue
            us = [u for u in units if u.sec == k and not u.dead]
            if cur() - sum(u.words() for u in us) < target - 40: continue
            kill_units(us, 'РАЗДЕЛ', hs)
    stat['sec'] = cur()
    def cls(s): return 1 if '«' in s else 2 if '//' in s else 3
    def tails(mincls, allow_exc, name):
        while cur() > target:
            cs = []
            for u in units:
                if u.dead or u.kind not in TXT or u.sec in prav or u.sec == 1 or u.prot or len(u.sents) < 2 or u.text().rstrip().endswith(':'): continue
                s = u.sents[-1]; c = cls(s)
                if c < mincls or (not allow_exc and EXC.search(s.lower())): continue
                if not safe([(id(u), len(u.sents) - 1)], s): continue
                cs.append((c, wc(u.text()), id(u), u))
            if not cs: break
            cs.sort(key=lambda x: x[:3], reverse=True); u = cs[0][3]; s = u.sents.pop()
            if log is not None: log.append('%s −%d: %s' % (name, wc(s), s[:80]))
        stat[name] = cur()
    # 2. пояснительные хвостовые предложения без ссылки и цитаты
    tails(3, False, 't3')
    # 3. соразмерное сокращение разделов: у каждого раздела свой бюджет, первый блок раздела остаётся,
    #    остальные блоки убираются в порядке: без цитаты → не связанные с формулировкой вопроса → ближе к концу
    body = [k for k in heads if k != 1 and k not in prav]
    def sec_atoms(k):
        res = []
        for bl in blocks:
            if bl[0].sec == k and any(not x.dead for x in bl): res.append(bl)
        return res
    def aw(bl): return sum(x.words() for x in bl)
    def rel(bl): return len(stems(' '.join(x.text() for x in bl)) & tst)
    def trim(rounds, name, keep_first=True):
        for _ in range(rounds):
            excess = cur() - target
            if excess <= 25: break
            cand = {k: [bl for bl in sec_atoms(k)[(1 if keep_first else 0):] if not any(x.prot or x.kind == 'def' for x in bl)] for k in body}
            if not keep_first:
                for k in body:
                    if len(sec_atoms(k)) < 2: cand[k] = []      # последний блок раздела не убираем
            pool = sum(aw(bl) for k in body for bl in cand[k])
            if pool == 0: break
            share = min(1.0, excess / pool); progress = False
            for k in body:
                need = share * sum(aw(bl) for bl in cand[k]); got = 0
                order = sorted(enumerate(cand[k]), key=lambda x: (cls(' '.join(u.text() for u in x[1])) == 1, min(rel(x[1]), 2), -x[0]))
                for _i, bl in order:
                    w = aw(bl)
                    if got + w / 2 > need or cur() - w < target - 30: continue
                    us = [x for x in bl if not x.dead]
                    if kill_units(us, name, us[0].text()): got += w; progress = True
            if not progress: break
        stat[name] = cur()
    trim(6, 'b')
    tails(3, True, 't3e'); tails(2, False, 't2')
    trim(4, 'b2')
    tails(2, True, 't2e'); tails(1, False, 't1')
    trim(3, 'b3', keep_first=False)
    # сборка
    out = []; prev = None
    for u in units:
        if u.dead: continue
        if u.kind in TXT:
            t = u.text().rstrip()
            if u.line.rstrip().endswith(';') and t.endswith('.'): t = t[:-1] + ';'
        else: t = u.line
        if prev is not None and not (u.kind in LST and prev in LST): out.append('')
        out.append(t); prev = u.kind
    t = '\n'.join(out)
    # подпись (целиком полужирная строка), после которой не осталось текста
    for _ in range(3): t = re.sub(r'(?m)^\*\*[^*\n]{1,80}\*\*\n\n(?=\*\*[^*\n]{1,80}\*\*\n|## |!! |\Z)', '', t)
    # раздел без текста
    for _ in range(3): t = re.sub(r'(?m)^## [^\n]*\n\n(?=## |!! |\Z)', '', t)
    k = 0
    def ren(m):
        nonlocal k; k += 1; return '## %d. ' % k
    t = re.sub(r'(?m)^## \d+\. ', ren, t) + '\n'
    return t, w0, target, stat
if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'show':
        n = int(sys.argv[2]); F = float(sys.argv[3]) if len(sys.argv) > 3 else F_DEF; log = []
        t, w0, tg, st = cut(open(A + 'q%03d.txt' % n, encoding='utf-8').read(), F, log)
        print(w0, tg, wc(t), st); print('\n'.join(log))
        if len(sys.argv) > 4: print(t)
    else:
        F = float(sys.argv[2]) if len(sys.argv) > 2 else F_DEF; T0 = T1 = 0; agg = {}; bad = []; low = []
        for f in sorted(glob.glob(A + 'q*.txt')):
            txt = open(f, encoding='utf-8').read(); t, w0, tg, st = cut(txt, F)
            T0 += w0; T1 += wc(t)
            for k, v in st.items(): agg[k] = agg.get(k, 0) + v
            if wc(t) > tg + 40: bad.append((f[-7:-4], tg, wc(t)))
            if wc(t) < tg - 60: low.append((f[-7:-4], tg, wc(t)))
            if mode == 'apply': open(f, 'w', encoding='utf-8').write(t)
        print('было', T0, 'стало', T1, 'доля', round(T1 / T0, 3)); print(agg); print('не дотянули:', len(bad), bad[:60]); print('перебор:', [(f, tg, w) for f, tg, w in low]); print('разделы не убраны:', SKIP)
