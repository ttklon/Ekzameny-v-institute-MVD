#!/usr/bin/env python3
"""recentn.py ПАПКА_ТЕКСТОВ ФАЙЛ_REFCHECK [ФАЙЛ_REFCHECK…] -n НОМЕР [-y 2025,2026] [-w 320] [-c]

Изменения актов без статей (указы Президента, постановления Правительства, приказы) и ответы, которые на них ссылаются.
recent.py и recentp.py работают только с актами, разбитыми на статьи; этот скрипт — для остальных.

В тексте акта (папка от kextract.py) ищутся отметки «(В редакции … от ДД.ММ.ГГГГ № …)», «(Дополнен …)», «(Утратил силу …)»
с датой нужного года. Отметка стоит после изменённого места, поэтому изменённым считается текст от предыдущей отметки
(или начала пункта) до неё. Для каждого такого места определяется пункт («12.», «5(1).») и подпункт («52)», «е)»).
Перечни изменяющих актов под заголовком (шесть дат и больше) пропускаются.
ФАЙЛ_REFCHECK — вывод «refcheck.py … -a»: из него берутся предложения ответов со ссылкой на пункт этого акта
(акт распознаётся по шестизначному коду файла в строке привязки). Печатается: изменённые места по пунктам; под каждым — предложения
ответов, ссылающиеся на этот пункт. В конце — ссылки на акт без пункта (только счёт) и пункты, которых отметки не касаются.
  -n НОМЕР   номер акта, как в имени файла («699», «1090»);   -f ЧАСТЬ_ИМЕНИ   если номер у двух актов общий («от 22.12.2015»);   -y   годы через запятую;   -w   длина печатаемого места;
  -c         только счёт.
Пометок скрипт не ставит: каждое напечатанное предложение читается рядом с изменённым местом.
"""
import re, sys, os, glob, collections
def opt(k, d=None, flag=False):
    if k in sys.argv:
        i = sys.argv.index(k)
        if flag: sys.argv.pop(i); return True
        v = sys.argv[i + 1]; del sys.argv[i:i + 2]; return v
    return False if flag else d
NUM = opt('-n'); FSUB = opt('-f'); YEARS = opt('-y', '2025,2026').split(','); W = int(opt('-w', 320)); CNT = opt('-c', flag=True)
SRC = sys.argv[1]; RC = sys.argv[2:]
paths = [p for p in sorted(glob.glob(os.path.join(SRC, '*.txt'))) if re.search(r'№ ?%s(?![\w-])' % re.escape(NUM), os.path.basename(p))]
if FSUB: paths = [p for p in paths if FSUB in os.path.basename(p)]
if not paths: sys.exit('нет акта № ' + NUM)
MARK = re.compile(r'\((?:[А-ЯЁа-яё][^()]{0,80})?(?:в редакции|в ред\.|дополнен\w*|утратил\w*|введен\w*)[^()]*\)', re.I)
DATE = re.compile(r'от (\d{2})\.(\d{2})\.(\d{4})')
PT = re.compile(r'(?<= )(\d+(?:\(\d+\))?(?: ?\d)?)\. (?=[А-ЯЁ«(])'); SP = re.compile(r'(?<= )(\d+(?: ?\d)?|[а-яё](?: ?\d)?)\) ')
best = None
for p in paths:
    t = re.sub(r'\s+', ' ', open(p, encoding='utf-8').read()); ch = []; prev = 0
    for m in MARK.finditer(t):
        ds = DATE.findall(m.group())
        if len(ds) < 6 and any(d[2] in YEARS for d in ds):
            a = max(prev, m.start() - 900); frag = t[a:m.start()]
            pts = [x for x in PT.finditer(t[:m.start()][-6000:])]; sps = [x for x in SP.finditer(frag)]
            pn = pts[-1].group(1).replace(' ', '.') if pts else '?'
            if pts and (len(t[:m.start()][-6000:]) - pts[-1].start()) < len(frag): frag = t[:m.start()][-6000:][pts[-1].start():]
            sn = sps[-1].group(1).replace(' ', '.') if sps else ''
            ch.append((pn, sn, frag.strip(), ' '.join('%s.%s.%s' % d for d in ds if d[2] in YEARS)))
        prev = m.end()
    if best is None or len(ch) > len(best[1]): best = (p, ch)
p, ch = best
CODES = re.compile(r'← (?:%s) ' % '|'.join(os.path.basename(x)[:6] for x in paths))
print('== ' + os.path.basename(p)[:110] + ' — изменённых мест: %d' % len(ch))
blocks = []
for f in RC:
    cur = None
    for line in open(f, encoding='utf-8'):
        m = re.match(r'(\S+:\d+)  .*?\[(.*)\]\s*$', line)
        if m: cur = [m.group(1), m.group(2), '']; blocks.append(cur)
        elif cur is not None and line.startswith('   ') and not line.startswith('      →') and not cur[2]: cur[2] = line.strip()
mine = collections.defaultdict(list); nopt = 0; cited = collections.Counter()
for loc, refs, sent in blocks:
    for r in refs.split('; '):
        if not CODES.search(r): continue
        mm = re.search(r'(?:^| )п ([\d.,()]+)', r)
        if not mm: nopt += 1; continue
        for q in mm.group(1).split(','): mine[q.replace('(', '.').replace(')', '')].append((loc, sent)); cited[q] += 1
bypt = collections.defaultdict(list)
for pn, sn, frag, d in ch: bypt[pn.replace('(', '.').replace(')', '')].append((sn, frag, d))
hit = 0
for pn in sorted(bypt, key=lambda x: [int(y) if y.isdigit() else 0 for y in re.split(r'\D+', x)]):
    ss = mine.get(pn, [])
    if not ss and not CNT and '-all' not in sys.argv: continue
    hit += len(ss)
    if CNT: continue
    print('\n-- п. %s: изменённых мест %d' % (pn, len(bypt[pn])))
    for sn, frag, d in bypt[pn]: print('   [%s%s] …%s' % (d, (' подп. ' + sn) if sn else '', frag[-W:]))
    seen = set()
    for loc, sent in ss:
        k = re.sub(r'\W+', '', sent)[:120]
        if k in seen: print('   > ' + loc + ' (то же)'); continue
        seen.add(k); print('   > %s  %s' % (loc, sent[:520]))
print('\n-- пунктов с изменениями: %d; из них названы в ответах: %d; предложений к прочтению: %d; ссылок на акт без пункта: %d; названы пункты без изменений: %s'
      % (len(bypt), sum(1 for k in bypt if k in mine), hit, nopt, ', '.join(sorted(k for k in mine if k not in bypt))[:300]))
