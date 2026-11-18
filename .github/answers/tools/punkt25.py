#!/usr/bin/env python3
"""punkt25.py SRC IDX_ACTS [N…] — ссылки на пункты подзаконных актов («п. 63 Правил», «п. 9.2 Инструкции») и статьи законов
без деления в указателе: слова предложения ищутся в тексте названного пункта (статьи) названного акта.
Если в названном пункте слов мало, печатается пункт того же акта, где слова предложения собраны лучше всего.
Акт неполной ссылки берётся из контекста раздела; если в нём не сошлось — пробуются остальные акты ответа."""
import sys, os, re, math, pickle
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K
src, ia = sys.argv[1:3]; only = [int(x) for x in sys.argv[3:]]
sys.argv = [sys.argv[0], src]
import cut25, qcheck2
meta = pickle.load(open(os.path.join(ia, 'meta.pkl'), 'rb')); vocab = meta['vocab']; poff = np.load(os.path.join(ia, 'poff.npy')); NC = len(np.load(os.path.join(ia, 'cstart.npy'), mmap_mode='r'))
def w8(w):
    i = vocab.get(w); return math.log(NC / (1 + (int(poff[i + 1] - poff[i]) if i is not None else 0))) + 0.2
FC = {}
def texts(disp, dates={}):
    """тексты акта по названию из ссылки; dates — {номер акта: дата} из полных названий в ответе (чтобы «Пленум № 21» не спутать с другим № 21)"""
    m = re.search(r'№ ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', disp); dm = re.search(r'\d\d\.\d\d\.\d{4}', disp)
    date = dm.group() if dm else (dates.get(m.group(1)) if m else None); key = (disp, date)
    if key not in FC:
        kind, pat = qcheck2.act_files(disp)
        if kind == 'SKIP' or kind == 'UNK' or not pat: FC[key] = []
        else:
            fs = [(rel, p) for rel, p in sorted(qcheck2.files.items()) if re.search(pat, rel)]
            if date and any(date in rel for rel, p in fs): fs = [(rel, p) for rel, p in fs if date in rel]
            out = []
            for rel, p in fs:
                t = open(p, encoding='utf-8', errors='replace').read(); t = re.sub(r'<\d+>', ' ', t); t = K.CLEAN.sub(' ', t); out.append((os.path.basename(p)[:40], re.sub(r'\s+', ' ', t)))
            FC[key] = out
    return FC[key]
PC = {}
def punkts(key, t):
    """[(номер, текст)] — пункты «N. Текст» и подпункты «N.M. Текст» по порядку; пункт включает свои подпункты"""
    if key in PC: return PC[key]
    raw = [m for m in re.finditer(r'(?:(?<=\s)|^)(\d{1,3}(?:\.\d{1,2}){0,2})\. ?(?=[А-ЯЁ«(])', t)]
    ms = []; cur = None                      # принимаются только номера по порядку: N+1 после N, подпункты N.M внутри N, новый счёт с 1
    for m in raw:
        num = m.group(1); top = int(num.split('.')[0])
        if '.' in num:
            if cur is not None and top == cur: ms.append(m)
        elif top == 1 or (cur is not None and top == cur + 1): ms.append(m); cur = top
    out = []
    for i, m in enumerate(ms):
        num = m.group(1); j = i + 1
        while j < len(ms) and ms[j].group(1).startswith(num + '.'): j += 1
        end = ms[j].start() if j < len(ms) else len(t)
        out.append((num, t[m.start():min(end, m.start() + 6000)]))
    PC[key] = out; return out
def cov(words, wt, txt):
    have = set(K.tokens(txt)); tot = sum(wt[w] for w in words) or 1
    return sum(wt[w] for w in words if w in have) / tot
tot = bad = 0
for n in (only or range(1, 150)):
    lines = open(cut25.A + 'q%03d.txt' % n, encoding='utf-8').read().split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces); allacts = list(dict.fromkeys(d for d in names.values() if d))
    dates = {}
    for dm_ in re.finditer(r'от (\d\d\.\d\d\.\d{4})(?: г\.)? № ?(\d+(?:[/.-]\d+)*(?:-[А-ЯA-Z]+|н)?)', '\n'.join(lines)): dates.setdefault(dm_.group(2), dm_.group(1))
    for (i, _z), line in pieces:
        if line.startswith('#') or line.startswith('!!'): continue
        refs = list(cut25.REF.finditer(line)); pos = 0
        for s in K.sentences(line):
            a = line.find(s[:40], pos); a = pos if a < 0 else a; b = a + len(s); pos = b
            inr = [(k, m) for k, m in enumerate(refs) if a <= m.start() < b]
            if not inr: continue
            # текст, относящийся к ссылке: от предыдущей ссылки (или начала предложения) до этой ссылки
            for z, (k, m) in enumerate(inr):
                r = m.group(1)
                if re.search(r'[Сс]т\.|[Чч]\.\s*\d|гл\.|глав|раздел', r): continue
                pm = re.search(r'(?:^|[\s(])(?:п|пп)\.\s*(\d+(?:\.\d+)*)((?:\s*(?:,|и|–|—|-)\s*\d+(?:\.\d+)*)*)', r)
                if not pm or re.search(r'подп\.', r): continue
                nums = [pm.group(1)] + re.findall(r'\d+(?:\.\d+)*', pm.group(2)); rng = re.search(r'[–—-]', pm.group(2))
                if rng and len(nums) == 2 and '.' not in nums[0] + nums[1] and int(nums[1]) - int(nums[0]) < 40: nums = [str(x) for x in range(int(nums[0]), int(nums[1]) + 1)]
                st = inr[z - 1][1].end() if z else a
                seg = line[st:m.start()] if len(K.tokens(K.strip(line[st:m.start()]))) >= 3 else s
                words = sorted({w for w in K.tokens(K.strip(seg)) if not w[0].isdigit()})
                if len(words) < 3: continue
                wt = {w: w8(w) for w in words}
                own = cut25.ref_ctx(r); disp = names.get(((i, 0), k))
                if not disp or re.search(r'[Зз]акон|[Кк]одекс|КоАП|Конституц|УК РФ|УПК|КАС', disp): continue
                cands = [disp] + ([d for d in allacts if d != disp and not re.search(r'[Зз]акон|[Кк]одекс|КоАП|Конституц|УК РФ|УПК|КАС', d)] if not own[0] else [])
                best = (-1, '', ''); alt = (-1, '', '', '')
                for ci, d in enumerate(cands):
                    if not d: continue
                    for fn, t in texts(d, dates):
                        P = punkts(fn, t)
                        if not P: continue
                        c = max([cov(words, wt, x) for num, x in P if num in nums] or [-1])
                        if c > best[0]: best = (c, d, fn)
                        if ci == 0:
                            for num, x in P:
                                if len(x) > 4000: continue
                                c2 = cov(words, wt, x)
                                if c2 > alt[0]: alt = (c2, num, fn, x)
                    if best[0] >= 0.6: break
                if best[0] < 0: continue
                tot += 1
                if best[0] < 0.5:
                    bad += 1
                    print('q%03d:%d п. %s %s: в пункте %.2f | %s' % (n, i + 1, ','.join(nums[:4]), (disp or '?')[:38], best[0], seg.strip()[:230]))
                    if alt[0] > best[0] + 0.2: print('      лучше: п. %s (%.2f): %s' % (alt[1], alt[0], alt[3][:200]))
print('ссылок на пункты сверено:', tot, 'слов предложения в названном пункте меньше половины:', bad)
