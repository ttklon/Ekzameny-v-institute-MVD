# -*- coding: utf-8 -*-
"""Правка имён изданий после раскладки: повторы одного издания, авторский знак в начале названия, служебный текст вместо названия.
Запуск: python3 polish5d.py [коды]. Повторный запуск безопасен."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5
os.chdir(ROOT)
def run(code):
    S = DISC[code]['dir'] + '/2. Источники/'; MP = D5 + 'manifest_%s.json' % code
    man = [m for m in json.load(open(MP, encoding='utf-8')) if os.path.exists(S + m['dst'])]
    names = {m['dst'].lower() for m in man}; out = []; st = dict(повторов=0, переименовано=0)
    byname = {m['dst']: m for m in man}
    for m in man:
        if m['cat'] not in ('book', 'sci'): out.append(m); continue
        d, f = os.path.split(m['dst']); base, ext = os.path.splitext(f)
        mm = re.match(r'^(.*) \((\d)\)$', base)
        if mm:
            first = byname.get(d + '/' + mm.group(1) + ext)
            if first and first.get('pages') == m.get('pages') and abs(first.get('size', 0) - m.get('size', 0)) < 0.2 * max(first.get('size', 1), 1):
                os.remove(S + m['dst']); st['повторов'] += 1; continue
        new = base
        new = re.sub(r'^((?:ред\. |сост\. )?[^.]*?(?: и др)?\. )[А-ЯЁ]\s?[–-]\s?\d{1,3}\s+', r'\1', new)
        if re.search(r'Авторский вклад|Печатается по|Рецензент', new):
            cat = os.path.basename(os.path.dirname(m.get('lib') or '')) or 'Издание'
            new = '%s. %s' % (re.sub(r'^\d{4}\s*', '', cat).strip(' .'), m.get('year') or '')
            m['how'] = 'каталог'; m['title'] = new; m['authors'] = ''
        if new != base:
            k = 2; cand = new
            while (d + '/' + cand + ext).lower() in names: cand = '%s (%d)' % (new, k); k += 1
            os.rename(S + m['dst'], S + d + '/' + cand + ext); names.add((d + '/' + cand + ext).lower())
            m['dst'] = d + '/' + cand + ext; m['title'] = re.sub(r'^[А-ЯЁ]\s?[–-]\s?\d{1,3}\s+', '', m['title']); st['переименовано'] += 1
        out.append(m)
    json.dump(out, open(MP, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(code, st)
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in DISC] or list(DISC): run(code)
