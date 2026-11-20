#!/usr/bin/env python3
"""read26.py SRC ПАПКА N [-l A-B] [-w СЛОВ] [-k ФАЙЛ] — ответ по АДП № N целиком, строка за строкой, с текстом каждой названной нормы под строкой.
Нужен для сплошной сверки глазами: ничего не отбирает и не оценивает, печатает все непустые строки. Акт ссылки определяется так же,
как в actline26.py (для КоАП РФ — как в koapline26.py). Под строкой — кусок названной нормы (СЛОВ, по умолчанию 45), в котором больше
всего слов строки; короткая норма печатается целиком. «[нет нормы]» — такой части или пункта в акте не нашлось, «[акт?]» — акт
определить не удалось или его текста нет в базе. Норма, уже напечатанная в этом же прогоне тем же куском, заменяется словом «выше».
Ключ -k ФАЙЛ запоминает напечатанные нормы между прогонами (вариант 2, затем вариант 1 того же вопроса).
Ключ -s ПАПКА2: строка, которая без разметки, кавычек и знаков препинания дословно совпадает со строкой того же вопроса в ПАПКА2,
печатается одной пометкой «= ПАПКА2:строка» (текст уже прочитан там). Нормы Конституции РФ берутся из распознанного текста в src-text.
ПАПКА — adp2 или каталог варианта 1, разрезанного по вопросам (tools/v1split.py). Ключ -l A-B — только строки с A по B.
    python3 tools/read26.py /tmp/src adp2 31 -l 1-40
"""
import sys, os, re, io, contextlib, importlib.util, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
argv = sys.argv[1:]; W = 45; LR = None; KEEP = None
if '-w' in argv: i = argv.index('-w'); W = int(argv[i + 1]); del argv[i:i + 2]
if '-l' in argv: i = argv.index('-l'); a, b = argv[i + 1].split('-'); LR = (int(a), int(b)); del argv[i:i + 2]
if '-k' in argv: i = argv.index('-k'); KEEP = argv[i + 1]; del argv[i:i + 2]
SAME = None
if '-s' in argv: i = argv.index('-s'); SAME = argv[i + 1]; del argv[i:i + 2]
SRC, A, N = argv[0], argv[1], int(argv[2])
def load(name, args):
    sys.argv = [name] + args
    spec = importlib.util.spec_from_file_location(name[:-3], os.path.join(HERE, name)); m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(m)
    return m
al = load('actline26.py', [SRC, tempfile.mkdtemp()])
sp = load('sanpart26.py', [SRC])
cut25 = al.cut25
KREF = re.compile(r'(?:[Чч]\. ?([\d\.]+(?:(?:[–,]| и ) ?[\d\.]+)*),? )?[Сс]т\. (\d+\.\d+(?:\.\d+)?)|(?<![\w.])[Чч]\. ?([\d\.]+(?:(?:[–,]| и ) ?[\d\.]+)*)(?! ст\.)')
def plist(x):
    out = []
    for y in re.split(r'[, и]+', x or ''):
        y = y.rstrip('.')
        if '–' in y:
            a, b = y.split('–')[:2]
            try:
                fa, fb = float(a), float(b)
                if '.' not in a and '.' not in b and fb - fa < 12: out += [str(k) for k in range(int(fa), int(fb) + 1)]
                else: out += [a, b]
            except ValueError: out.append(a)
        elif y: out.append(y)
    return out
def koap(r, last):
    """[(метка, текст | None)], последняя статья"""
    got = []
    for m in KREF.finditer(r):
        if m.group(2): a = m.group(2); ps = plist(m.group(1)); last = a
        else:
            a = last; ps = plist(m.group(3))
            if not a: continue
        d = sp.P(a)
        if not d: got.append(('ст. %s КоАП' % a, None)); continue
        if ps:
            for p in ps: got.append(('ч. %s ст. %s КоАП' % (p, a), d.get(p)))
        else: got.append(('ст. %s КоАП' % a, ' '.join(v for k, v in d.items() if not (k == '1' and ('загл' in d or '—' in d)))))
    return got, last
f = os.path.join(A, 'q%03d.txt' % N); raw = open(f, encoding='utf-8').read(); lines = raw.split('\n'); al.RAW[0] = raw
al.DATES.clear(); al.ALIAS.clear(); al.HOME[:] = [None, None]
for d, n in re.findall(r'от (\d\d\.\d\d\.\d{4}) № ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', raw): al.DATES.setdefault(n, d)
for r, name in re.findall(r'//([^/]+)//[^/(]{0,40}\(далее — ([^)]+)\)', raw):
    d = cut25.ref_ctx(r)[2]; fp = al.act_pat(d) if d else None
    if not fp or fp == 'SKIP': continue
    if fp != 'KOAP' and '№' not in name: al.ALIAS.setdefault(al.nkey(name), fp)
    if al.known(fp): al.HOME[0 if al.has_articles(fp) else 1] = al.HOME[0 if al.has_articles(fp) else 1] or fp
res = al.resolve(lines); seen = {}; klast = None; npar = 0
def flat(x): return re.sub(r'[^0-9a-zа-я]+', ' ', re.sub(r'^!! ', '', x).lower().replace('ё', 'е')).strip()
same = {}
if SAME and os.path.exists(os.path.join(SAME, 'q%03d.txt' % N)):
    for j, l2 in enumerate(open(os.path.join(SAME, 'q%03d.txt' % N), encoding='utf-8').read().split('\n')):
        if l2.strip(): same.setdefault(flat(l2), j + 1)
# Конституция РФ: в базе официальный текст — скан без текстового слоя, поэтому берётся распознанный текст из src-text
CONST = {}
_cf = os.path.join(HERE, '..', 'src-text', 'Конституция РФ (распознанный текст скана).txt')
if os.path.exists(_cf):
    ct = re.sub(r'\s+', ' ', open(_cf, encoding='utf-8').read())
    ms = list(re.finditer(r'Статья (\d+)\*? ', ct))
    for a, m in enumerate(ms):
        body = ct[m.end():ms[a + 1].start() if a + 1 < len(ms) else m.end() + 6000]
        if len(body) > len(CONST.get(m.group(1), '')): CONST[m.group(1)] = body
OTHER = re.compile(r'[Зз]акон|КоАП|[Кк]одекс|№|Указ|Положени|приказ|Концепци|Стратеги|Устав|Наставлен|Правил|Порядк|Инструкци|УК|УПК|КАС|ГК|Пленум|того же')
def const(r):
    out = []
    for m in re.finditer(r'((?:п\. ?«[а-я](?:\.\d)?»(?:(?:, | и |–)«[а-я](?:\.\d)?»)* )?(?:ч\. ?[\d\.]+(?:(?:, | и |–)[\d\.]+)* )?)ст\. ?(\d+(?:(?:, | и |–)\d+)*)', r):
        pre, arts = m.group(1), re.split(r', | и |–', m.group(2))
        for a in arts:
            body = CONST.get(a)
            if body is None: out.append(('ст. %s Конституции' % a, None)); continue
            parts = re.findall(r'ч\. ?([\d\.]+(?:(?:, | и |–)[\d\.]+)*)', pre); lets = re.findall(r'«([а-я](?:\.\d)?)»', pre); t = body; lab = 'ст. %s' % a
            if parts and len(arts) == 1:
                ps = re.split(r', | и |–', parts[0]); seg = []
                for pn in ps:
                    pn = pn.rstrip('.'); mm = re.search(r'(?:^| )%s\. (?=[А-Я])' % re.escape(pn), body)
                    if mm:
                        nx = re.search(r' %d\. (?=[А-Я])' % (int(float(pn)) + 1), body[mm.end():]); seg.append(body[mm.start():mm.end() + (nx.start() if nx else 3000)].strip())
                if seg: t = ' '.join(seg); lab = 'ч. %s ст. %s' % (parts[0], a)
            if lets and len(arts) == 1: lab = 'п. «%s» %s' % ('», «'.join(lets), lab)                 # буквы в распознанном тексте ненадёжны: окно по словам
            out.append((lab + ' Конституции', t))
    return out
sticky = False
if KEEP and os.path.exists(KEEP):
    import json
    seen = {tuple(k.split('\t')): v for k, v in json.load(open(KEEP, encoding='utf-8')).items()}
for i, line in enumerate(lines):
    if not line.strip(): continue
    if line.startswith('#'):
        m = re.search(r'[Сс]т(?:атья|\.) (\d+\.\d+(?:\.\d+)?)', line); klast = m.group(1) if m else klast
        sticky = 'онституц' in line
    npar += 1
    if LR and not (LR[0] <= i + 1 <= LR[1]): continue
    if same and not line.startswith('#') and flat(line) in same:
        print('%d| = %s:%d  %s…' % (i + 1, os.path.basename(os.path.normpath(SAME)), same[flat(line)], ' '.join(line.split()[:7]))); continue
    print('%d| %s' % (i + 1, line))
    lt = al.toks(re.sub(r'//[^/]*//', '', line)); out = []; isc = sticky; prev = 0
    for k, m in enumerate(cut25.REF.finditer(line)):
        r = m.group(1); cnd, _ = res.get((i, k), ([], False))
        if 'Конституци' in r: isc = True
        elif OTHER.search(r): isc = False
        elif 'Конституци' in line[prev:m.start()]: isc = True
        elif OTHER.search(re.sub(r'//[^/]*//', '', line[prev:m.start()])) and not sticky: isc = False
        prev = m.end()
        if isc and 'Конституци' not in r and re.search(r'п\. ?\d', r): isc = False                  # в Конституции пункты только буквенные
        if isc and CONST and re.search(r'ст\. ?\d+(?!\.\d)', r):
            out += const(r); continue
        if not re.search(al.UNIT, r) and not re.search(r'\d+\.\d+', r): continue                    # название акта без нормы
        if cnd and cnd[0][0] == 'KOAP' or (not cnd and re.search(r'ст\. \d+\.\d+', r)):
            got, klast = koap(r, klast); out += got; continue
        if not cnd: out.append((r + ' [акт?]', '')); continue
        bestc = None
        for ci, (fp, art) in enumerate(cnd):
            if fp in ('KOAP', 'SKIP'): continue
            nf = al.norm_for(fp, art, r, lt)
            if any(lab == 'нет текста акта' for lab, _ in nf): continue
            key = (all(t is not None for _, t in nf), len(lt & al.toks(' '.join(t or '' for _, t in nf))), -ci)
            if bestc is None or key > bestc[0]: bestc = (key, fp, nf)
        if bestc is None: out.append((r + ' [акт?]', '')); continue
        out += [(lab.strip() + ' · ' + al.short(bestc[1]), t) for lab, t in bestc[2]]
    if line.startswith('!! '): out = []                                                          # итоговый блок повторяет ответ
    for lab, t in out:
        if t is None: print('      [%s] [нет нормы]' % lab); continue
        if t == '': print('      [%s]' % lab); continue
        w = al.window(t, lt, 25 if (len(out) >= 3 and lab.startswith('ст.')) else W); key = (lab, w[:80])
        if key in seen: print('      [%s] выше, %s' % (lab, seen[key])); continue
        seen[key] = '%s:%d' % (os.path.basename(os.path.normpath(A)), i + 1); print('      [%s] %s' % (lab, w))
if KEEP:
    import json
    json.dump({'\t'.join(k): v for k, v in seen.items()}, open(KEEP, 'w', encoding='utf-8'), ensure_ascii=False)
print('== вопрос %d: непустых строк %d' % (N, npar))
