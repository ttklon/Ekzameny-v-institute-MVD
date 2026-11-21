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
 'obor': (r'общевойсков|оборонительн\w+ бо|наступательн\w+ бо|в оборон|в наступлени|отделени\w+ в бою|опорн\w+ пункт|систем\w+ огня|инженерн\w+ оборудовани', r'оборон|наступ|системы огня|инженерное оборудование|командира отделения', 'общевойсковой бой: оборона и наступление'),
 'graf': (r'графическ\w+ документ|рабоч\w+ карт', r'графическ|рабочей карты', 'боевые графические документы'),
 'boy': (r'тактико-специальн|тактическ\w+ подготовк|служебно-боев', r'^$', 'общевойсковая тактика, тактико-специальная подготовка'),
 'ovd': (r'нападен', r'нападени', 'нападение на объекты ОВД'),
 'pps': (r'патрульно-постов|нарядов|наряды', r'патрульно-постов|проверки документов|нарядов', 'наряды, патрульно-постовая служба'),
}
CTXR = re.compile(r'внутренних дел|полици|мвд|овд|росгвард|правоохран|курсант|силов|войск|военнослужащ', re.I)
NO = re.compile(r'наркотич|19[0-4]\d|отечественн\w+ войн|спортивн\w+ ориентирован|школьник|студент|туризм|истори|ссср|ркка|красной арми|местн\w+ противовоздушн|армени|таджикист|нато|квалификац|уголовно-правов\w+ (характеристик|анализ)|состав\w* преступлен|уголовн\w+ (процесс|судопроизводств)|расследован|наказани|физическ\w+ подготовк|огнев\w+ подготовк', re.I)
tt = topics('tsp'); tk = {t['id']: keys('tsp', t['text']) for t in tt}
have = {c['slug'] for c in json.load(open(D5 + 'cyber_tsp_selected.json', encoding='utf-8'))}
cand = collections.defaultdict(list); seen = set()
PLACED = {m['key'] for m in json.load(open(D5 + 'manifest_tsp.json', encoding='utf-8'))}
# дополнительный поиск (cyber_x3.tsv) даёт много посторонних статей (история войн, геодезия, спорт) — признак в названии строже
X3 = {'topo': r'военн\w+ топограф|ориентирован\w+ на местности|изучени\w+ местност|навыки навигации|топографическ\w+ планов и карт',
      'zal': r'заложник', 'ovd': r'комендантск', 'spec': r'снайперск\w+ групп'}
X3MAP = {'ovd': 'ovd', 'topo': 'topo', 'zal': 'zal'}
NO3 = re.compile(r'19[0-4]\d|18\d\d|отечественн\w+ войн|ссср|истори|строительств|геодез|учащихся|школ|студент|уголовно-правов|квалификац', re.I)
LINES = [(l, False) for l in open(D5 + 'cyber_tsp2.tsv', encoding='utf-8').read().split('\n')]
if os.path.exists(D5 + 'cyber_x3.tsv'): LINES += [(l, True) for l in open(D5 + 'cyber_x3.tsv', encoding='utf-8').read().split('\n')]
for l, extra in LINES:
    r = l.split('\t')
    if r[0] not in G: continue
    if extra:
        if len(r) < 8 or NO3.search(r[5]): continue
        gg = [g for g, rx in X3.items() if re.search(rx, r[5], re.I)]
        if not gg: continue
        r[0] = gg[0]
    if len(r) < 8 or r[1] == 'ОШИБКА': continue
    g, year, vak, journal, authors, title, link, abstr = r[:8]
    if not link or link in have or link in seen or not authors.strip() or BAD.search(title) or BAD.search(journal) or NO.search(title): continue
    if not extra and not re.search(G[g][0], title, re.I): continue
    if not extra and g not in ('topo', 'obor', 'graf') and not CTXR.search(title + ' ' + abstr + ' ' + journal): continue
    seen.add(link)
    score = (1 if vak else 0) + {'2026': 0.6, '2025': 0.5, '2024': 0.3}.get(year, 0) + (0.7 if CTXR.search(title) else 0)
    cand[g].append((score, link, dict(slug=link, year=year, vak=bool(vak), journal=journal, authors=authors, title=title, group=g)))
# статьи, отобранные и размещённые раньше, остаются; новые добавляются сверх них (до 12 на раздел за одну очередь)
OLDP = D5 + 'cyber_tsp2_selected.json'
sel = [c for c in (json.load(open(OLDP, encoding='utf-8')) if os.path.exists(OLDP) else []) if c['n'] in PLACED]
kept = {c['slug'] for c in sel}
for g, L in cand.items():
    gt = [t for t in tt if re.search(G[g][1], t['text'], re.I)]
    for score, link, c in sorted([x for x in L if x[1] not in kept], key=lambda x: (-x[0], x[1]))[:12]:
        tl = c['title'].lower().replace('ё', 'е')
        hit = [t['id'] for t in gt if tk[t['id']] and sum(1 for k in tk[t['id']] if k in tl) >= (1 if len(tk[t['id']]) <= 2 else 2)]
        c['t'] = hit or [t['id'] for t in gt]; c['wide'] = not hit; c['general'] = not c['t']
        c['n'] = 's' + hashlib.sha1(link.encode('utf-8')).hexdigest()[:6]; sel.append(c)
json.dump(sel, open(D5 + 'cyber_tsp2_selected.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
cov = collections.Counter(t for c in sel for t in c['t']) + collections.Counter(t for c in json.load(open(D5 + 'cyber_tsp_selected.json', encoding='utf-8')) for t in c['t'])
print('статей:', len(sel), 'ВАК:', sum(c['vak'] for c in sel), dict(collections.Counter(c['group'] for c in sel)), '| вопросов без статей:', ' '.join(t['refs'][0] for t in tt if not cov[t['id']]))
if '--show' in sys.argv:
    for c in sel:
        if c['n'] not in PLACED: print(c['group'], c['year'], 'ВАК' if c['vak'] else '   ', '|', c['title'][:120], '|', ' '.join(c['t'][:6]))
