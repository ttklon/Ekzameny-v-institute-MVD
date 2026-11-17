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
F_DEF = 0.58
PERI = ['отграничен', 'отлич', 'смежн', 'ответственност', 'взаимодейств', 'гаранти', 'проблем', 'практическ', 'значени', 'соотношен', 'обжалован', 'оформлен',
        'контроль', 'надзор', 'особенност', 'иные ', 'другие ', 'други', 'история', 'зарубеж', 'перспектив', 'статистик', 'последстви', 'связь', 'оценк', 'пределы', 'ошибк', 'итог', 'вывод', 'краткий']
ABBR = {'ст', 'ч', 'п', 'подп', 'абз', 'гл', 'разд', 'утв', 'г', 'гг', 'т', 'см', 'др', 'пр', 'им', 'ул', 'руб', 'тыс', 'млн', 'е', 'д', 'н', 'э', 'ред', 'рис', 'табл', 'прим', 'стр'}
EXC = re.compile(r'не допуска|запрещ|исключени|кроме |однако|нельзя|не вправе|не может|только ')
PRAV = re.compile(r'[Пп]равов\w+ (основ|регулир|база)|[Нн]ормативн\w+ (основ|база|правов|закрепл)|[Ии]сточники|[Кк]онституционн\w+ (и законодательн\w+ )?основ')
REF = re.compile(r'//(.+?)//')
SEQ = re.compile(r'- \*\*(//)?(Ч|Ст|П|Подп|Гл|Часть|Статья|Пункт|Глава|Перв|Втор|Трет|Четв|Пят|Шест|Седьм|Восьм|Девят|Десят|\d)')
COUNT = re.compile(r'\b(два|две|двух|три|трёх|четыре|четырёх|пять|шесть|семь|восемь|девять|десять|одиннадцать|двенадцать|тринадцать|перечень|структура|система|виды|вид|классификаци\w+|группы|наказани\w+|санкци\w+|состав|составы|элементы|алгоритм|порядок действий|этапы|стадии)\b')
ANA = re.compile(r'(Его|Её|Их|Ему|Ей|Им|Эти|Этот|Эта|Это|Этим|Этой|Этого|Этих|Такой|Такие|Такое|Такая|Таким|При этом|Кроме того|Также|Он|Она|Они|Оно|Там же|Тот же|Те же|Та же|То же|В этом|В этих|В таком|В таких|Для этого|Поэтому|Однако|Но|А|И|Вместе с тем|Наряду с этим|Указанн\w+|Названн\w+|Данн\w+|Последн\w+|Иначе|Тогда|Здесь|Отсюда|Остальн\w+|В остальн\w+|Помимо этого|Например|Так|В частности|То есть|Исключени\w+|Следовательно|Значит|Соответственно|Тем самым|В обоих|Оба|Обе|Второй|Вторая|Второе|Третий|Третья|Третье)[ ,:—]')
ELEM = re.compile(r'\*\*(объект|объективная сторона|субъект|субъективная сторона|предмет|родовой объект|видовой объект)')
DROP = {}; SKIP = []; AUTO = []; AUTOSEC = False; LEFT = {}; BC = {}

_d = os.path.join(HERE, 'drop25.txt')
if os.path.exists(_d):
    for _l in open(_d, encoding='utf-8'):
        _m = re.match(r'(\d+):\s*([\d,\s]*)$', _l.strip())
        if _m: DROP.setdefault(int(_m.group(1)), []).extend(int(x) for x in _m.group(2).replace(' ', '').split(',') if x)
def wc(s): return len(s.split())
def stems(s): return {w[:5] for w in re.findall(r'[а-яё]{5,}', s.lower())}
def stems4(s): return {w[:4] for w in re.findall(r'[а-яё]{4,}', s.lower())}
def _generic():
    cnt = {}; fs = sorted(glob.glob(A + 'q*.txt'))
    for f in fs:
        with open(f, encoding='utf-8') as fh: t = fh.readline()
        for x in stems4(re.sub(r'^# Вопрос \d+\. ', '', t)): cnt[x] = cnt.get(x, 0) + 1
    return {x for x, c in cnt.items() if c > 0.08 * max(len(fs), 1)}
GENERIC = _generic()
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
        s.sents = split_sent(body) if kind in TXT or kind == 'bang' else [body]
    def text(s): return s.pre + ' '.join(x.strip() for x in s.sents) if s.kind in TXT or s.kind == 'bang' else s.line
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
UNITW = r'(?:[Чч]|[Пп]|[Сс]т|[Гл]л|[Пп]одп|[Аа]бз|[Рр]азд)\.'
def ref_ctx(r):
    """(ключ акта, статья, название акта как в ссылке) из текста ссылки"""
    m = re.search(r'(?<![А-Яа-яёЁ])(?!' + UNITW + r')[А-ЯЁA-Z№][^/]*$', r[1:]) if len(r) > 1 else None
    act = disp = None
    if re.match(r'(?!' + UNITW + r')[А-ЯЁ]', r): m2 = r
    else: m2 = r[1 + m.start():] if m else None
    if m2:
        disp = m2.strip(); act = re.sub(r'[^а-яёa-z0-9№]', '', disp.lower())[:14]
        if not act: act = disp = None
    arts = re.findall(r'[Сс]т\.\s*([\d.]+\d)', r)
    return act, (arts[-1] if arts else None), disp
def resolve(pieces, skip=frozenset()):
    """pieces: [(id, текст)] по порядку; {(id, k): (акт, статья)} и {(id, k): название акта} для ссылок вне skip"""
    act = art = disp = None; res = {}; names = {}
    for pid, t in pieces:
        if pid in skip: continue
        if t.startswith('## '):                      # контекст ссылок действует в пределах раздела
            act = art = disp = None
            m = re.findall(r'[Сс]т\.\s*([\d.]+\d)', t)
            if m and '//' not in t: art = m[-1]
        for k, m in enumerate(REF.finditer(t)):
            a, s, d = ref_ctx(m.group(1))
            if a: act = a; art = s; disp = d
            elif s: art = s
            res[(pid, k)] = (act, art); names[(pid, k)] = disp
    return res, names
NOM = {'КоАП РФ': '//Кодекс Российской Федерации об административных правонарушениях//', 'Уголовный кодекс': '//Уголовный кодекс Российской Федерации//', 'УК РФ': '//Уголовный кодекс Российской Федерации//',
       'УПК РФ': '//Уголовно-процессуальный кодекс Российской Федерации//', 'КАС РФ': '//Кодекс административного судопроизводства Российской Федерации//', 'Семейный кодекс': '//Семейный кодекс Российской Федерации//',
       'Закон о полиции': '//Федеральный закон от 07.02.2011 № 3-ФЗ «О полиции»//', 'Закон о службе': '//Федеральный закон от 30.11.2011 № 342-ФЗ «О службе в органах внутренних дел Российской Федерации и внесении изменений в отдельные законодательные акты Российской Федерации»//',
       'Закон о прокуратуре': '//Федеральный закон от 17.01.1992 № 2202-1 «О прокуратуре Российской Федерации»//', 'Росгвардия': 'Федеральная служба войск национальной гвардии Российской Федерации'}
NOMMAP = [('Федерального конституционного закона', 'Федеральный конституционный закон'), ('Федерального закона', 'Федеральный закон'), ('Закона Российской Федерации', 'Закон Российской Федерации'),
          ('Кодекса', 'Кодекс'), ('Уголовного кодекса', 'Уголовный кодекс'), ('Уголовно-процессуального кодекса', 'Уголовно-процессуальный кодекс'), ('Трудового кодекса', 'Трудовой кодекс'), ('Гражданского кодекса', 'Гражданский кодекс'),
          ('Воздушного кодекса', 'Воздушный кодекс'), ('Семейного кодекса', 'Семейный кодекс'), ('Лесного кодекса', 'Лесной кодекс'), ('Водного кодекса', 'Водный кодекс'), ('Указа', 'Указ'), ('Типового положения', 'Типовое положение'),
          ('Примерного положения', 'Примерное положение'), ('Положения', 'Положение'), ('Наставления', 'Наставление'), ('Инструкции', 'Инструкция'), ('Правил', 'Правила'), ('Порядка', 'Порядок'), ('Приказа', 'Приказ'), ('приказа', 'Приказ'),
          ('Постановления', 'Постановление'), ('постановления', 'Постановление'), ('Устава', 'Устав'), ('Административного регламента', 'Административный регламент'), ('Требований', 'Требования'), ('Концепции', 'Концепция'), ('Перечня', 'Перечень'),
          ('Конституции', 'Конституция'), ('Основ', 'Основы'), ('Руководства', 'Руководство'), ('Стратегии', 'Стратегия'), ('Доктрины', 'Доктрина')]
def to_nom(ref):
    """//ч. 1 ст. 2 Федерального закона …// → //Федеральный закон …//; None — не удалось"""
    r = ref.strip('/').strip()
    m = re.search(r'(?<![А-Яа-яёЁ])(?!' + UNITW + r')[А-ЯЁ]|(?<![а-яё])(приказа|постановления) ', r)
    if not m: return None
    r = r[m.start():]
    for g, n in sorted(NOMMAP, key=lambda x: -len(x[0])):
        if r.startswith(g + ' '): return '//' + n + r[len(g):] + '//'
    if re.match(r'(Федеральный|Кодекс|Закон|Указ|Положение|Наставление|Инструкция|Правила|Порядок|Приказ|Постановление|Устав|Типовое|Уголовный|Трудовой|Семейный|Воздушный|Конституция|Административный|Требования|Концепция|Перечень|Основы|Примерное|Лесной|Водный|Гражданский|Стратегия|Руководство)\\b', r): return '//' + r + '//'
    return None
def abbr_used(ab, text):
    """используется ли сокращённое название (в любом падеже) в тексте"""
    if '№' in ab:
        return re.search(r'(?<![\\d/-])' + re.escape(ab[ab.index('№'):]) + r'(?![\\d/-])', text) is not None
    ws = ab.split()
    pat = r'\\s+'.join(re.escape(w[:max(3, len(w) - 2)]) + r'\\w*' if len(w) > 3 else re.escape(w) for w in ws)
    return re.search(r'(?<![А-Яа-яёЁ])' + pat, text) is not None
GEN = re.compile(r'//(Федерального|Кодекса|Закона|Указа|Положения|Наставления|Инструкции|Правил|Порядка|[Пп]риказа|[Пп]остановления|Типового|Устава|Требований|Административного|Руководства|Концепции|Перечня|Уголовного|Трудового|Гражданского|Воздушного|Семейного|Основ|Конституции)\b')
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
        if thesis and len(ELEM.findall(' '.join(x.line[:60].lower() for x in tops))) >= 2: thesis = False       # элементы состава
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
    def check(skip_ids, removed_text, fix=False):
        """None — удалять нельзя; иначе список (полное название, сокращение) для переноса в «Правовую основу».
        fix=True: неполная ссылка ниже, которая после удаления стала бы относиться к другому акту или статье, дополняется."""
        ps = pieces(); skip = frozenset(skip_ids); move = []
        rest = ' '.join(t for pid, t in ps if pid not in skip)
        for m in re.finditer(r'далее —\s+([^)/;»]+?)[)/;»]', removed_text):
            ab = m.group(1).strip(' .')
            if not ab or not abbr_used(ab, rest): continue
            if re.search(r'далее —\s+' + re.escape(ab), rest): continue
            if ab in NOM: move.append((NOM[ab], ab)); continue
            fm = re.search(r'(//[^/]+//|«[^«»]+(?:«[^«»]*»[^«»]*)*»(?:,? утв\.[^()]*?)?)\s*\(далее —\s+' + re.escape(ab) + r'\)', removed_text)
            if not fm: return None
            full = fm.group(1).strip()
            if full.startswith('//'):
                full = to_nom(full)
                if not full: return None
            elif 'утв' not in full: return None
            move.append((full, ab))
        if '//' in removed_text:
            um = {id(u): u for u in units}
            ps2 = [x for x in ps if um[x[0][0]].kind != 'bang']       # «Главное для запоминания» — самостоятельный текст
            a, na = resolve(ps2); b, _ = resolve(ps2, skip)
            bad = [k for k in b if a[k] != b[k]]
            if bad and not fix: return None
            patches = []
            for _ in range(6):
                if not bad: break
                k = bad[0]; (pid, si), ri = k; u = um[pid]
                if u.kind not in TXT or a[k][0] is None or na[k] is None: return None
                refs = list(REF.finditer(u.sents[si])); m = refs[ri]; r = m.group(1)
                add = ''
                if a[k][1] and not re.search(r'[Сс]т\.', r): add += ' ст. ' + a[k][1]
                add += ' ' + na[k]
                old = u.sents[si]; u.sents[si] = old[:m.end(1)] + add + old[m.end(1):]; patches.append((u, si, old))
                ps = pieces(); ps2 = [x for x in ps if um[x[0][0]].kind != 'bang']
                a2, _n = resolve(ps2, skip)
                bad = [kk for kk in a2 if kk in a and a[kk] != a2[kk]]
            if bad:
                for u, si, old in reversed(patches): u.sents[si] = old
                return None
            if log is not None:
                for u, si, old in patches: log.append('ССЫЛКА дополнена: ' + u.sents[si][:110])
        return move
    def safe(skip_ids, removed_text): return check(skip_ids, removed_text) == []
    def kill_units(us, name, label):
        ids = [(id(u), k) for u in us for k in range(len(u.sents) if u.kind in TXT else 1)]
        t = ' '.join(u.text() for u in us)
        move = check(ids, t)      # ссылки автоматически не дополняются: при риске удаление отменяется
        if move is None: return False
        if move:
            pl = [i for i, u in enumerate(units) if u.sec in prav and u.kind == 'li' and not u.dead]
            if not pl: return False     # (ссылки, дополненные выше, остаются дополненными — это безвредно)
            at = pl[-1]
            for full, ab in move:
                nu = Unit('- %s (далее — %s).' % (full, ab), units[at].sec, 'li'); nu.prot = True; nu.block = [nu]
                at += 1; units.insert(at, nu)
                if log is not None: log.append('ПЕРЕНОС в «Правовую основу»: ' + nu.line[:110])
        for u in us: u.dead = True
        if log is not None: log.append('%s −%d: %s' % (name, wc(t), label[:80]))
        return True
    stat = {}
    # 1. разделы, выбранные вручную (drop25.txt); если списка для ответа нет — по ключевым словам заголовка
    qn = int(re.search(r'Вопрос (\d+)', title).group(1))
    if qn in DROP:
        for k in sorted(DROP[qn], reverse=True):
            if k not in heads or k == 1 or k in prav: SKIP.append((qn, k, 'нет/защищён')); continue
            us = [u for u in units if u.sec == k and not u.dead and u.kind != 'bang']
            if not kill_units(us, 'РАЗДЕЛ', heads[k]): SKIP.append((qn, k, 'небезопасно'))
    else:
        for k in sorted(heads, reverse=True):
            if k == 1 or k in prav or cur() <= target: continue
            hs = re.sub(r'^## \d+\. ', '', heads[k].lower())
            if not [p for p in PERI if p in hs and not any(p.strip()[:5] in w for w in re.findall(r'[а-яё]+', title.lower()))]: continue
            us = [u for u in units if u.sec == k and not u.dead and u.kind != 'bang']
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
    body = [k for k in heads if k not in prav]      # в разделе 1 определение и первый блок защищены
    def sec_atoms(k):
        res = []
        for bl in blocks:
            if bl[0].sec == k and any(not x.dead for x in bl): res.append(bl)
        return res
    def aw(bl): return sum(x.words() for x in bl)
    def rel(bl): return len(stems4(' '.join(x.text() for x in bl)) & tst4)
    size0 = {}
    for bl in blocks: size0[bl[0].sec] = size0.get(bl[0].sec, 0) + 1
    tst4 = stems4(title) - GENERIC
    core = {k: len(stems4(re.sub(r'^## \d+\. ', '', h)) & tst4) >= 2 for k, h in heads.items()}     # раздел прямо отвечает на формулировку вопроса
    def trim(rounds, name, with_core=False):
        """прореживание: первый блок раздела остаётся; в разделе остаётся не меньше половины блоков (и не меньше двух)"""
        for _ in range(rounds):
            excess = cur() - target
            if excess <= 25: break
            cand = {}
            for k in body:
                at = sec_atoms(k); floor = max(2, -(-size0.get(k, 0) * (7 if core[k] else 4) // 10)); free = max(0, len(at) - floor)
                cand[k] = ([bl for bl in at[1:] if not any(x.prot or x.kind == 'def' for x in bl)], free)
            pool = sum(aw(bl) for k in body for bl in cand[k][0])
            if pool == 0: break
            share = min(1.0, excess / pool); progress = False
            for k in body:
                cs, free = cand[k]
                need = share * sum(aw(bl) for bl in cs); got = 0
                order = sorted(enumerate(cs), key=lambda x: (cls(' '.join(u.text() for u in x[1])) == 1, min(rel(x[1]), 2), -x[0]))
                for _i, bl in order:
                    w = aw(bl)
                    if free <= 0: break
                    if got + w / 2 > need or cur() - w < target - 30: continue
                    us = [x for x in bl if not x.dead]
                    if kill_units(us, name, us[0].text()): got += w; progress = True; free -= 1
            if not progress: break
        stat[name] = cur()
    def auto_sections(name):
        """если прореживания не хватило — убираются целые разделы: сначала не связанные с формулировкой вопроса, ближе к концу"""
        while cur() - target > 60:
            excess = cur() - target; live = [k for k in body if sec_atoms(k)]
            if len(live) <= 3: break
            cs = []
            for k in live[1:]:
                us = [u for u in units if u.sec == k and not u.dead and u.kind != 'bang']
                if any(u.prot for u in us): continue
                w = sum(u.words() for u in us)
                if w > excess + 45: continue
                cs.append((match[k], -k, w, us, k))
            done = False
            for c in sorted(cs, key=lambda x: x[:2]):
                if kill_units(c[3], name, heads[c[4]]): AUTO.append((qn, heads[c[4]][:60], c[2])); done = True; break
            if not done: break
        stat[name] = cur()
    trim(6, 'b')
    tails(3, True, 't3e'); tails(2, False, 't2')
    if AUTOSEC: auto_sections('s2')
    trim(3, 'b2')
    tails(2, True, 't2e'); tails(1, False, 't1')
    # «Главное для запоминания»: убираются предложения о том, чего в ответе больше нет
    gone = stems(' '.join(u.line for u in units if u.dead)); kept = stems(' '.join(u.text() for u in units if not u.dead and u.kind != 'bang'))
    for u in units:
        if u.kind != 'bang': continue
        keep = []
        for i, sn in enumerate(u.sents):
            st = stems(sn); nov = (st - kept) & gone
            if i >= 2 and len(st) >= 3 and len(nov) >= max(2, 0.3 * len(st)):
                if log is not None: log.append('!! −%d: %s' % (wc(sn), sn[:90]))
                continue
            keep.append(sn)
        u.sents = keep
    stat['bang'] = cur()
    LEFT[qn] = (cur() - target, [(k, re.sub(r'^## \d+\. ', '', heads[k])[:26], sum(u.words() for u in units if u.sec == k and u.kind not in ('bang', 'head')), 'P' if k in prav else 'C' if core[k] else '') for k in heads if any(not u.dead for u in units if u.sec == k and u.kind != 'head' and u.kind != 'bang')])
    # сборка
    out = []; prev = None
    for u in units:
        if u.dead: continue
        if u.kind in TXT or u.kind == 'bang':
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
        if mode == 'left':
            for n in sorted(LEFT):
                if LEFT[n][0] > 45: print('%d|+%d|%s' % (n, LEFT[n][0], '|'.join('%d%s %s=%d' % (k, f, h, w) for k, h, w, f in LEFT[n][1])))
        print('разделы убраны автоматически:', len(AUTO))
        for x in AUTO: print('  ', x)
