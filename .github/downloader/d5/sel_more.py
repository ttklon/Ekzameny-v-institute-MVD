# -*- coding: utf-8 -*-
"""Добор статей (вторая очередь) -> cyber_<код>_selected.json.
1. По прежним результатам поиска (cyber_<код>.tsv) на вопрос берётся до KMORE статей вместо 2–3;
   сверх уже размещённых добавляются только статьи из журналов с отметкой ВАК.
2. Вопросы, у которых автоматический отбор не дал ничего (в формулировке нет отличительных слов), —
   по признаку в названии статьи, заданному вручную (MAN); источники — cyber_<код>.tsv и cyber_x3.tsv (доп. поиск)."""
import os, re, sys, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
import sel_art
os.chdir(ROOT)
KMORE = {'upp': 5, 'up': 5, 'gpp': 6, 'tp': 6}
PRE = {'upp': 'p', 'up': 'u', 'gpp': 'g', 'tp': 't', 'tsp': 's'}
MAN = {
 'upp001': r'уголовн\w+ (процесс|судопроизводств)\w*: понятие и назначение|назначени\w+ уголовн\w+ (процесс|судопроизводств)|задач\w* уголовн\w+ (процесс|судопроизводств)|цел\w+ уголовн\w+ (процесс|судопроизводств)',
 'upp069': r'стади\w+ уголовн\w+ (процесс|судопроизводств)|систем\w+ стадий|досудебн\w+ стади|судебн\w+ стади',
 'upp128': r'ходатайств',
 'upp130': r'процессуальн\w+ срок|исчислени\w+ срок|срок\w* в уголовн\w+ (процесс|судопроизводств)|разумн\w+ срок',
 'up001': r'(предмет\w*|метод\w*|систем\w+) уголовн\w+ прав|понятие уголовн\w+ прав|уголовн\w+ прав\w+ как отрасл',
 'up008': r'(поняти\w+|признак\w+|сущност\w+) преступлени|общественн\w+ опасност\w+ (как|деяни|преступлен)|малозначительн',
 'up065': r'краж',
 'gpp003': r'принцип\w* гражданск\w+ (процесс|судопроизводств)|принцип\w* (гласност|состязательност|диспозитивност|доступност|добросовестност|непосредственност|процессуальн\w+ экономи)',
 'gpp013': r'соучасти|правопреемств',
 'tp002': r'наемн\w+ труд|несамостоятельн\w+ труд|зависим\w+ труд',
 'tp025': r'увольнени\w+ .*(дисциплинарн|прогул|виновн|утрат\w+ довери)|(прогул|утрат\w+ довери|виновн\w+ действ)|дисциплинарн\w+ увольнени|увольнение работника как вид дисциплинарн',
 'tp038': r'отпуск\w* без сохранени|регулирования отпусков',
}
def rows_of(path):
    if not os.path.exists(path): return []
    return [r for r in (l.rstrip('\n').split('\t') for l in open(path, encoding='utf-8')) if len(r) >= 8 and r[1] != 'ОШИБКА']
def run(code):
    man = {m['key'] for m in json.load(open(D5 + 'manifest_%s.json' % code, encoding='utf-8'))}
    sel = sel_art.run(code, KMORE[code])
    sel = [c for c in sel if c['n'] in man or c['vak']]
    have = {c['slug'] for c in sel}; add = 0
    for tid, rx in MAN.items():
        if not tid.startswith(code) or tid[len(code)].isalpha(): continue
        cand = []
        for r in rows_of(D5 + 'cyber_%s.tsv' % code) + rows_of(D5 + 'cyber_x3.tsv'):
            t, year, vak, journal, authors, title, link, abstr = r[:8]
            if t != tid or not link or link in have or not authors.strip(): continue
            if sel_art.BAD.search(title) or sel_art.BAD.search(journal) or re.search(sel_art.NEG[code], title, re.I): continue
            if not re.search(rx, title.lower().replace('ё', 'е')): continue
            score = (1 if vak else 0) + {'2026': 0.5, '2025': 0.4, '2024': 0.2}.get(year, 0)
            cand.append((score, link, dict(slug=link, year=year, vak=bool(vak), journal=journal, authors=authors, title=title, t=[tid], manual=True)))
        for score, link, c in sorted(cand, key=lambda x: (-x[0], x[1]))[:5]:
            if link in have: continue
            c['n'] = PRE[code] + hashlib.sha1(link.encode('utf-8')).hexdigest()[:6]; sel.append(c); have.add(link); add += 1
    json.dump(sel, open(D5 + 'cyber_%s_selected.json' % code, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    cov = collections.Counter(t for c in sel for t in c['t']); tt = topics(code)
    print('  ', code, 'итого:', len(sel), 'из них новых:', sum(1 for c in sel if c['n'] not in man), 'по ручному признаку:', add,
          '| вопросов без статей:', ' '.join(t['refs'][0] for t in tt if not cov[t['id']]) or '—', '| с 1–2:', sum(1 for t in tt if 0 < cov[t['id']] < 3))
    if '--show' in sys.argv:
        for c in sel:
            if c.get('manual'): print('     ', c['t'][0], c['year'], 'ВАК' if c['vak'] else '   ', c['title'][:110])
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in KMORE] or list(KMORE): run(code)
