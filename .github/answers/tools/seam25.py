#!/usr/bin/env python3
"""seam25.py — швы после сокращения: 1) сокращение «далее — X» осталось без введения; 2) краткое название акта с номером без полного названия в ответе.
seam25.py [fix] — с fix: недостающее введение добавляется пунктом в конец перечня «Правовая основа» (полное название берётся из версии до сокращения)."""
import re, sys, os, glob, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import cut25
BASE = '30db505'
fix = len(sys.argv) > 1 and sys.argv[1] == 'fix'
def old(n): return subprocess.run(['git', 'show', '%s:.github/answers/adp2/q%03d.txt' % (BASE, n)], capture_output=True, text=True, cwd=HERE).stdout
tot = 0
for f in sorted(glob.glob(cut25.A + 'q*.txt')):
    n = int(f[-7:-4]); t = open(f, encoding='utf-8').read(); o = old(n); add = []; rep = []
    for m in re.finditer(r'\(далее —\s+([^)]+)\)|, далее —\s+([^)]+)\)', o):
        ab = (m.group(1) or m.group(2)).strip(' .')
        if re.search(r'далее —\s+' + re.escape(ab), t): continue
        body = t
        if not cut25.abbr_used(ab, body): continue
        full = None
        if ab in cut25.NOM: full = cut25.NOM[ab]
        else:
            fm = re.search(r'(//[^/]+//|«[^«»]+(?:«[^«»]*»[^«»]*)*»(?:,? утв\.[^()]*?)?)\s*\(далее —\s+' + re.escape(ab) + r'\)', o)
            if fm:
                full = fm.group(1).strip()
                if full.startswith('//'): full = cut25.to_nom(full)
        rep.append((ab, full))
        if full and (full, ab) not in add: add.append((full, ab))
    for ab, full in rep: print('q%03d нет введения: %s  ←  %s' % (n, ab, (full or 'НЕ НАЙДЕНО')[:90])); tot += 1
    if fix and add:
        L = t.split('\n'); sec = None; last = None
        for i, l in enumerate(L):
            if l.startswith('## '): sec = cut25.PRAV.search(l) is not None
            elif sec and l.startswith('- '): last = i
        if last is None: print('   q%03d: нет перечня «Правовая основа» — исправить вручную' % n); continue
        for full, ab in add:
            if full.strip('/') in t:      # полное название уже есть в тексте — дописываем введение к нему
                i = t.index(full.strip('/')); j = t.index('//', i) + 2 if full.startswith('//') else i + len(full)
                t = t[:j] + ' (далее — %s)' % ab + t[j:]; L = t.split('\n'); print('   введение дописано к полному названию:', ab); continue
            last += 1; L.insert(last, '- %s (далее — %s).' % (full, ab)); t = '\n'.join(L)
        open(f, 'w', encoding='utf-8').write(t)
print('всего:', tot)
# 2) краткое название с номером без полного названия (дата и номер) и без «далее —»
print('--- краткие названия без полного:')
k2 = 0
for f in sorted(glob.glob(cut25.A + 'q*.txt')):
    n = int(f[-7:-4]); t = open(f, encoding='utf-8').read(); seen = set()
    for m in re.finditer(r'(Закон\w*|Положени\w+|Инструкци\w+|Правил\w*|Порядк\w+|Порядок|Наставлени\w+|Указ\w*|Пленум\w*|Регламент\w*|Требовани\w+|Устав\w*|приказ\w* МВД России|Приказ\w* МВД России|Постановлени\w+|постановлени\w+) (№ \d+(?:[/.-]\d+)*(?:-[А-ЯA-Zа-я]+|дсп|н)?)', t):
        num = m.group(2)
        if num in seen: continue
        seen.add(num)
        if re.search(r'от \d\d\.\d\d\.\d{4}(?: г\.)? ' + re.escape(num) + r'(?![\d-])', t): continue
        if re.search(r'далее —[^)]*' + re.escape(num) + r'(?![\d-])', t): continue
        k2 += 1; print('q%03d %s' % (n, m.group(0)))
print('всего:', k2)
