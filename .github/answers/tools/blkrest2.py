#!/usr/bin/env python3
"""blkrest2.py [N…] [apply] — предложения блока «Главное для запоминания», убранные при сокращении (есть в 30db505,
нет сейчас). Для каждого считается, покрыто ли оно текущим текстом ответа (слова по основам и ссылки //…//).
С «apply» покрытые предложения возвращаются в блок на прежнее место; непокрытые только печатаются."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
A = os.path.join(HERE, '..', 'adp2')
st = lambda w: w[:5] if len(w) > 6 else w[:4]
words = lambda s: [w for w in re.findall(r'[а-яё]+', re.sub(r'//[^/]*//', ' ', s).lower().replace('ё', 'е')) if len(w) >= 5]
nums = lambda s: set(re.findall(r'\d+(?:\.\d+)*', ' '.join(re.findall(r'//([^/]*)//', s))))
only = [int(a) for a in sys.argv[1:] if a.isdigit()]; ap = 'apply' in sys.argv; show = 'show' in sys.argv; nr = nw = nb = 0
for q in range(1, 150):
    if only and q not in only: continue
    p = os.path.join(A, 'q%03d.txt' % q); L = open(p, encoding='utf-8').read().split('\n')
    O = subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n')
    bi = next(i for i, l in enumerate(L) if l.startswith('!! ')); ob = next(l for l in O if l.startswith('!! '))
    cs = cut25.split_sent(L[bi][3:]); os_ = cut25.split_sent(ob[3:])
    body = ' '.join(l for l in L if not l.startswith('!! ')); bs = set(st(w) for w in words(body)); bn = nums(body)
    cset = set(s.strip() for s in cs); res = []; ch = False
    for s in os_:
        t = s.strip()
        if t in cset: res.append(t); continue
        # предложение могло быть переписано: ищем текущее с тем же началом
        cur = next((c.strip() for c in cs if c.strip()[:25] == t[:25]), None)
        if cur: res.append(cur); continue
        ws = words(t); miss = sorted({w for w in ws if st(w) not in bs}); mn = sorted(nums(t) - bn)
        ok = len(miss) <= 1 and len(mn) == 0
        if ok:
            nr += 1; nw += len(t.split()); res.append(t); ch = True
            if show: print('q%03d + %s' % (q, t[:200]))
        else:
            nb += 1
            if show or only: print('q%03d ? [%s | %s] %s' % (q, ', '.join(miss), ', '.join(mn), t[:200]))
    extra = [c.strip() for c in cs if c.strip() not in res]
    if extra: res += extra
    if ap and ch:
        L[bi] = '!! ' + ' '.join(res); open(p, 'w', encoding='utf-8').write('\n'.join(L))
print('вернуть', nr, 'слов', nw, '; не покрыто текстом', nb)
