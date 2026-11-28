#!/usr/bin/env python3
"""look25.py SRC ЗАПРОС [ЗАПРОС…] — показать место акта из папки extract_src.py (для чтения ответа рядом с текстом нормы).
ЗАПРОС — поля через «|»:
  ФАЙЛ|СТАТЬЯ[|ЧАСТЬ[|ПУНКТ]]   — статья закона или кодекса, её часть, пункт части («К|27.5|2», «П|13|1|16», «П|2||5» — пункт без части);
  ФАЙЛ|п N[|ПОДПУНКТ]            — пункт N приказа, постановления, указа, постановления Пленума («a3078c|п 28»);
  ФАЙЛ|/РЕГУЛЯРНОЕ ВЫРАЖЕНИЕ/    — места текста с этим выражением.
ФАЙЛ — часть имени файла (берётся HTML-версия, если она есть) или сокращение: К — КоАП РФ, П — Закон о полиции,
С — Закон о службе, У — УК РФ. В конце запроса можно дать «|=ЧИСЛО» — сколько знаков печатать (по умолчанию 900)."""
import sys, os, re, collections
SRC = sys.argv[1]
AL = {'К': 'КоАП РФ от 30.12.2001', 'П': '№ 3-ФЗ О полиции', 'С': '№ 342-ФЗ О службе', 'У': 'Уголовный кодекс'}
CLEAN = re.compile(r'\((?:[ВвДд]\s+редакци|[Дд]ополнени\w*\s+-|[Уу]тратил\w*\s+силу\s+-|[Вв]\s+ред\.)[^()]*(?:\([^()]*\)[^()]*)*\)')
NAMES = sorted(os.listdir(SRC))
def find(key):
    key = AL.get(key, key); c = [n for n in NAMES if key.lower() in n.lower()]
    h = [n for n in c if n.endswith('.html.txt')]
    return (h or c or [None])[0]
def load(name):
    raw = open(os.path.join(SRC, name), encoding='utf-8', errors='replace').read()
    return CLEAN.sub(' ', re.sub(r'<\d+>', ' ', raw))
def arts(raw):
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
def sq(s): return re.sub(r'\s+', ' ', s).strip()
def punkt(raw, n, w):
    """пункт n акта без статей: от « n. Заглавная» до следующего по счёту номера"""
    t = sq(raw); out = []; nx = None
    if re.fullmatch(r'\d+', n): nx = str(int(n) + 1)
    elif re.fullmatch(r'\d+(\.\d+)+', n):
        a = n.split('.'); nx = '.'.join(a[:-1] + [str(int(a[-1]) + 1)])
    for m in re.finditer(r'(?<![\d№,]) ' + re.escape(n) + r'\. ?(?=[А-ЯЁ«(\[])', t):
        e = re.search(r'(?<![\d№,]) ' + re.escape(nx) + r'\. ?(?=[А-ЯЁ«(\[])', t[m.end():m.end() + 30000]) if nx else None
        out.append(t[m.start():m.end() + (e.start() if e else w)])
    return out
def main():
    for q in sys.argv[2:]:
        f = q.split('|'); w = 900
        if f[-1].startswith('='): w = int(f.pop()[1:])
        name = find(f[0])
        if not name: print('### %s: файл не найден' % q); continue
        raw = load(name); print('### %s  [%s]' % (q, name[7:70]))
        if len(f) > 1 and f[1].startswith('/'):
            t = sq(raw); k = 0
            for m in re.finditer(f[1].strip('/'), t):
                print('  …' + t[max(0, m.start() - w // 3):m.start() + w * 2 // 3]); k += 1
                if k >= 6: break
            if not k: print('  НЕ НАЙДЕНО')
        elif len(f) > 1 and f[1].startswith('п '):
            ps = punkt(raw, f[1][2:].strip(), w)
            if not ps: print('  ПУНКТ НЕ НАЙДЕН')
            for p in ps[:4]:
                if len(f) > 2:
                    m = re.search(r'(?<![\d.]) ?' + re.escape(f[2]) + r'\) ', p)
                    p = p[m.start():] if m else 'ПОДПУНКТ НЕ НАЙДЕН: ' + p
                print('  ' + p[:w])
        else:
            A = arts(raw); a = A.get(f[1]) if len(f) > 1 else None
            if a is None: print('  СТАТЬИ НЕТ; всего статей %d' % len(A)); continue
            part = f[2] if len(f) > 2 else ''; pu = f[3] if len(f) > 3 else ''
            t = a
            if part:
                P = split(a, PART)
                if part not in P: print('  ЧАСТИ НЕТ; есть: ' + ' '.join(k for k in P if k) + ' | ' + sq(a)[:300]); continue
                t = P[part]
            if pu:
                U = split(t, PUNKT)
                if pu not in U and not part: U = split(a, PART)
                if pu not in U: print('  ПУНКТА НЕТ; есть: ' + ' '.join(k for k in U if k) + ' | ' + sq(t)[:300]); continue
                t = U[pu]
            print('  ' + sq(t)[:w])
if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main()
