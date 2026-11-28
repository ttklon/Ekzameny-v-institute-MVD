# -*- coding: utf-8 -*-
"""Этапы 4 и 5 для дисциплин «Деятельность Госавтоинспекции» (G) и «Обеспечение собственной безопасности ОВД» (S):
научные издания библиотеки, статьи cyberleninka.ru 2023 года и новее, эмпирические материалы.
Команды: select — отбор статей по результатам поиска (cyber_g.tsv, cyber_s.tsv) и задания на загрузку;
         place — описание и раскладка загруженного; registry — реестр, списки по разделам, контрольные суммы."""
import os, re, sys, json, hashlib, collections, urllib.parse as U
HERE = os.path.dirname(os.path.abspath(__file__)); DL = os.path.dirname(HERE); ROOT = os.path.dirname(os.path.dirname(DL))
DISC = {'g': 'Деятельность Госавтоинспекции', 's': 'Обеспечение собственной безопасности органов внутренних дел'}
D4 = '2. Источники/4. Научные материалы (с 2023 года)'; D4A = D4 + '/Статьи'; D5 = '2. Источники/5. Эмпирические материалы (с 2023 года)'; D3 = '2. Источники/3. Учебная литература'
TODAY = '28.11.2026'
STOP = set('''понятие понятия виды вид признаки признак значение система системы общая общие характеристика порядок основания основание его ее их как
для при или также данного данное состав особенности особенность содержание сущность формы форма классификация структура роль цель цели задачи задача
иных иные другие российской федерации россии российского права право правовое правовой правовые правового вопросы вопрос проблемы проблем
элементы элемент условия условие соотношение основные основных методы метод принципы принцип современные действий действия способы способ определение
области сфере лицом лица лиц отношении отношение статья статьи кодекса кодекс деятельности деятельность органов органы органах внутренних осуществления
средств средства средством сотрудников сотрудниками сотрудника сотрудник сотрудники делам делах дела'''.split())
CTX = {'g': r'дорожн|транспортн|водител|госавтоинспекц|гибдд|автомобил|\bдтп\b|пешеход|самокат|мобильност|автотранспорт|автошкол|\bдпс\b',
       's': r'внутренних дел|полици|сотрудник|правоохранительн|\bмвд\b|должностн|коррупц|взят|служебн|оперативно-ро|оперативно-разыск|государственн\w+ (служ|тайн|защит)|представител\w+ власти|дисциплинарн'}
NEG = {'g': r'железнодорожн\w+ транспорт|воздушн|морск|речн|внутренн\w+ водн|авиаци|трубопровод|космич|метрополитен',
       's': r'\bуис\b|продовольственн|аппарат\w* суда|наркоти|несовершеннолетн|персональных данных работник|экстремизм|патрульно-постов|уголовно-исполнительн|осужденн|исправительн\w+ (учрежден|колони)|банк|налогов|таможен|муниципальн\w+ служ|школьн|студент\w+ вуз'}
BAD = re.compile(r'казахстан|кыргыз|киргиз|узбекистан|беларус|белорус|таджикистан|армени|азербайджан|монголи|вьетнам|китая|китайск|\bкнр\b|зарубежн|иностранн(ых|ого) государств|'
                 r'истори|дореволюц|советск|\bссср\b|\bxix\b|\bxviii\b|xx век|рецензи|юбилей|памяти |обзор конференц|украин|германи|франци|\bсша\b|еаэс|\bснг\b|японии|индии|европейск|'
                 r'японск|американск|германск|французск|британск|зарубежья|сингапур|рельс|шлифован|дошкольн|грузопассажирск|транспортно-технологическ|совместного потребления|арест товаров|днр|лнр|туркмен|молдов|латви|эстони|литв|польш|итали|испани|великобритан|англи|сербии|иран|турци|корея|абхази|осети', re.I)
K = {'g': 6, 's': 6}
LEGAL = r'правов|правонаруш|ответственност|преступлен|полици|госавтоинспекц|гибдд|надзор|законо|административн|уголовн|\bмвд\b|внутренних дел|расследован|квалификац|судебн|служебн|дисциплин|оперативно'
def stem(w):
    w = w.lower().replace('ё', 'е')
    return w[:6] if len(w) > 7 else (w[:5] if len(w) > 5 else w)
def keys(q):
    out = []
    for w in re.findall(r'[а-яёА-ЯЁ]{4,}', q):
        if w.lower().replace('ё', 'е') in STOP: continue
        s = stem(w)
        if s not in out: out.append(s)
    return out
def select():
    for d in 'gs':
        p = os.path.join(HERE, 'cyber_%s.tsv' % d)
        if not os.path.exists(p): print(d, 'нет результатов поиска'); continue
        rows = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')]
        qs = [l.rstrip('\n').split('\t') for l in open(os.path.join(HERE, 'cyber_q_%s.txt' % d), encoding='utf-8') if l.strip()]
        # результаты идут в порядке запросов: строки одного запроса подряд; запрос восстанавливается по метке и порядку
        errs = [r for r in rows if len(r) > 1 and r[1] == 'ОШИБКА']
        cand = collections.defaultdict(list); info = {}; qi = -1; prev = None; rank = 0; seen_in_q = set()
        # поиск не пишет текст запроса, поэтому статья сверяется со всеми запросами своей метки
        byq = collections.defaultdict(list)
        for tag, q in qs: byq[tag].append(q)
        st = collections.Counter()
        pos = collections.Counter(); seen_t = {}
        for r in rows:
            if len(r) < 8 or r[1] == 'ОШИБКА': continue
            tag, year, vak, journal, authors, title, link, abstr = r[:8]
            st['строк'] += 1; pos[tag] += 1
            if not link or not authors.strip(): continue
            if BAD.search(title) or BAD.search(journal): st['иностранное, историческое'] += 1; continue
            if sum(1 for c in title if 'a' <= c.lower() <= 'z') > len(title) * 0.4: continue
            tl = title.lower().replace('ё', 'е'); al = abstr.lower().replace('ё', 'е')
            if re.search(NEG[d], tl): st['другая отрасль'] += 1; continue
            if not (re.search(CTX[d], tl) or len(re.findall(CTX[d], al)) >= 2): st['нет признака дисциплины'] += 1; continue
            if not (re.search(LEGAL, tl) or len(re.findall(LEGAL, al)) >= 2): st['не правовая тема'] += 1; continue
            nt = re.sub(r'[^а-яa-z0-9]+', '', tl)
            if nt in seen_t and seen_t[nt] != link: st['повтор названия'] += 1; continue
            seen_t[nt] = link
            best = None
            for q in byq[tag]:
                ks = keys(q)
                if not ks: continue
                ht = sum(1 for k in ks if k in tl); ha = sum(1 for k in ks if k in al)
                need = 1 if len(ks) <= 2 else 2
                if ht < need and not (ht >= 1 and ha >= max(2, len(ks) // 2)): continue
                score = 3.0 * ht / len(ks) + 1.0 * ha / len(ks) + (0.6 if vak else 0) + {'2026': 0.5, '2025': 0.4, '2024': 0.2}.get(year, 0)
                if best is None or score > best[0]: best = (score, q)
                cand[(tag, q)].append((score, link))
            if best is None: st['мало совпадений с запросом'] += 1; continue
            info[link] = dict(slug=link, year=year, vak=bool(vak), journal=journal, authors=authors, title=title, ann=abstr[:300])
        chosen = collections.OrderedDict()
        for tag, q in qs:
            got = 0
            for score, link in sorted(set(cand[(tag, q)]), reverse=True):
                if got >= K[d]: break
                c = chosen.setdefault(link, dict(info[link], t=[], q=[]))
                if tag not in c['t']: c['t'].append(tag)
                if q not in c['q']: c['q'].append(q)
                got += 1
        sel = []
        for link, c in chosen.items():
            c['n'] = 'a' + d + hashlib.sha1(link.encode('utf-8')).hexdigest()[:6]; sel.append(c)
        json.dump(sel, open(os.path.join(HERE, 'cyber_%s_selected.json' % d), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        cov = collections.Counter(q for c in sel for q in c['q'])
        empty = [q for tag, q in qs if not cov[q]]
        sec = collections.Counter(t for c in sel for t in c['t'])
        print(d.upper(), 'запросов', len(qs), 'ошибок поиска', len(errs), 'строк', st['строк'], dict(st))
        print('  отобрано статей', len(sel), 'ВАК', sum(c['vak'] for c in sel), 'по годам', dict(collections.Counter(c['year'] for c in sel)))
        print('  по разделам', dict(sorted(sec.items())))
        print('  запросы без статей (%d):' % len(empty), '; '.join(empty))
        n = 4; b = [[] for _ in range(n)]
        for i, c in enumerate(sel): b[i % n].append(c)
        for i, x in enumerate(b, 1):
            with open(os.path.join(DL, 'shards', 'r48_art_%s%d.tsv' % (d, i)), 'w', encoding='utf-8') as f:
                for c in x: f.write('get\thttps://cyberleninka.ru%s/pdf\t.work/art/%s.pdf\n' % (c['slug'], c['n']))
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'select': select()
    elif cmd == 'place': import sci_place; sci_place.run()
    elif cmd == 'registry': import sci_place; sci_place.registry()
    else: print(__doc__)
