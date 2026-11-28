#!/usr/bin/env python3
"""bl25.py [show] — блок «Главное для запоминания» против текста ответа после сокращения:
ссылки блока (статья + часть/пункт), которых больше нет в тексте ответа. С show печатает строки версии до сокращения, где такая ссылка была."""
import re, sys, os, glob, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
BASE = '30db505'
def old(n): return subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (BASE, n)], capture_output=True, text=True, cwd=HERE).stdout
def keys(lines):
    """множество (статья, часть/пункт) для всех ссылок; неполная ссылка получает статью из контекста"""
    pieces = [((i, 0), l) for i, l in enumerate(lines) if l.strip()]
    res, names = cut25.resolve(pieces); out = {}
    for (i, _z), line in pieces:
        for k, m in enumerate(cut25.REF.finditer(line)):
            act, art = res[((i, 0), k)]; r = m.group(1)
            arts = re.findall(r'[Сс]т\.\s*(\d+(?:\.\d+)*)', r) or ([art] if art else [])
            parts = re.findall(r'(?:[Чч]|[Пп]|подп|Подп)\.\s*([\dа-я«»., и–-]+?)(?=\s*(?:ст\.|ч\.|п\.|$|[А-ЯЁа-яё]{3}))', r)
            nums = set()
            for p in parts:
                for x in re.findall(r'\d+(?:\.\d+)*', p): nums.add(x)
            for a in arts:
                for x in (nums or {''}): out.setdefault((a, x), i)
    return out
show = len(sys.argv) > 1 and sys.argv[1] == 'show'; tot = 0; ans = 0
for f in sorted(glob.glob(cut25.A + 'q*.txt')):
    n = int(f[-7:-4]); L = open(f, encoding='utf-8').read().split('\n')
    bi = [i for i, l in enumerate(L) if l.startswith('!! ')]
    if not bi: continue
    body = [l for l in L if not l.startswith('!! ')]; blk = [l[3:] for l in L if l.startswith('!! ')]
    kb = keys(body); kk = keys(blk)
    arts_body = {a for a, x in kb}
    miss = sorted({(a, x) for (a, x) in kk if (a, x) not in kb and x and not ((a, '') in kb and False)})
    # часть статьи считается покрытой, если в тексте есть ссылка на эту статью целиком без частей — нет: требуем часть
    O = [l for l in old(n).split('\n') if not l.startswith('!! ')]; ko = keys(O)
    miss = [k for k in miss if k in ko]      # только то, что было в тексте до сокращения
    if not miss: continue
    ans += 1; tot += len(miss)
    print('q%03d: в блоке есть, в тексте нет: %s' % (n, ', '.join('ст. %s ч./п. %s' % (a, x) for a, x in miss)))
    if show:
        for a, x in miss:
            if (a, x) in ko: print('      было [%s/%s]: %s' % (a, x, O[ko[(a, x)]][:330]))
            else: print('      [%s/%s] и до сокращения в тексте не было' % (a, x))
print('ответов:', ans, 'ссылок:', tot)
