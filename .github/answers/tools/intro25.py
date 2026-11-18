#!/usr/bin/env python3
"""intro25.py [REV] — вводные строки, оставшиеся без продолжения: короткая строка с числительным («два условия», «три группы»)
или с двоеточием на конце, после которой в редакции REV (по умолчанию 4b36cfb) шёл текст, а теперь его нет."""
import re, subprocess, sys, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
REV = next((a for a in sys.argv[1:] if not a.isdigit()), '4b36cfb')
NUMW = re.compile(r'\b(два|две|двух|три|тр[её]х|четыре|четыр[её]х|пять|пяти|шесть|шести|семь|семи|восемь|восьми|девять|десять|несколько|следующ\w+)\b', re.I)
n = 0
for q in range(1, 150):
    L = [l for l in open('adp2/q%03d.txt' % q, encoding='utf-8').read().split('\n') if l.strip()]
    O = [l for l in subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (REV, q)], capture_output=True, text=True).stdout.split('\n') if l.strip()]
    pos = {}
    for i, l in enumerate(O): pos.setdefault(l[:40], i)
    for i, l in enumerate(L):
        if l.startswith(('#', '!!', '>')) or len(l.split()) > 22: continue
        if not (l.rstrip().rstrip('*').endswith(':') or NUMW.search(l)): continue
        j = pos.get(l[:40])
        if j is None or j + 1 >= len(O) or O[j + 1].startswith(('## ', '!!')): continue
        nxt = L[i + 1] if i + 1 < len(L) else ''
        if nxt[:25] != O[j + 1][:25]:
            n += 1; print('q%03d:%d %s\n      было далее: %s\n      теперь:     %s' % (q, i + 1, l[:110], O[j + 1][:90], nxt[:90]))
print('всего', n)
