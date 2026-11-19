#!/usr/bin/env python3
"""law26.py — построчная правка варианта 2 с опорой на редакцию на 36 часов.
Редакция на 25 часов получена вычёркиванием строк из редакции на 36 часов (`4b36cfb`), и во многих разделах остались
обрывки: заголовок с одной ссылкой, «первые два из перечисленных» без перечня. Программа показывает ответ целиком —
оставленные и вычеркнутые строки подряд — и собирает новый текст по списку решений `law26_ops.tsv`.
  law26.py view N         — строки ответа N с номерами: «K» оставлена, «R» вычеркнута (есть только в редакции на 36 часов),
                            «C» есть только в нынешнем тексте (изменена или вставлена позже); в скобках число слов
  law26.py apply [N…]     — собрать ответы, для которых есть решения, записать adp2/qNNN.txt, напечатать число слов
  law26.py add            — дописать решения со стандартного ввода (поля через пробел: «N + 12 13», «N = 17 текст»)
  law26.py sub N 'было' 'стало' — заменить фрагмент в одной строке собранного ответа (решение «=» пишется само)
  law26.py words          — число слов по всем ответам
Решения (по одному в строке, поля через табуляцию): «N  +  номера» вернуть вычеркнутые строки; «N  -  номера» убрать строки;
«N  =  номер  текст» заменить текст строки (вычеркнутая строка при этом возвращается); «N  >  номер  текст» вставить новую
строку после указанной. Номера считаются по выводу view и не меняются: основа — редакции `OLD` и `CUR` из git.
Заголовки разделов «## N.» после сборки нумеруются заново."""
import sys, os, re, subprocess, difflib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..')
OLD, CUR = '4b36cfb', 'b39f4c9'
FULL = bool(os.environ.get('FULL'))        # FULL=1 — не обрезать длинные строки в view
RATIO = 0.6853                           # доля объёма редакции на 25 часов от редакции на 36 часов; цель для ответа — среднее между нынешним объёмом и этой долей
OPS = os.path.join(HERE, 'law26_ops.tsv')
def show(rev, n):
    t = subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (rev, n)], capture_output=True, text=True, cwd=ROOT).stdout
    return [l for l in t.split('\n') if l.strip()]
def merged(n):
    a, b = show(OLD, n), show(CUR, n); out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal': out += [('K', l) for l in a[i1:i2]]
        else:
            out += [('R', l) for l in a[i1:i2]]; out += [('C', l) for l in b[j1:j2]]
    return out
def islist(l): return bool(re.match(r'\s*(?:[-*] |\d+[.)] )', l))
def render(lines):
    out = []; k = 0
    for i, l in enumerate(lines):
        if l.startswith('## '):
            k += 1; l = re.sub(r'^## \d+\.', '## %d.' % k, l)
        if i and not (islist(l) and islist(lines[i - 1])): out.append('')
        out.append(l)
    return '\n'.join(out) + '\n'
def ops():
    res = {}
    if os.path.exists(OPS):
        for ln in open(OPS, encoding='utf-8').read().split('\n'):
            if not ln.strip() or ln.startswith('#'): continue
            f = ln.split('\t'); res.setdefault(int(f[0]), []).append(f[1:])
    return res
def build(n, O, num=False):
    M = merged(n); inc = {i: s != 'R' for i, (s, l) in enumerate(M)}; txt = {i: l for i, (s, l) in enumerate(M)}; after = {}
    for f in O:
        if f[0] == '+':
            for x in f[1].split(): inc[int(x)] = True  # для оставленной строки отменяет более раннее «-»
        elif f[0] == '-':
            for x in f[1].split(): inc[int(x)] = False
        elif f[0] == '=': inc[int(f[1])] = True; txt[int(f[1])] = f[2]
        elif f[0] == '>': after.setdefault(int(f[1]), []).append(f[2])
        else: raise SystemExit('q%03d: неизвестное решение %s' % (n, f[0]))
    lines = []; src = []
    for i in range(len(M)):
        if inc[i]: lines.append(txt[i]); src.append(i)
        lines += after.get(i, []); src += [None] * len(after.get(i, []))
    return (lines, src) if num else lines
def wc(t): return len(t.split())
def path(n): return os.path.join(ROOT, 'adp2', 'q%03d.txt' % n)
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'view':
        for n in map(int, sys.argv[2:]):
            M = merged(n); cur = sum(wc(l) for s, l in M if s != 'R'); old = sum(wc(l) for s, l in M if s != 'C')
            print('=== q%03d: сейчас %d слов, в редакции на 36 часов %d, цель %d' % (n, cur, old, round((cur + old * RATIO) / 2)))
            lim = {'K': 760, 'R': 460, 'C': 460}
            for i, (s, l) in enumerate(M):
                m = 160 if l.startswith('!! ') else lim[s]
                print('%s%d(%d) %s' % (s, i, wc(l), l if len(l) <= m or FULL else l[:m] + '…'))
    elif cmd == 'apply':
        O = ops(); only = [int(x) for x in sys.argv[2:]]
        for n in sorted(O):
            if only and n not in only: continue
            t = render(build(n, O[n])); was = wc('\n'.join(l for s, l in merged(n) if s != 'R'))
            old = sum(wc(l) for s, l in merged(n) if s != 'C')
            open(path(n), 'w', encoding='utf-8').write(t); print('q%03d %d → %d (%+d); цель %d' % (n, was, wc(t), wc(t) - was, round((was + old * RATIO) / 2)))
        print('всего слов: %d' % sum(wc(open(path(n), encoding='utf-8').read()) for n in range(1, 150)))
    elif cmd == 'add':                       # решения со стандартного ввода: «N + 12 13», «N - 5», «N = 17 текст», «N > 17 текст»
        with open(OPS, 'a', encoding='utf-8') as f:
            for ln in sys.stdin.read().split('\n'):
                if not ln.strip(): continue
                if ln.startswith('#'): f.write(ln + '\n'); continue
                a = ln.split(' ', 2); assert a[1] in '+-=>', ln
                if a[1] in '=>':
                    b = a[2].split(' ', 1); f.write('\t'.join([a[0], a[1], b[0], b[1].strip()]) + '\n')
                else: f.write('\t'.join(a) + '\n')
    elif cmd == 'sub':                       # law26.py sub N 'старый фрагмент' 'новый фрагмент' — правка одной строки собранного текста
        n, a, b = int(sys.argv[2]), sys.argv[3], sys.argv[4]; lines, src = build(n, ops().get(n, []), True)
        hit = [i for i, l in enumerate(lines) if a in l]
        if len(hit) != 1 or src[hit[0]] is None: raise SystemExit('q%03d: фрагмент найден %d раз(а) или стоит во вставленной строке' % (n, len(hit)))
        with open(OPS, 'a', encoding='utf-8') as f: f.write('\t'.join([str(n), '=', str(src[hit[0]]), lines[hit[0]].replace(a, b).strip()]) + '\n')
        print('q%03d: строка %d исправлена' % (n, src[hit[0]]))
    elif cmd == 'words':
        print(sum(wc(open(path(n), encoding='utf-8').read()) for n in range(1, 150)))
    elif cmd == 'selftest':
        bad = 0
        for n in range(1, 150):
            if render(show(CUR, n)) != subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (CUR, n)], capture_output=True, text=True, cwd=ROOT).stdout: bad += 1; print('q%03d: расстановка пустых строк отличается' % n)
        print('отличий: %d' % bad)
    else: sys.exit(__doc__)
if __name__ == '__main__': main()
