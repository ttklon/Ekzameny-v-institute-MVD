# -*- coding: utf-8 -*-
"""ТСП: отбор статей по тематическим разделам (cyber_tsp2.tsv) -> cyber_tsp2_selected.json.
Вопросы ТСП узкие (боевые порядки групп, топография), статей по ним мало, поэтому статья привязывается к разделу:
если в названии есть ключевые слова конкретного вопроса — к нему, иначе ко всем вопросам раздела."""
import os, re, sys, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, D5, topics
from sel_art import keys, BAD
os.chdir(ROOT)
G = {  # раздел: (что должно быть в названии статьи, какие вопросы относятся к разделу, название)
 'zal': (r'заложник', r'заложник', 'освобождение заложников'),
 'spec': (r'специальн\w+ операци|оперативн\w+ штаб|чрезвычайн\w+ обстоятельств|особых условиях', r'специальн\w+ операци|спецопераци|оперативн\w+ штаб|оценк\w+ обстановк|боево\w+ приказ|расчет\w+ времени', 'специальная операция, управление'),
 'mb': (r'массов\w+ беспоряд', r'массов\w+ беспоряд', 'пресечение массовых беспорядков'),
 'mm': (r'массов\w+ мероприят|публичн\w+ мероприят|спортивн\w+ мероприят|массовых (спортивн|публичн|культурн)', r'массов\w+ мероприят', 'массовые мероприятия'),
 'poisk': (r'вооруженн\w+ преступник|задержани|личн\w+ безопасност', r'поиск|писку|задержан|преследован|заслон|засад|розыскн|блокирован|оцеплен|помещени|вооруженн', 'поиск и задержание вооружённых преступников'),
 'topo': (r'топограф|ориентирован\w+ на местност', r'координат|компас|местност|азимут|дирекцион|топограф|карт|рельеф|условных знаков', 'топографическая подготовка'),
 'go': (r'чрезвычайн\w+ ситуаци|гражданск\w+ оборон|радиацион|химическ|эвакуац', r'чрезвычайн\w+ ситуаци|массового поражения|ядерн|коллективн\w+ защит|эвакуац|специальн\w+ обработк|дезактив|ДП|ВПХР|ОЗК|противогаз', 'чрезвычайные ситуации, защита'),
 'boy': (r'тактико-специальн|тактическ\w+ подготовк|служебно-боев', r'^$', 'общевойсковая тактика, тактико-специальная подготовка'),
 'ovd': (r'нападен', r'нападени', 'нападение на объекты ОВД'),
 'pps': (r'патрульно-постов|нарядов|наряды', r'патрульно-постов|проверки документов|нарядов', 'наряды, патрульно-постовая служба'),
}
CTXR = re.compile(r'внутренних дел|полици|мвд|овд|росгвард|правоохран|курсант|силов', re.I)
NO = re.compile(r'квалификац|уголовно-правов\w+ (характеристик|анализ)|состав\w* преступлен|уголовн\w+ (процесс|судопроизводств)|расследован|наказани|физическ\w+ подготовк|огнев\w+ подготовк', re.I)
tt = topics('tsp'); tk = {t['id']: keys('tsp', t['text']) for t in tt}
have = {c['slug'] for c in json.load(open(D5 + 'cyber_tsp_selected.json', encoding='utf-8'))}
cand = collections.defaultdict(list); seen = set()
for l in open(D5 + 'cyber_tsp2.tsv', encoding='utf-8'):
    r = l.rstrip('\n').split('\t')
    if len(r) < 8 or r[1] == 'ОШИБКА': continue
    g, year, vak, journal, authors, title, link, abstr = r[:8]
    if not link or link in have or link in seen or not authors.strip() or BAD.search(title) or BAD.search(journal) or NO.search(title): continue
    if not re.search(G[g][0], title, re.I): continue
    if g not in ('topo',) and not CTXR.search(title + ' ' + abstr + ' ' + journal): continue
    seen.add(link)
    score = (1 if vak else 0) + {'2026': 0.6, '2025': 0.5, '2024': 0.3}.get(year, 0) + (0.7 if CTXR.search(title) else 0)
    cand[g].append((score, link, dict(slug=link, year=year, vak=bool(vak), journal=journal, authors=authors, title=title, group=g)))
sel = []
for g, L in cand.items():
    gt = [t for t in tt if re.search(G[g][1], t['text'], re.I)]
    for score, link, c in sorted(L, key=lambda x: (-x[0], x[1]))[:14]:
        tl = c['title'].lower().replace('ё', 'е')
        hit = [t['id'] for t in gt if tk[t['id']] and sum(1 for k in tk[t['id']] if k in tl) >= (1 if len(tk[t['id']]) <= 2 else 2)]
        c['t'] = hit or [t['id'] for t in gt]; c['wide'] = not hit; c['general'] = not c['t']
        c['n'] = 's' + hashlib.sha1(link.encode('utf-8')).hexdigest()[:6]; sel.append(c)
json.dump(sel, open(D5 + 'cyber_tsp2_selected.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
cov = collections.Counter(t for c in sel for t in c['t']) + collections.Counter(t for c in json.load(open(D5 + 'cyber_tsp_selected.json', encoding='utf-8')) for t in c['t'])
print('статей:', len(sel), 'ВАК:', sum(c['vak'] for c in sel), dict(collections.Counter(c['group'] for c in sel)), '| вопросов без статей:', ' '.join(t['refs'][0] for t in tt if not cov[t['id']]))
if '--show' in sys.argv:
    for c in sel: print(c['group'], c['year'], '|', c['title'][:110])
