#!/usr/bin/env python3
"""actline26.py SRC ПАПКА_ОТВЕТОВ [-t ПОРОГ] [-q N,N…] — отрезок ответа по АДП против названной нормы любого акта, кроме КоАП РФ
(КоАП сверяет koapline26.py). Строка делится на отрезки (между «;» и концами предложений); для отрезка берутся ссылки, стоящие в нём
(если в отрезке ссылок нет — все ссылки строки). Акт неполной ссылки («ст. 13», «ч. 2», «п. 5») подбирается из нескольких:
последний названный выше закон (название акта в заголовке раздела и слова «КоАП РФ», «УК РФ», «КАС РФ», «Закон о полиции» перед
ссылкой тоже считаются), главный закон ответа (первый, для которого введено сокращение «далее — …»); для «п. N» — последний
названный акт без статей, акт, названный дальше в той же строке, пункт текущей статьи. Берётся тот, в котором такая норма есть и
совпадение с отрезком выше. По ссылке достаётся текст нормы: статья → часть → пункт, для актов без статей — пункт → подпункт.
Считается доля слов отрезка, которые есть в норме. Печатается:
  НЕТ   — норма с таким номером не найдена ни в одном из подходящих актов;
  АКТ?  — неполная ссылка стоит в разделе после ссылки на другой закон, а норма нашлась не в нём, а в главном законе ответа:
          читатель может отнести ссылку не к тому акту (совпадение при этом может быть высоким);
  ИНОЕ  — совпадение с названной нормой ниже ПОРОГА (по умолчанию 40 %), а в другом месте того же акта — заметно выше
          (вероятна ошибка в номере пункта, части, статьи); показано это место;
  ~NN%  — совпадение ниже ПОРОГА.
Под отрезком — кусок названной нормы с наибольшим совпадением. Пометка не означает ошибку: отрезок читается глазами.
ПАПКА_ОТВЕТОВ — папка с файлами qNNN.txt (adp2 или вариант 1, разрезанный по вопросам).
Ключ -v дополнительно печатает ссылки, акт которых определить не удалось (нет текста акта в базе либо акт не назван).
    python3 tools/actline26.py /tmp/src adp2 -q 31,32
"""
import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
argv = [a for a in sys.argv[1:] if a != '-v']; THR = 40; ONLY = None
if '-t' in argv: i = argv.index('-t'); THR = int(argv[i + 1]); del argv[i:i + 2]
if '-q' in argv: i = argv.index('-q'); ONLY = {int(x) for x in argv[i + 1].split(',')}; del argv[i:i + 2]
SRC, A = argv[0], argv[1]
import cut25
files = {}
for l in open(os.path.join(SRC, '_index.tsv'), encoding='utf-8'):
    nm, rel = l.rstrip('\n').split('\t'); files[nm + ' ' + rel] = os.path.join(SRC, nm)
def nkey(s): return re.sub(r'[^а-яёa-z0-9№]', '', s.lower())
NAMED = [(r'ополиции|№3фз', r'№ 3-ФЗ О полиции'), (r'коап|обадминистративныхправ', 'KOAP'), (r'ослужбе', r'№ 342-ФЗ'), (r'опрокуратуре', r'№ 2202-1'),
         (r'уголовногокодекса|^укрф|уголовныйкодекс', r'Уголовный кодекс РФ от'), (r'уголовнопроцесс|упкрф', r'Уголовно-процессуальный кодекс РФ от'), (r'конституци', 'SKIP'),
         (r'положенияоминистерстве|положениеоминистерстве|положенияомвд|положениеомвд', r'№ 699'), (r'кодексаэтики|кодексэтики', r'№ 460'),
         (r'онаркотическ', r'№ 3-ФЗ О наркотических'), (r'оборужии', r'№ 150-ФЗ'), (r'очрезвычайномположении', r'№ 3-ФКЗ'), (r'овоенномположении', r'№ 1-ФКЗ'),
         (r'обезопасности$', r'№ 390-ФЗ'), (r'оспорте$', r'№ 329-ФЗ'), (r'опрофилактике$', r'№ 182-ФЗ'), (r'оправительстве', r'№ 4-ФКЗ'), (r'осоциальныхгарантиях', r'№ 247-ФЗ'),
         (r'воздушн', r'Воздушный кодекс'), (r'кввт|внутреннеговодноготранспорта', r'Кодекс внутреннего водного транспорта'), (r'административногосудопроизводства|касрф', r'КАС РФ от'),
         (r'семейн', r'Семейный кодекс'), (r'гражданскогокодекса|гражданскийкодекс|^гкрф', r'Гражданский кодекс'), (r'дисциплинарн', r'№ 1377'),
         (r'правил[а]?дорожногодвижения', r'№ 1090'), (r'положени[ея]опаспорте', r'№ 2267'), (r'^руководств', r'№ 444 Руководство')]
ALIAS = {}; HOME = [None, None]; RAW = ['']
DATES = {}                                       # номер акта → дата из полного названия в этом же ответе
def act_pat(disp):
    """образец имени файла акта; после «@» — дата акта, если она известна (номера у разных актов совпадают)"""
    m = re.search(r'№ ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', disp)
    if m and m.group(1) not in ('3-ФЗ', '195-ФЗ', '342-ФЗ', '2202-1', '63-ФЗ', '174-ФЗ'):
        d = re.search(r'от (\d\d\.\d\d\.\d{4}) № ?' + re.escape(m.group(1)), disp)
        date = d.group(1) if d else DATES.get(m.group(1))
        return r'№ ' + re.escape(m.group(1).split('/')[0]) + r'(?![\d-])' + ('@' + date if date else '')
    key = nkey(disp)
    for pat, fp in NAMED:
        if re.search(pat, key): return fp
    for ak, fp in ALIAS.items():                 # «(далее — Инструкция)»
        if key.startswith(ak[:max(5, len(ak) - 2)]): return fp
    w = re.match(r'[А-ЯЁа-яё]+(?: [а-яё]+)?', disp)   # «Наставления», «Типового положения» — по первому «… № N» после этого слова в ответе
    if w and not m and not re.match(r'Закон|Кодекс|Федеральн|Устав', disp):
        st = r'\w* '.join(x[:max(4, len(x) - 2)] for x in w.group(0).split()) + r'\w*'
        h = re.search(r'(?i)' + st + r'[^№\n]{0,200}№ ?(\d+(?:[/.-]\d+)*)', RAW[0])
        if h: return act_pat('№ ' + h.group(1))
    return None
def clean(raw):
    raw = re.sub(r'\s+', ' ', raw)
    raw = re.sub(r'Стр\. \d+ из \d+', ' ', raw)
    raw = re.sub(r'<\d+>', ' ', raw)
    raw = re.sub(r'\((?:В редакции|в ред\.|Дополнен|Абзац|Пункт|Часть|Подпункт|Статья|Наименование|Утратил|Введен|введен|Изменен|п\. \d+[^()]{0,30}введен|часть [^()]{0,30}введена)[^()]{0,400}\)', ' ', raw)
    return re.sub(r' ([;.,:])', r'\1', re.sub(r'\s+', ' ', raw))
_txt = {}
def texts(fp):
    if fp not in _txt:
        pat, _, date = fp.partition('@')
        fs = [p for n, p in sorted(files.items()) if re.search(pat, n) and (not date or date in n)]
        ts = [clean(open(p, encoding='utf-8', errors='replace').read()) for p in fs]
        _txt[fp] = sorted([t for t in ts if len(t) > 500], key=len, reverse=True)
    return _txt[fp]
def nz(s): return s.lower().replace('ё', 'е')
def toks(s): return set(w[:5] for w in re.findall(r'[а-яё]{4,}', nz(s)))
def num_pat(n, glue='?'):
    """номер 12.1 в тексте бывает «12.1», «12 1», «121» (верхний индекс в PDF); у статей слитное написание не допускается"""
    p = n.split('.')
    if len(p) == 2 and glue: return re.escape(p[0]) + r'(?:(?:\.| )?' + re.escape(p[1]) + r'|\(' + re.escape(p[1]) + r'\))'      # «17.1», «17 1», «171», «17(1)»
    return re.escape(p[0]) + (r'(?:\.| )' + glue + re.escape(p[1]) if len(p) > 1 else '') + (r'(?:\.| )' + glue + re.escape(p[2]) if len(p) > 2 else '')
def nxt(n, sub=True):
    """номера, с которых начинается следующая единица; sub=False — «42.1» считается частью пункта 42 (акты без статей)"""
    p = n.split('.'); return [str(int(p[0]) + 1)] + (['.'.join(p[:-1] + [str(int(p[-1]) + 1)])] if len(p) > 1 else ([n + '.1'] if sub else []))
def article(t, a):
    ms = list(re.finditer(r'Статья\s+' + num_pat(a, '') + r'\s?\.\s+(?=[А-ЯЁ(])', t))
    if not ms: return None
    best = ''
    for m in ms:                                  # оглавление даёт короткий кусок; берётся самый длинный
        e = re.search(r' (?:Статья\s+\d+[\d. ]{0,6}\.\s+[А-ЯЁ(]|Глава \d+|ГЛАВА \d+|Раздел [IVX]+)', t[m.end():m.end() + 60000])
        s = t[m.end():m.end() + (e.start() if e else 60000)]
        if len(s) > len(best): best = s
    return best
def cands(t, n, kind, sub=True):
    """все места, где начинается единица с номером n: часть/пункт «n. Текст» или пункт «n) текст»"""
    if kind == 'dot': pat = r'(?:(?<=[^№N] )|^)' + num_pat(n) + r'\s?\. ?(?=[А-ЯЁ«("])'
    else: pat = r'(?:(?<=[.;:)»] )|(?<=[а-я] ))' + num_pat(n) + r'\) ?(?=[а-яёА-ЯЁ«(])'
    out = []
    for m in re.finditer(pat, t):
        end = len(t)
        for x in nxt(n, sub):
            p2 = (r'(?<=[^№N] )' + num_pat(x) + r'\s?\. ?(?=[А-ЯЁ«("])') if kind == 'dot' else (r'(?<=[.;:)»] )' + num_pat(x) + r'\) ?(?=[а-яёА-ЯЁ«(])')
            e = re.search(p2, t[m.end():m.end() + 30000])
            if e: end = min(end, m.end() + e.start())
        out.append(t[m.start():min(end, m.start() + 40000)])
    return out
def best(cs, lt):
    return max(cs, key=lambda c: (len(lt & toks(c)), -len(c))) if cs else None
def lst(x):
    out = []
    for y in re.split(r'\s*(?:,| и )\s*', x):
        y = y.strip().rstrip('.')
        if '–' in y:
            a, b = y.split('–')[:2]
            if a.isdigit() and b.isdigit() and int(b) - int(a) < 15: out += [str(k) for k in range(int(a), int(b) + 1)]
            else: out += [a, b]
        elif re.fullmatch(r'\d+(?:\.\d+)*', y): out.append(y)
    return out
def parse(r):
    g = lambda pat: (lambda m: lst(m.group(1)) if m else [])(re.search(pat, r))
    return {'pp': g(r'(?:[Пп]одп|пп)\. ?(«?[\dа-я.–, и»«]+?)(?= п\.| ч\.| ст\.|$|\s[А-ЯЁ]|,? п\.)') if re.search(r'(?:[Пп]одп|пп)\. ?\d', r) else [],
            'p': g(r'(?<![а-яё])[Пп]\. ?([\d.–, и]+)'), 'ch': g(r'(?<![а-яё])[Чч]\. ?([\d.–, и]+)')}
def norm_for(fp, art, r, lt):
    """[(метка, текст|None)] для ссылки r на акт с файлами fp; ссылка с несколькими статьями разбирается по кускам «… ст. N»"""
    ch = re.findall(r'(.*?[Сс]т\. ?(\d+(?:\.\d+)*(?:(?:, | и |–)\d+(?:\.\d+)*)*))', r)
    if not ch: return norm_one(fp, art, r, lt)
    out = []
    for chunk, arts in ch:
        pre = chunk[:chunk.lower().rfind('ст.')]
        for a in lst(arts)[:8]: out += norm_one(fp, a, pre, lt)
    return out
def norm_one(fp, art, r, lt):
    ts = texts(fp)
    if not ts: return [('нет текста акта', '')]
    d = parse(r); res = []
    for t in ts:
        res = []; base = t; lab = ''
        if art:
            base = article(t, art); lab = 'ст. ' + art
            if base is None: res = [(lab, None)]; continue
        units = [(lab, base)]
        if d['ch']:
            units = []
            for c in d['ch']:
                u = best(cands(base, c, 'dot'), lt)
                if u is None and not re.search(r'(?:^| )1\. ?[А-ЯЁ]', base[:4000]): units.append((lab + ' (части не нумерованы)', base))
                else: units.append((('ч. %s ' % c) + lab, u))
        if d['p']:
            new = []
            for ulab, u in units:
                if u is None: new.append((ulab, None)); continue
                for p in d['p']:
                    if art and not d['ch']: x = best(cands(u, p, 'par') + cands(u, p, 'dot'), lt)     # «п. 1 ст. 9.1»: пункт бывает и «1.», и «1)»
                    elif art: x = best(cands(u, p, 'par'), lt) or best(cands(u, p, 'dot'), lt)
                    else: x = best(cands(u, p, 'dot', False), lt) or best(cands(u, p, 'par'), lt)
                    new.append((('п. %s ' % p) + ulab, x))
            units = new
        if d['pp']:
            new = []
            for ulab, u in units:
                if u is None: new.append((ulab, None)); continue
                for p in d['pp']:
                    x = best(cands(u, p, 'par'), lt) or best(cands(u, p, 'dot'), lt)
                    new.append((('подп. %s ' % p) + ulab, x if x is not None else u))   # подпункт не найден — берётся пункт
            units = new
        res = units
        if all(u is not None for _, u in res): return res
    return res
def window(t, lt, W=45):
    ws = t.split()
    if len(ws) <= W: return t
    sc = [1 if nz(w).strip('.,;:()«»"')[:5] in lt else 0 for w in ws]; c = sum(sc[:W]); b = c; bi = 0
    for j in range(1, len(ws) - W + 1):
        c += sc[j + W - 1] - sc[j - 1]
        if c > b: b = c; bi = j
    return ('…' if bi else '') + ' '.join(ws[bi:bi + W])
def elsewhere(fp, lt, W=60):
    """лучшее окно по всему акту: (доля, текст)"""
    bb = (0, '')
    for t in texts(fp)[:1]:
        ws = t.split()
        if len(ws) <= W: continue
        sc = [1 if nz(w).strip('.,;:()«»"')[:5] in lt else 0 for w in ws]
        seen = {}; c = 0; best_c = -1; bi = 0
        # число разных слов отрезка в окне (а не вхождений)
        from collections import Counter
        cnt = Counter(); keys = [nz(w).strip('.,;:()«»"')[:5] for w in ws]
        for j, k in enumerate(keys):
            if k in lt: cnt[k] += 1
            if j >= W:
                k0 = keys[j - W]
                if k0 in lt:
                    cnt[k0] -= 1
                    if not cnt[k0]: del cnt[k0]
            if len(cnt) > best_c: best_c = len(cnt); bi = max(0, j - W + 1)
        v = 100 * best_c // max(1, len(lt))
        if v > bb[0]: bb = (v, ' '.join(ws[bi:bi + W]))
    return bb
def short(fp):
    return re.sub(r'\(\?!\[\\d-\]\)|\\', '', fp.split('|')[0]).replace('@', ' от ')
_ha = {}
def has_articles(fp):
    if fp in ('KOAP', 'SKIP'): return True
    if fp == 'NOTEXT': return False
    if fp not in _ha: _ha[fp] = any(all(re.search(r'Статья\s+%d\s?\.\s+[А-ЯЁ(]' % n, t) for n in (1, 2, 3)) for t in texts(fp)[:1])
    return _ha[fp]
HINT = [(r'КоАП', 'KOAP'), (r'УПК РФ', r'Уголовно-процессуальный кодекс РФ от'), (r'(?<![А-Яа-я])УК РФ', r'Уголовный кодекс РФ от'), (r'КАС РФ', r'КАС РФ от'),
        (r'Закон\w* о полиции', r'№ 3-ФЗ О полиции'), (r'Конституци', 'SKIP')]
UNIT = r'(?:[Сс]т|[Чч]|[Пп]|[Пп]одп|пп)\. ?\d'
def hint(txt):
    """акт, названный в тексте вне ссылки (ближайший к концу txt)"""
    pos = -1; fp = None
    for pat, hp in HINT:
        for h in re.finditer(pat, txt):
            if h.start() > pos: pos = h.start(); fp = hp
    for h in re.finditer(r'Закон\w* (№ ?\d+(?:-\d)?-ФК?З)', txt):
        if h.start() > pos: pos = h.start(); fp = act_pat(h.group(1))
    return fp
def known(fp): return bool(fp) and (fp in ('KOAP', 'SKIP') or bool(texts(fp)))
def resolve(lines):
    """{(i, k): ([(акт, статья), …] — кандидаты по порядку предпочтения, акт раздела назван в этом же разделе другим законом?)}"""
    first = [None, None]; named = {}
    for i, l in enumerate(lines):
        for k, m in enumerate(cut25.REF.finditer(l)):
            d = cut25.ref_ctx(m.group(1))[2]; fp = act_pat(d) if d else None
            if not known(fp) or fp == 'SKIP': continue
            named.setdefault(i, []).append((k, fp))
            if has_articles(fp): first[0] = first[0] or fp
            else: first[1] = first[1] or fp
    home = HOME[0] or first[0]; home_na = HOME[1] or first[1]
    anyact = art = None; stat = home; noart = home_na; sec_named = False; out = {}
    for i, l in enumerate(lines):
        if l.startswith('## '):
            sec_named = False; art = None; anyact = None
            ht = re.sub(r'//[^/]*//', ' ', l); hp = hint(ht)
            if hp and has_articles(hp): stat = hp
            a = re.findall(r'(?:[Сс]т\.|стать\w+)\s*(\d+(?:\.\d+)*)', ht); art = a[-1] if a else None
            hn = re.search(r'№ ?(\d+(?:[/.-]\d+)*)(?!-ФК?З)', ht)                  # «(Порядок № 264)»
            if hn:
                x = act_pat('№ ' + hn.group(1))
                if x and texts(x):
                    if not has_articles(x): anyact = noart = x
                else: anyact = 'NOTEXT'
        prev = 0
        for k, m in enumerate(cut25.REF.finditer(l)):
            r = m.group(1); _a, s_art, disp = cut25.ref_ctx(r)
            if disp and nkey(disp) in ('закона', 'закон', 'законе', 'законом', 'закону', 'кодекса', 'кодекс'): disp = None
            if disp and disp.startswith('«'): disp = None      # «ст. 6 «Законность»» — название статьи, а не акта
            fp = act_pat(disp) if disp else None
            isst = bool(re.search(r'(?:[Сс]т|(?<![а-яё])[Чч])\. ?\d', r))
            if not fp and not disp and isst: fp = hint(l[max(prev, m.start() - 220):m.start()])
            pv0 = prev; prev = m.end(); cnd = []
            if fp and known(fp):
                anyact = fp; art = s_art
                if has_articles(fp):
                    if fp != stat and fp != 'SKIP': sec_named = True
                    stat = fp
                else: noart = fp
                cnd = [(fp, art if has_articles(fp) else None)]
            elif disp or fp: anyact = 'NOTEXT'; art = None             # акт назван, но текста нет в базе: неполные ссылки после него не судятся
            elif re.search(r'[Сс]т\. ?\d', r):
                # «ст. 19.3» без названия акта: если в текущем законе такой статьи нет, это КоАП РФ
                if s_art and '.' in s_art and (stat in (None, 'KOAP', 'SKIP') or not any(article(t, s_art) for t in texts(stat)[:1])): stat = 'KOAP'
                elif stat == 'KOAP' and s_art and '.' not in s_art and home and home != 'KOAP': stat = home     # у статей КоАП номер всегда с точкой
                if anyact == 'NOTEXT' and '.' not in (s_art or ''): out[(i, k)] = ([], False); continue
                anyact = stat; art = s_art; cnd = [(stat, art)] + ([(home, art)] if home and home != stat else [])
            elif anyact == 'NOTEXT': cnd = []
            elif re.search(r'(?<![а-яё])[Чч]\. ?\d', r): cnd = [(stat, art)] + ([(home, art)] if home and home != stat else [])
            else:                                                      # только «п. N»
                num = re.search(r'№ ?(\d+)(?![\d-]*-ФЗ)', l[pv0:m.start()])       # «По приказу № 825 … (п. 9)»
                hp = act_pat('№ ' + num.group(1)) if num else None
                if hp and texts(hp) and not has_articles(hp): anyact = noart = hp
                if anyact and anyact != 'NOTEXT' and not has_articles(anyact): cnd.append((anyact, None))
                elif stat and art: cnd += [(stat, art)] + ([(home, art)] if home and home != stat else [])
                cnd += [(fp2, None) for k2, fp2 in named.get(i, []) if k2 > k and not has_articles(fp2)][:1]
                cnd += [(x, None) for x in (noart, home_na, first[1]) if x]
            seen = []; cnd = [c for c in cnd if c[0] and not (c in seen or seen.append(c))]
            out[(i, k)] = (cnd, sec_named and len(cnd) > 1 and isst)
    return out
n_seg = n_flag = n_noact = 0; stat_ = {'НЕТ': 0, 'АКТ?': 0, 'ИНОЕ': 0, 'низк': 0}
for f in sorted(glob.glob(os.path.join(A, 'q*.txt'))):
    q = int(os.path.basename(f)[1:4])
    if ONLY and q not in ONLY: continue
    raw = open(f, encoding='utf-8').read(); lines = raw.split('\n'); RAW[0] = raw
    DATES.clear(); ALIAS.clear(); HOME[:] = [None, None]
    for d, n in re.findall(r'от (\d\d\.\d\d\.\d{4}) № ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', raw): DATES.setdefault(n, d)
    for r, al in re.findall(r'//([^/]+)//[^/(]{0,40}\(далее — ([^)]+)\)', raw):
        d = cut25.ref_ctx(r)[2]; fp = act_pat(d) if d else None
        if not fp or fp == 'SKIP': continue
        if fp != 'KOAP' and '№' not in al: ALIAS.setdefault(nkey(al), fp)
        if known(fp): HOME[0 if has_articles(fp) else 1] = HOME[0 if has_articles(fp) else 1] or fp
    res = resolve(lines)
    for i, line in enumerate(lines):
        if not line.strip() or line.startswith('#') or line.startswith('!! '): continue
        refs = list(cut25.REF.finditer(line))
        if not refs: continue
        info = []
        for k, m in enumerate(refs):
            cnd, amb = res[(i, k)]; r = m.group(1)
            if not re.search(UNIT, r): cnd = [('SKIP', None)]            # название акта без нормы
            elif not cnd:
                n_noact += 1
                if '-v' in sys.argv: print('q%03d:%d акт не определён: %s | %s' % (q, i + 1, r, line[max(0, m.start() - 150):m.start()]))
            info.append((m, cnd, r, amb))
        if not any(c and c[0][0] not in ('KOAP', 'SKIP') for _, c, _, _ in info): continue
        cuts = [0] + [m.end() for m in re.finditer(r';\s|(?<=[а-яё»)/])\.\s+(?=[А-ЯЁ«*])', line) if not any(x[0].start() < m.start() < x[0].end() for x in info)] + [len(line)]
        for a, b in zip(cuts, cuts[1:]):
            seg = line[a:b]
            own = [x for x in info if a <= x[0].start() < b and re.search(UNIT, x[2])]
            if own and any((not x[1]) or x[1][0][0] == 'KOAP' for x in own): continue    # отрезок с КоАП или с неопределённым актом не судится
            use = [x for x in (own or info) if x[1] and x[1][0][0] not in ('KOAP', 'SKIP')]
            if not use: continue
            body = re.sub(r'//[^/]*//', '', seg); lt = toks(body)
            if len(re.findall(r'[а-яё]{4,}', nz(body))) < 5: continue
            got = []; amb = []; notext = False
            for m, cnd, r, am in use:
                bestc = None
                for ci, (fp, art) in enumerate(cnd):
                    if fp in ('KOAP', 'SKIP'): continue
                    nf = norm_for(fp, art, r, lt)
                    if any(lab == 'нет текста акта' for lab, _ in nf): continue
                    ok = all(t is not None for _, t in nf)
                    cv = len(lt & toks(' '.join(t or '' for _, t in nf)))
                    key = (ok, cv, -ci)
                    if bestc is None or key > bestc[0]: bestc = (key, ci, fp, nf)
                if bestc is None: notext = True; break
                _, ci, fp, nf = bestc
                if am and ci > 0 and m in [x[0] for x in own]: amb.append('%s → %s, а не %s' % (r, short(fp), short(cnd[0][0])))
                got += [(lab.strip() + ' · ' + short(fp), t, fp) for lab, t in nf]
            if notext: continue
            n_seg += 1
            none = [lab for lab, t, _ in got if t is None]
            allv = ' '.join(t or '' for _, t, _ in got); cov = 100 * len(lt & toks(allv)) // max(1, len(lt))
            tag = None; extra = ''; kind = None
            if none and own: tag = 'НЕТ ' + '; '.join(none); kind = 'НЕТ'
            elif amb: tag = 'АКТ? ' + '; '.join(amb) + ' (%d%%)' % cov; kind = 'АКТ?'
            elif cov < THR:
                ev, et = max((elsewhere(fp, lt) for fp in {g[2] for g in got}), key=lambda x: x[0])
                if ev >= cov + 30 and ev >= 60 and toks(et) - toks(allv): tag = 'ИНОЕ %d%%→%d%%' % (cov, ev); extra = et; kind = 'ИНОЕ'
                else: tag = '~%d%%' % cov; kind = 'низк'
            if not tag: continue
            n_flag += 1; stat_[kind] += 1
            print('q%03d:%d %s | %s' % (q, i + 1, tag, seg.strip()[:460]))
            for lab, t, _ in got[:3]:
                if t: print('      [%s] %s' % (lab.strip(), window(t, lt)[:330]))
            if extra: print('      [иное место] ' + extra[:420])
print('отрезков со ссылкой на акт (кроме КоАП): %d, помечено: %d (нет нормы %d, акт под вопросом %d, иное место %d, низкое совпадение %d); ссылок с неопределённым актом: %d'
      % (n_seg, n_flag, stat_['НЕТ'], stat_['АКТ?'], stat_['ИНОЕ'], stat_['низк'], n_noact))
