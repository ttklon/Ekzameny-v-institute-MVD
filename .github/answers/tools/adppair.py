#!/usr/bin/env python3
"""adppair.py SRC ФИЛЬТР [N1 N2] [--min=0] [--max=101] [--w=330] [--num] [--v1]
Вариант 2 АДП: каждое предложение со ссылкой на акт, название которого (или путь файла) подходит под ФИЛЬТР,
печатается рядом с текстом названной нормы: в файле акта берётся названная статья (для актов без статей — весь
текст) и в ней ищется окно из трёх предложений с наибольшим числом значимых слов предложения ответа.
Печатает долю совпадения и числа предложения, которых нет в названной статье. --num — только пары с такими числами.
"""
import sys, os, re, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = [a for a in sys.argv[1:] if not a.startswith('--')]; opts = [a for a in sys.argv[1:] if a.startswith('--')]
src, flt = args[0], re.compile(args[1])
n1, n2 = (int(args[2]), int(args[3])) if len(args) > 3 else (1, 149)
mn, mx, width = 0, 101, 330
for o in opts:
    if o.startswith('--min='): mn = int(o[6:])
    if o.startswith('--max='): mx = int(o[6:])
    if o.startswith('--w='): width = int(o[4:])
sys.argv = [sys.argv[0], src]
import srctok25 as K
import cut25, qcheck2
files = qcheck2.files
TXT = {}
def text_of(p):
    if p not in TXT:
        t = open(p, encoding='utf-8', errors='ignore').read(); t = re.sub(r'[-\u00ad]\s*\n\s*(?=[а-яё])', '', t); TXT[p] = re.sub(r'\s+', ' ', t)
    return TXT[p]
ART = {}
def article(p, art):
    key = (p, art)
    if key not in ART:
        t = text_of(p)
        ms = [m for m in re.finditer(r'Статья\s+' + re.escape(art).replace(r'\.', r'[.\s]\s?') + r'(?![\d.]\d)[\s.]', t)]
        best = ''
        for m in ms:
            e = re.search(r'Статья\s+\d', t[m.end():]); seg = t[m.start(): m.end() + (e.start() if e else 8000)]
            if len(seg) > len(best): best = seg
        ART[key] = best
    return ART[key]
PUN = {}
def punkt(p, num):
    key = (p, num)
    if key not in PUN:
        t = text_of(p); best = ''
        if num.replace('.', '').isdigit():
            pat = r'(?:(?<=[.;:)»\d>] )|(?<=\. \. ))' + re.escape(num) + r'\.? (?=[А-ЯЁ«(])'
            for m in re.finditer(pat, t):
                nxt = num.split('.'); nxt[-1] = str(int(nxt[-1]) + 1); nx = '.'.join(nxt)
                e = re.search(r'(?<=[.;:)»\d>] )' + re.escape(nx) + r'\.? (?=[А-ЯЁ«(])', t[m.end():m.end() + 9000])
                seg = t[m.start(): m.end() + (e.start() if e else 2500)]
                if e and len(seg) > len(best): best = seg
                elif not e and not best: best = seg
        PUN[key] = best
    return PUN[key]
SENT = {}
def sents(t):
    if id(t) not in SENT:
        ss = [x for x in re.split(r'(?<=[.;:!?])\s+', t) if len(x) > 15]; SENT[id(t)] = (ss, [set(K.tokens(x)) for x in ss])
    return SENT[id(t)]
def nums_of(s):
    s = cut25.REF.sub(' ', s); s = re.sub(r'\d{1,2}\.\d{2}\.\d{4}|№\s*[\d/.-]+[А-Яа-я-]*', ' ', s)
    return sorted(set(re.sub(r'\s', '', x) for x in re.findall(r'(?<![\d.])\d[\d ]*\d|\d', s)), key=lambda x: int(x))
tot = out = 0
A = cut25.A if '--v1' not in opts else None
for n in range(n1, n2 + 1):
    p = cut25.A + 'q%03d.txt' % n
    if not os.path.exists(p): continue
    lines = open(p, encoding='utf-8').read().split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces)
    for (i, _z), line in pieces:
        if line.startswith('#'): continue
        refs = list(cut25.REF.finditer(line)); pos = 0
        for s in K.sentences(line):
            a = line.find(s[:40], pos); a = pos if a < 0 else a; b = a + len(s); pos = b
            done = set()
            for k, m in enumerate(refs):
                if not (a <= m.start() < b): continue
                act, art = res.get(((i, 0), k), (None, None)); disp = names.get(((i, 0), k)) or ''
                if not disp: continue
                kind, pat = qcheck2.act_files(disp)
                if kind == 'SKIP': pat = r'Конституция РФ \(официальный'
                fl = [pth for rel, pth in files.items() if pat and re.search(pat, rel)] if kind != 'UNK' else []
                if not (flt.search(disp) or any(flt.search(os.path.basename(x)) for x in fl)): continue
                hasart = bool(re.search(r'[Сс]т(?:\.|ать)', m.group(1))) or bool(art)
                key = (disp, art if hasart else None)
                if key in done: continue
                done.add(key); tot += 1
                toks = [w for w in dict.fromkeys(K.tokens(K.strip(s))) if not w[0].isdigit()]
                if len(toks) < 3: continue
                best = (-1, '', '', '')
                if hasart and art and any(article(f, art) for f in fl): fl = [f for f in fl if article(f, art)]
                if not flt.search(disp) and not any(flt.search(os.path.basename(x)) for x in fl): continue
                pm = re.search(r'(?:подп\. [^ ]+ )?п(?:ункт[а-я]*|\.)\s?(\d+(?:\.\d+)*)', m.group(1)) if not (hasart and art) else None
                if pm and any(punkt(f, pm.group(1)) for f in fl): fl = [f for f in fl if punkt(f, pm.group(1))]
                for f in fl:
                    body = article(f, art) if (hasart and art) else (punkt(f, pm.group(1)) if pm else '')
                    scope = body or text_of(f)
                    ss, st = sents(scope)
                    df = {}
                    for x in st:
                        for w in x: df[w] = df.get(w, 0) + 1
                    wt = {w: math.log(1 + len(ss) / (1 + df.get(w, 0))) + 0.3 for w in toks}; T = sum(wt.values())
                    for j in range(len(ss)):
                        have = st[j] | (st[j + 1] if j + 1 < len(ss) else set()) | (st[j + 2] if j + 2 < len(ss) else set())
                        sc = sum(wt[w] for w in toks if w in have) / T
                        if sc > best[0]: best = (sc, ' '.join(ss[j:j + 3]), scope, (('ст. ' + art if hasart and art else 'п. ' + pm.group(1)) if body else ('ПУНКТ НЕ НАЙДЕН, весь акт' if pm else 'ВЕСЬ АКТ' if not (hasart and art) else 'СТАТЬЯ НЕ НАЙДЕНА, весь акт')))
                if best[0] < 0:
                    print('q%03d:%d [НЕТ ФАЙЛА: %s] %s' % (n, i + 1, disp, K.strip(s)[:width])); out += 1; continue
                cv = round(100 * best[0])
                flat = re.sub(r'\s', '', best[2]); miss = [x for x in nums_of(s) if x not in flat and x not in ('1','2','3')] if '--words' not in opts else []
                if '--num' in opts and not miss: continue
                if not (mn <= cv < mx) and not ('--num' in opts): continue
                out += 1
                print('q%03d:%d [%d%% %s%s] %s' % (n, i + 1, cv, best[3], (' ЧИСЛА НЕТ: ' + ','.join(miss)) if miss else '', re.sub(r'\*\*', '', s)[:width]))
                print('    ▸ ' + best[1][:width + 60])
print('ссылок: %d, напечатано: %d' % (tot, out))
