#!/usr/bin/env python3
"""recentp.py ФАЙЛ_ВСЕХ_ССЫЛОК ФАЙЛ_АКТА КОД_АКТА [ГОДЫ] [-w ШИРИНА] [-l] [-a]

То же, что recent.py, но с точностью до пункта и для любого акта со статьями (закон «О полиции», № 342-ФЗ,
№ 115-ФЗ и т. п.): в частях с длинными перечнями (ч. 1 ст. 12, ч. 1 ст. 13 закона «О полиции») меняется один
пункт, а ссылаются ответы на десятки других.
Единица — пункт части (или часть, или статья), после текста которой стоит отметка «(В редакции … от ДД.ММ.ГГГГ № …)»,
«(Дополнение пунктом …)» с нужным годом. Для каждой единицы печатается её текст и предложения ответов, которые
ссылаются на этот пункт (или на часть, если пункт в ссылке не назван — только с -a: таких ссылок много,
и о содержании пункта они обычно не говорят). Ссылки на статью целиком собраны в конце, по одному блоку на статью.
  -l   только перечень изменённых единиц с началом текста;
  -a   показывать и ссылки без пункта на часть, где изменён пункт;
  -A   для ссылок на статью целиком печатать текст каждой изменённой единицы статьи;
  -w   сколько знаков текста нормы печатать (по умолчанию 700).
"""
import re, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawtext as L

NOTE = re.compile(r'\((?:[^()]|\([^()]*\))*?от\s\d\d\.\d\d\.\d{4}\s№(?:[^()]|\([^()]*\))*?\)')
PNT = re.compile(r'(?<= )(\d+(?:[. ]\d+)?|[а-яё]) ?\) ')

def norm(p): return re.sub(r'[\s.«»"]', '', p or '')

def units(path, years):
    yr = '|'.join(years); date = re.compile(r'от\s\d\d\.\d\d\.(?:%s)\s№\s?[\d\w-]+' % yr)
    out = collections.OrderedDict()
    for art, body in L.articles(path).items():
        ps = L.parts(body); spans = []
        for p, txt in ps.items():
            i = body.find(txt)
            if i >= 0: spans.append((i, i + len(txt), p))
        for m in NOTE.finditer(body):
            n = m.group(0)
            if len(n) > 900: continue
            ds = [re.sub(r'\s+', ' ', d) for d in date.findall(n)]
            if not ds: continue
            if re.match(r'\((?:Статья в редакции|Дополнение статьей|Наименование)', n):
                key = (art, '', ''); txt = body
            else:
                part = next((p for a, b, p in spans if a <= m.start() < b), ''); a0 = next((a for a, b, p in spans if a <= m.start() < b), 0)
                seg = body[a0:m.start()]
                # предыдущая отметка отделяет чужой пункт или абзац
                prev = [x for x in NOTE.finditer(seg)]; cut = prev[-1].end() if prev else 0
                labs = list(PNT.finditer(' ' + seg))
                if labs and part != 'прим':
                    lab = labs[-1]; key = (art, part, norm(lab.group(1))); txt = (' ' + seg)[lab.start():]
                else:
                    key = (art, part, ''); txt = seg[cut:] if len(seg) - cut > 80 else seg
            e = out.setdefault(key, dict(text=re.sub(r'\s+', ' ', txt).strip(), marks=[]))
            for d in ds:
                if d not in e['marks']: e['marks'].append(d)
    return out

def name(k):
    a, p, q = k
    return ' '.join(x for x in ['п. ' + q if q else '', 'ч. ' + p if p else '', 'ст. ' + a] if x)

def window(t, sent, w):
    t = L.strip_marks(t) if hasattr(L, 'strip_marks') else t
    if len(t) <= w: return t
    st = L.stems(re.sub(r'//.*?//', '', sent)) if sent else set(); bp = 0; bs = -1
    for p in range(0, len(t) - w + 1, 60):
        sc = len(st & L.stems(t[p:p + w]))
        if sc > bs: bs, bp = sc, p
    return ('…' if bp else '') + t[bp:bp + w] + '…'

if __name__ == '__main__':
    argv = sys.argv[1:]; w = 700
    if '-w' in argv: i = argv.index('-w'); w = int(argv[i + 1]); del argv[i:i + 2]
    args = [a for a in argv if not a.startswith('-')]
    refs, path, code = args[0], args[1], args[2]
    years = args[3].split(',') if len(args) > 3 else ['2025', '2026']
    us = units(path, years)
    if '-l' in argv:
        for k, e in us.items(): print('%s | %s\n   %s' % (name(k), '; '.join(e['marks']), window(e['text'], '', min(w, 260))))
        print('-- изменённых единиц:', len(us)); sys.exit()
    hits = collections.defaultdict(list); arthits = collections.defaultdict(list); skipped = 0
    for b in re.split(r'\n\s*\n', open(refs, encoding='utf-8').read()):
        m = re.match(r'(\S+)\s+(\S.*?)\s+\[(.*?) ← (\S+)', b)
        if not m or m.group(4) != code: continue
        ref = m.group(3); am = re.search(r'ст ([\d.,]+)', ref)
        if not am: continue
        tok = dict((a, [norm(x) for x in b.split(',')]) for a, b in re.findall(r'(?:^| )(подп|п|ч) ([\w.,«»]+)', ref))
        # «п. 13 ст. 5» в законах, где статьи делятся на пункты, — это единица уровня части
        if 'ч' in tok: parts_, pnts, loose = tok['ч'], tok.get('п'), False
        elif 'п' in tok and 'подп' in tok: parts_, pnts, loose = tok['п'], tok['подп'], False
        elif 'п' in tok: parts_, pnts, loose = tok['п'], None, True
        else: parts_, pnts, loose = None, None, False
        sent = b.split('\n')[1].strip() if '\n' in b else ''
        for art in am.group(1).split(','):
            if not parts_ and not pnts:
                if any(k[0] == art for k in us): arthits[art].append((m.group(1), ref, sent))
                continue
            for k in us:
                if k[0] != art: continue
                if loose:
                    if k[1] and k[1] in parts_: lvl = 'part'
                    elif k[2] and k[2] in parts_ and k[1] in ('', '1'): lvl = 'pnt'
                    elif not k[1] and not k[2]: lvl = 'part'
                    else: continue
                    if lvl == 'part' and k[2]:
                        if '-a' not in argv: skipped += 1; continue
                else:
                    if parts_ and k[1] and k[1] not in parts_: continue
                    if pnts and k[2] and k[2] not in pnts: continue
                    if k[2] and not pnts:
                        if '-a' not in argv: skipped += 1; continue
                hits[k].append((m.group(1), ref, sent))
    n = 0; na = 0
    for k, e in us.items():
        if not hits[k]: continue
        print('== %s | %s' % (name(k), '; '.join(e['marks'])))
        print('   Н: ' + window(e['text'], ' '.join(s for _, _, s in hits[k]), w))
        seen = set()
        for loc, ref, sent in hits[k]:
            if (loc, sent) in seen: continue
            seen.add((loc, sent)); n += 1
            print('   %s [%s]\n      %s' % (loc, ref, sent))
        print()
    for art, hs in arthits.items():
        ks = [k for k in us if k[0] == art]
        print('== ст. %s — ссылки на статью целиком; изменены: %s' % (art, ', '.join(name(k).replace(' ст. ' + art, '') if (k[1] or k[2]) else 'статья' for k in ks)))
        if '-A' in argv:
            for k in ks: print('   Н %s: %s' % (name(k), window(us[k]['text'], ' '.join(s for _, _, s in hs), w)))
        seen = set()
        for loc, ref, sent in hs:
            if (loc, sent) in seen: continue
            seen.add((loc, sent)); na += 1
            print('   %s [%s]\n      %s' % (loc, ref, sent))
        print()
    print('-- изменённых единиц: %d, из них со ссылкой на часть или пункт: %d; предложений: %d; предложений со ссылкой на изменённую статью целиком: %d; ссылок без пункта на часть с изменённым пунктом (не показаны без -a): %d'
          % (len(us), sum(1 for k in us if hits[k]), n, na, skipped))
