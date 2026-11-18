#!/usr/bin/env python3
"""srcsent25.py SRC IDX_ACTS IDX_LIT [N…] — сверка каждого предложения варианта 2 с источниками (нужен numpy).
SRC — папка extract_src.py; IDX_* — указатели srcidx25.py (акты с судебной практикой; литература).
Для каждого предложения:
  • если в нём есть ссылка (//ч. N ст. M акта//) — слова и числа сверяются с названной статьёй названного акта
    (для актов без статей — с ближайшим по словам местом этого акта);
  • в любом случае ищется место в актах и место в литературе, где собрано больше всего слов предложения.
Печатает таблицу: ответ:строка:предложение, вид, доля слов в названной статье, доля в лучшем месте актов, в литературе,
числа, которых нет в названной статье, числа, которых нет ни в одном найденном месте, имя файла, текст.
Доля считается по основам слов с весом (редкое слово весит больше). Это отбор мест для чтения, а не вывод об ошибке."""
import sys, os, re, glob, pickle, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import srctok25 as K
src, ia, il = sys.argv[1:4]; only = [int(x) for x in sys.argv[4:]]
sys.argv = [sys.argv[0], src]
import cut25, qcheck2
class Idx:
    def __init__(s, d):
        m = pickle.load(open(os.path.join(d, 'meta.pkl'), 'rb')); s.vocab = m['vocab']; s.names = m['names']; s.arts = m['arts']; s.W = m['W']
        ld = lambda n: np.load(os.path.join(d, n + '.npy'), mmap_mode='r')
        s.T = ld('T'); s.pch = ld('pch'); s.poff = ld('poff'); s.cstart = ld('cstart'); s.cfile = np.array(ld('cfile')); s.cart = np.array(ld('cart'))
        s.C = len(s.cstart); s.N = len(s.T); s.cache = {}
        s.f0 = np.searchsorted(s.cfile, np.arange(len(s.names) + 1))
    def df(s, w):
        i = s.vocab.get(w); return 0 if i is None else int(s.poff[i + 1] - s.poff[i])
    def chunkset(s, c):
        if c not in s.cache:
            if len(s.cache) > 4000: s.cache.clear()
            a = int(s.cstart[c]); b = int(s.cstart[c + 1]) if c + 1 < s.C else s.N
            s.cache[c] = set(np.unique(s.T[a:b]).tolist())
        return s.cache[c]
    def score(s, toks, wt, mask=None):
        """вес слов предложения по отрезкам (отрезок + следующий)"""
        sc = np.zeros(s.C + 1, dtype=np.float32)
        for w in toks:
            i = s.vocab.get(w)
            if i is None: continue
            p = s.pch[s.poff[i]:s.poff[i + 1]]; sc[p] += wt[w]
        two = sc[:-1] + sc[1:]                       # приблизительно: слово в обоих отрезках считается дважды
        if mask is not None: two = np.where(mask, two, -1)
        return two
    def cover(s, toks, wt, chunks):
        have = set()
        for c in chunks:
            if 0 <= c < s.C: have |= s.chunkset(c)
        ids = {w: s.vocab.get(w) for w in toks}
        tot = sum(wt[w] for w in toks) or 1
        return sum(wt[w] for w in toks if ids[w] in have) / tot, {w for w in toks if ids[w] in have}
A_, L_ = Idx(ia), Idx(il)
NC = A_.C + L_.C
files = qcheck2.files
def idx_files(pat):
    nm = {os.path.basename(p) for rel, p in files.items() if re.search(pat, rel)}
    return [i for i, n in enumerate(A_.names) if n in nm]
AFC = {}
def act_idx(disp):
    if disp not in AFC:
        kind, pat = qcheck2.act_files(disp)
        if kind == 'SKIP': pat = r'Конституци'
        AFC[disp] = idx_files(pat) if kind != 'UNK' and pat else []
    return AFC[disp]
ARTID = {a: i for i, a in enumerate(A_.arts)}
SPLIT = re.compile(r'(?<=[.!?…»)])\s+(?=[А-ЯЁ«*])')
def sentences(line):
    out = []; cur = ''
    for p in SPLIT.split(line):
        cur = (cur + ' ' + p) if cur else p
        if cur.count('«') <= cur.count('»') and cur.count('//') % 2 == 0 and cur.count('(') <= cur.count(')') and not re.search(r'(?:^|\s)(?:ст|ч|п|пп|подп|гл|абз|т|см|им|г|гг|др|руб|тыс|млн|д|е|н|примеч)\.$', cur):
            out.append(cur); cur = ''
    if cur: out.append(cur)
    return out
REFNUM = re.compile(r'(?:стать[а-я]*|ст\.|част[а-я]*|ч\.|пункт[а-я]*|п\.|пп\.|подп\.|подпункт[а-я]*|глав[а-я]*|гл\.|раздел[а-я]*|абз\.|абзац[а-я]*|примечани[а-я]*|приложени[а-я]*|№)\s*\d+(?:\.\d+)*(?:\s*(?:,|и|–|—|-)\s*\d+(?:\.\d+)*)*', re.I)
def strip(s):
    s = re.sub(r'//.+?//', ' ', s); s = REFNUM.sub(' ', s); s = re.sub(r'\d{1,2}\.\d{2}\.\d{4}', ' ', s)
    s = re.sub(r'^\s*(?:[-–>]\s*)?(?:\*\*)?\d+[.)]\s', ' ', s); s = re.sub(r'\b(?:19|20)\d\d\s*(?:г\.|год[а-я]*)', ' ', s)
    return s.replace('**', ' ')
def run(n):
    lines = open(cut25.A + 'q%03d.txt' % n, encoding='utf-8').read().split('\n')
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces); rows = []
    allacts = list(dict.fromkeys(d for d in names.values() if d))
    for (i, _z), line in pieces:
        if line.startswith('#'): continue
        block = line.startswith('!!')
        refs = list(cut25.REF.finditer(line)); pos = 0
        for si, s in enumerate(sentences(line)):
            a = line.find(s[:40], pos); a = pos if a < 0 else a; b = a + len(s); pos = b
            toks = K.tokens(strip(s)); words = sorted({w for w in toks if not w[0].isdigit()}); nums = sorted({w for w in toks if w[0].isdigit()}, key=int)
            if len(words) < 3 and not nums: continue
            wt = {w: math.log(NC / (1 + A_.df(w) + L_.df(w))) + 0.2 for w in set(toks)}
            for w in nums: wt[w] = 0.0
            # названная статья
            rc = ''; rmiss = ''; rname = ''
            tg = []
            for k, m in enumerate(refs):
                if not (a <= m.start() < b): continue
                own = cut25.ref_ctx(m.group(1)); act, art = res.get(((i, 0), k), (None, None)); disp = names.get(((i, 0), k))
                if not art and not own[0]: continue
                tg.append((art, disp, False))
                if not own[0]: tg += [(art, d, True) for d in allacts if d != disp]      # акт взят из контекста: пробуем и другие акты ответа
            got = set(); tried = False; best = -1.0
            for art, disp, fb in tg:
                if not disp or (fb and best >= 0.6 and not (nums and len(got) < len(nums))): continue
                for fi in act_idx(disp):
                    c0, c1 = int(A_.f0[fi]), int(A_.f0[fi + 1])
                    aid = ARTID.get(re.sub(r'\D', '', art)) if art else None
                    if aid is not None:
                        ch = (c0 + np.nonzero(A_.cart[c0:c1] == aid)[0]).tolist()
                        if not ch: continue
                        if len(ch) > 8:
                            mask = np.zeros(A_.C, dtype=bool); mask[ch] = True; two = A_.score(words + nums, {**wt, **{x: 1.0 for x in nums}}, mask); t = int(two.argmax()); ch2 = [c for c in (t - 1, t, t + 1, t + 2) if c in ch]
                        else: ch2 = ch
                        cv, _h = A_.cover(words, wt, ch2); _c, hn = A_.cover(nums, {x: 1 for x in nums}, ch)
                    elif fb or art and c1 - c0 > 3 and (A_.cart[c0:c1] != 0).mean() > 0.5: continue    # в акте со статьями такой статьи нет
                    else:
                        mask = np.zeros(A_.C, dtype=bool); mask[c0:c1] = True
                        two = A_.score(words + nums, {**wt, **{x: 1.0 for x in nums}}, mask); t = int(two.argmax())
                        ch = [c for c in range(t - 2, t + 4) if c0 <= c < c1]
                        cv, _h = A_.cover(words, wt, [c for c in (t - 1, t, t + 1, t + 2) if c0 <= c < c1]); _c, hn = A_.cover(nums, {x: 1 for x in nums}, ch)
                    tried = True; val = cv + (len(hn) / len(nums) if nums else 0)
                    if val > best + (len(got) / len(nums) if nums and best >= 0 else 0) or best < 0:
                        best = cv; got = set(hn); rname = ('~' if fb else '') + A_.names[fi][:40]
            if tried: rc = '%.2f' % best; rmiss = ','.join(x for x in nums if x not in got)
            elif tg: rc = 'нет'
            # лучшее место в актах и в литературе
            o = []; anyn = set(got)
            for X in (A_, L_):
                two = X.score(words + nums, {**wt, **{x: 0.5 for x in nums}}); t = int(two.argmax())
                cv, _h = X.cover(words, wt, [t, t + 1]); _c, hn = X.cover(nums, {x: 1 for x in nums}, [t - 1, t, t + 1, t + 2]); anyn |= hn
                o.append(('%.2f' % cv, X.names[int(X.cfile[t])][:40]))
            kind = 'блок' if block else ('опр' if line.startswith('>') else ('цит' if '«' in s and any(len(s[x + 1:y - 1].split()) >= 4 for x, y in qcheck2.quotes(s)) else 'текст'))
            rows.append('\t'.join(['q%03d:%d:%d' % (n, i + 1, si + 1), kind, rc, o[0][0], o[1][0], rmiss, ','.join(x for x in nums if x not in anyn), rname or o[0][1], o[1][1], s[:400]]))
    return rows
if __name__ == '__main__':
    for n in (only or range(1, 150)):
        for r in run(n): print(r)
        sys.stdout.flush()
