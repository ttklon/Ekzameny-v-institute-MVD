#!/usr/bin/env python3
"""normfixE25.py [apply] [N…] — возврат членов перечней, выпавших при сокращении из сохранившихся разделов:
1) блок с названием (**…**) вместе с его пунктами; 2) пункты перечня, от которого осталась часть;
3) вводная строка, от которой остались одни пункты. Пункты, оказавшиеся под чужой вводной строкой,
возвращаются под свою. Текст берётся из 30db505; сохранившиеся строки остаются в нынешнем виде.
Применён в два прохода: «apply» и «apply unnamed» (вводная строка без названия, выпавшая вместе со всем перечнем).
После первого прохода вручную убраны повторы там, где сохранившаяся строка была переписана (введено полное название акта);
повторно не запускать: скрипт вернёт эти повторы."""
import re, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, '..', 'adp2')
isb = lambda s: bool(re.match(r'\s*(-|\d+\.)\s', s))
hk = lambda h: re.sub(r'^##\s*\d+\.\s*', '', h).strip()
ck = lambda l: l[:30]
FIX = lambda s: s.replace('УК РФа Российской Федерации', 'Уголовного кодекса Российской Федерации')
def old(q): return [FIX(x) for x in subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True, cwd=HERE).stdout.split('\n')]
def split(L):
    """[(heading|None, [непустые строки])], последняя часть — блок !!"""
    P = [[None, []]]
    for l in L:
        if l.startswith('## ') or l.startswith('!! ') or l.startswith('# '): P.append([l, []])
        elif l.strip(): P[-1][1].append(l)
    return P
def emit(P):
    out = []
    for h, body in P:
        if h is not None: out += [h, '']
        for i, l in enumerate(body):
            out.append(l)
            if not (isb(l) and i + 1 < len(body) and isb(body[i + 1])): out.append('')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).rstrip('\n') + '\n'
def blocks(body):
    B = []
    for l in body:
        if isb(l) and B: B[-1].append(l)
        elif isb(l): B.append([None, l])          # перечень в начале раздела, без вводной строки
        else: B.append([l])
    return B
def cpl(a, b):
    n = min(len(a), len(b)); i = 0
    while i < n and a[i] == b[i]: i += 1
    return i
def same(o, c):
    """c — нынешний вид прежней строки o (дословно либо с усечённым концом)"""
    if o == c: return True
    k = cpl(o, c); m = min(len(o.rstrip('.;: ')), len(c.rstrip('.;: ')))
    return k >= 30 and (k >= m or k >= 80 or k >= 0.6 * m)
def punct(cur, o):
    if cur == o: return cur
    if cur.rstrip('.;') == o.rstrip('.;'): return o
    if o.rstrip().endswith(';') and cur.rstrip().endswith('.'): return cur.rstrip()[:-1] + ';'
    if o.rstrip().endswith('.') and cur.rstrip().endswith(';'): return cur.rstrip()[:-1] + '.'
    return cur
UNNAMED = 'unnamed' in sys.argv   # второй проход: вводная строка без названия, выпавшая вместе со всем перечнем
def fix_section(obody, cbody, log):
    C = list(cbody); added = 0
    def find(l):
        if l is None: return None
        best = None; bk = -1
        for i, x in enumerate(C):
            if same(l, x) and cpl(l, x) > bk: best = i; bk = cpl(l, x)
        return best
    OB = blocks(obody)
    for bi, b in enumerate(OB):
        head, items = b[0], b[1:]
        if head is None and UNNAMED: continue
        if head is None:
            for k, x in enumerate(items):
                if find(x) is not None: continue
                pos = 0
                for y in reversed(items[:k]):
                    if find(y) is not None: pos = find(y) + 1; break
                C.insert(pos, x); added += len(x.split()); log.append(('+пункт', x[:60], 1))
            continue
        hp = find(head); ip = [find(x) for x in items]
        named = head.startswith('**')
        lost_items = [x for x, p in zip(items, ip) if p is None]
        if hp is not None and not lost_items:
            if not items: continue
            run_end = hp + 1
            while run_end < len(C) and isb(C[run_end]): run_end += 1
            if all(hp < p < run_end for p in ip): continue
        if hp is None and not items and not named: continue          # обычный абзац — не возвращаем
        whole = hp is None and bool(items) and not named and all(p is None for p in ip)   # вводная строка и весь её перечень
        if UNNAMED != whole: continue
        # собрать полный блок
        cur_items = {}
        for x, p in zip(items, ip):
            if p is not None: cur_items[x] = C[p]
        take = sorted([p for p in ip if p is not None], reverse=True)
        if hp is not None:
            # пункты, идущие сразу за вводной строкой и не относящиеся к прежнему перечню (вставлены позже), сохраняем в конце
            run_end = hp + 1
            while run_end < len(C) and isb(C[run_end]): run_end += 1
            extra = [C[i] for i in range(hp + 1, run_end) if i not in take]
            headline = C[hp]
            rm = sorted((set(take) | set(range(hp + 1, run_end))) - {hp}, reverse=True)
            for i in rm: del C[i]
            hp = C.index(headline)
            new_items = [punct(cur_items[x], x) if x in cur_items else x for x in items] + extra
            C[hp + 1:hp + 1] = new_items
            added += sum(len(x.split()) for x in lost_items)
            log.append(('+пункты', head[:60], len(lost_items)))
        else:
            for i in take: del C[i]
            # якорь: ближайшая предыдущая прежняя строка раздела, сохранившаяся сейчас
            pos = 0
            prev = [x for bb in OB[:bi] for x in bb]
            for x in reversed(prev):
                p = find(x)
                if p is not None:
                    pos = p + 1
                    while pos < len(C) and isb(C[pos]): pos += 1
                    break
            new_items = [punct(cur_items[x], x) if x in cur_items else x for x in items]
            C[pos:pos] = [head] + new_items
            added += len(head.split()) + sum(len(x.split()) for x in lost_items)
            log.append(('+блок', head[:60], len(lost_items)))
    return C, added
def run(q, apply):
    p = os.path.join(A, 'q%03d.txt' % q); txt = open(p, encoding='utf-8').read()
    P = split(txt.split('\n')); O = split(old(q))
    om = {hk(h): body for h, body in O if h and h.startswith('## ')}
    tot = 0; logs = []
    for part in P:
        h = part[0]
        if not h or not h.startswith('## ') or hk(h) not in om: continue
        log = []
        part[1], a = fix_section(om[hk(h)], part[1], log)
        tot += a
        if log: logs.append((hk(h), log))
    new = emit(P)
    if apply and new != txt: open(p, 'w', encoding='utf-8').write(new)
    return tot, logs, new != txt
if __name__ == '__main__':
    apply = 'apply' in sys.argv; only = [int(a) for a in sys.argv[1:] if a.isdigit()]
    T = 0; nq = 0; nb = 0
    if 'roundtrip' in sys.argv:
        bad = [q for q in range(1, 150) if emit(split(open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read().split('\n'))) != open(os.path.join(A, 'q%03d.txt' % q), encoding='utf-8').read()]
        print('формат меняется без правок в:', bad); sys.exit()
    for q in range(1, 150):
        if only and q not in only: continue
        t, logs, ch = run(q, apply)
        if ch:
            nq += 1; T += t; nb += sum(len(l) for _, l in logs)
            if 'v' in sys.argv:
                for h, l in logs:
                    for k, hd, n in l: print('q%03d [%s] %s %s (%d)' % (q, h[:30], k, hd, n))
    print('ответов изменено:', nq, 'блоков и перечней:', nb, 'слов возвращено:', T)
