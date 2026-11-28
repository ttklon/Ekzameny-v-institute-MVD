#!/usr/bin/env python3
"""bl25fix.py [apply] [MAXW] — возвращает в текст строки, на которые ссылается блок «Главное для запоминания» (по списку bl25.py),
если раздел строки сохранился; строка ставится на прежнее место (после ближайшей сохранившейся предыдущей строки раздела)."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
apply = 'apply' in sys.argv; MAXW = int(([a for a in sys.argv[1:] if a.isdigit()] or [45])[0])
out = subprocess.run([sys.executable, os.path.join(HERE, 'bl25.py'), 'show'], capture_output=True, text=True).stdout
d = {}; cur = None
for l in out.split('\n'):
    m = re.match(r'q(\d+):', l)
    if m: cur = int(m.group(1)); continue
    m = re.match(r'\s+было \[[^\]]*\]: (.*)', l)
    if m and m.group(1) not in d.setdefault(cur, []): d[cur].append(m.group(1))
hk = lambda h: re.sub(r'^##\s*\d+\.\s*', '', h).strip()
tot = n = skip = 0
for q, ls in sorted(d.items()):
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True, cwd=HERE).stdout.split('\n')
    p = cut25.A + 'q%03d.txt' % q; C = open(p, encoding='utf-8').read().split('\n'); ch = False
    for s in ls:
        oi = [i for i, x in enumerate(O) if x.startswith(s[:300])][0]; full = O[oi]; w = len(full.split())
        if full in C: continue
        h = next((O[i] for i in range(oi, -1, -1) if O[i].startswith('## ')), None)
        ci = next((i for i, x in enumerate(C) if x.startswith('## ') and h and hk(x) == hk(h)), None)
        if w > MAXW or ci is None: skip += 1; print('  пропуск q%03d (%d сл., раздел %s): %s' % (q, w, 'есть' if ci is not None else 'удалён', full[:110])); continue
        end = next((i for i in range(ci + 1, len(C)) if C[i].startswith('## ') or C[i].startswith('!! ')), len(C))
        # ближайшая предыдущая строка исходного раздела, сохранившаяся в текущем
        pos = None
        for i in range(oi - 1, -1, -1):
            if O[i].startswith('## '): break
            if O[i].strip() and O[i] in C[ci:end]: pos = ci + C[ci:end].index(O[i]); break
        if pos is None: pos = ci
        item = full.startswith('- ') or full.startswith('  - ')
        prev_item = C[pos].startswith('- ') or C[pos].startswith('  - ')
        if item and prev_item:
            # если предыдущий пункт завершал перечень точкой, а вставка идёт в конец — оставляем как есть
            C.insert(pos + 1, full)
        else:
            C[pos + 1:pos + 1] = ['', full]
        tot += w; n += 1; ch = True
        print('q%03d +%d: %s' % (q, w, full[:120]))
    if ch and apply:
        t = re.sub(r'\n{3,}', '\n\n', '\n'.join(C)); open(p, 'w', encoding='utf-8').write(t)
print('вставлено строк:', n, 'слов:', tot, 'пропущено:', skip)
