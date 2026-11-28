# -*- coding: utf-8 -*-
"""Уточнение привязки изданий к вопросам по оглавлению: вопрос привязывается, если ключевые слова его формулировки
стоят в одной строке оглавления (или в двух соседних). Запуск: /tmp/venv/bin/python retopic.py [коды]."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
from sel_art import keys
import fitz
os.chdir(ROOT)
fitz.TOOLS.mupdf_display_errors(False)
def toc_lines(path):
    try: d = fitz.open(path)
    except Exception: return []
    n = d.page_count; idx = list(range(min(8, n))) + [i for i in range(max(8, n - 7), n)]
    out = []
    for i in idx:
        try: t = d[i].get_text()
        except Exception: continue
        if not re.search(r'оглавление|содержание', t[:400], re.I) and not re.search(r'\.{6,}\s*\d+|…{3,}\s*\d+', t): continue
        out += [' '.join(l.split()) for l in t.split('\n') if l.strip()]
    d.close()
    return out
def run(code):
    S = DISC[code]['dir'] + '/2. Источники/'; MP = D5 + 'manifest_%s.json' % code
    man = json.load(open(MP, encoding='utf-8'))
    tt = topics(code); tk = {t['id']: keys(code, t['text']) for t in tt}
    n = 0; withtoc = 0; added = 0
    for m in man:
        if m['cat'] not in ('book', 'sci') or not os.path.exists(S + m['dst']): continue
        if m.get('tocdone'): continue
        m['tocdone'] = True; n += 1
        L = [l.lower().replace('ё', 'е') for l in toc_lines(S + m['dst'])]
        if len(L) < 5: continue
        withtoc += 1
        wins = [L[i] + ' ' + (L[i + 1] if i + 1 < len(L) else '') for i in range(len(L))]
        q = list(m.get('q') or []); q0 = m.get('q0') or list(q); m['q0'] = q0
        for t in tt:
            ks = tk[t['id']]
            if not ks or t['id'] in q: continue
            need = len(ks) if len(ks) <= 2 else max(2, (len(ks) * 3 + 4) // 5)
            if len(ks) == 1 and len(ks[0]) < 6: continue
            if any(sum(1 for k in ks if k in w) >= need for w in wins): q.append(t['id']); added += 1
        m['q'] = q; m['toc'] = True
    json.dump(man, open(MP, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(code, 'изданий просмотрено:', n, 'с оглавлением:', withtoc, 'добавлено привязок:', added)
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in DISC] or list(DISC): run(code)
