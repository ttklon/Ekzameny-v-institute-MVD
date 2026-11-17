#!/tmp/venv/bin/python
"""ol.py N [N2] — сжатое оглавление автоверсии (/tmp/auto) для выбора сокращений.
абзац:  <строка> <слов> <флаги> <начало>;  список: <a-b> L<пунктов> <слов> <флаги> <начало первого пункта>
флаги: r — есть ссылка на норму, q — цитата, D — вводится сокращение («далее —»), * — кандидат правила A"""
import sys, re
sys.path.insert(0, '/tmp/w'); import mk2
Q = None
def is_A(x):
    """собственный текст без нормы: обычный абзац без ссылки и цитаты, не вводная к списку, не определение"""
    if not x.strip() or x[0] in '#>!' or x.lstrip().startswith('- '): return False
    if '//' in x or '«' in x or x.rstrip().rstrip('*').endswith(':'): return False
    return True
def outline(n):
    global Q
    if Q is None: Q = mk2.load_v1()
    L = open('/tmp/auto/q%03d.txt' % n, encoding='utf-8').read().split('\n')
    v1 = len(Q[n][1].split()); tot = sum(len(x.split()) for x in L)
    wa = sum(len(x.split()) for x in L if is_A(x))
    print('=== %d | v1 %d | авто %d | убрать %d (1,3) … %d (1,4) | A даёт %d' % (n, v1, tot, tot - v1 / 1.3, tot - v1 / 1.4, wa))
    sec = {}; cur = None
    for i, x in enumerate(L):
        if x.startswith('## '): cur = i; sec[cur] = 0
        elif cur is not None and not x.startswith('!!'): sec[cur] += len(x.split())
    i = 0
    while i < len(L):
        x = L[i]
        if not x.strip() or x.startswith('# ') or x.startswith('!!'): i += 1; continue
        if x.startswith('## '):
            print('%d [%d] %s' % (i, sec[i], x[3:68])); i += 1; continue
        if x.lstrip().startswith('- '):
            j = i; w = 0; fl = set(); k = 0
            while j < len(L) and (L[j].lstrip().startswith('- ')):
                w += len(L[j].split()); k += 1
                if '//' in L[j]: fl.add('r')
                if '«' in L[j]: fl.add('q')
                if 'далее —' in L[j]: fl.add('D')
                j += 1
            print('%d-%d L%d %d %s %s' % (i, j - 1, k, w, ''.join(sorted(fl)) or '-', x.replace('**', '').lstrip('- ')[:34])); i = j; continue
        fl = ('r' if '//' in x else '') + ('q' if '«' in x else '') + ('D' if 'далее —' in x else '') + ('*' if is_A(x) else '')
        print('%d %d %s %s' % (i, len(x.split()), fl or '-', x.replace('**', '')[:48])); i += 1
if __name__ == '__main__':
    a = int(sys.argv[1]); b = int(sys.argv[2]) if len(sys.argv) > 2 else a
    for n in range(a, b + 1):
        if n in mk2.MANUAL: continue
        outline(n)
