# -*- coding: utf-8 -*-
"""Отбор изданий из открытых каталогов электронной библиотеки (lib.eioskuimvd.ru) -> lib_<код>_list.json.
Берутся PDF не крупнее 45 МБ из каталогов дисциплины; год издания — из названия каталога («2024 Название»)."""
import os, re, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5
os.chdir(ROOT)
P = 'Эл. библ. для учебы/'
LISTS = ['.github/downloader/krim/lib_files.tsv', '.github/downloader/lib_top.tsv', '.github/downloader/lib_more.tsv', '.github/downloader/lib_bp.tsv', D5 + 'lib_files.tsv']
E_ = 'Электронные издания ВУЗов МВД России/'; KU = 'Электронная библиотека КЮИ/'; U = 'Электронные учебники ВУЗов МВД России/'; KE = 'Электронные учебные издания КЮИ/'; BP = 'БИБЛИОТЕКА ПОЛИЦЕЙСКОГО/'
CFG = {
 'upp': dict(dirs=[(E_ + 'Уголовно процессуальное право/', 2023), (E_ + 'Уголовный процесс/', 2023), (KU + 'Уголовный процесс/', 2021), (KU + 'Уголовно процессуальное право/', 2021),
                   (U + 'Уголовный процесс/', 2018), (KE + 'Уг.-пр.право/', 2018), (BP + '4. Основы уголовного процесса/', 0), (E_ + 'Дознание/', 2021)],
             bad=r'Расслед|Рассл\.|сыска|топограф|наркот|клевет|Адвокат в ОРД|програм\.обеспеч|Угл\.-исп|Методика|Преступ\.посяг|Соц-прав|опер\.подразд|профилакт|Проф\.раб|Межкафедр|иностр'),
 'up': dict(dirs=[(E_ + 'Уголовное право/', 2021), (KU + 'Уголовное право/', 2020), (U + 'Уголовное право/', 2018), (BP + '3. Основы уголовного права/', 0)],
            bad=r'иностр|зарубеж|Криминолог|Расслед|Рассл\.'),
 'gpp': dict(dirs=[(E_ + 'Гражданский процесс/', 2017), (KU + 'Гражданский процесс/', 2017)], bad=r'зарубеж'),
 'tp': dict(dirs=[(E_ + 'Трудовое право/', 2017), (KU + 'Трудовое право/', 2017)], bad=r'зарубеж'),
 'tsp': dict(dirs=[(E_ + 'Тактико-специальная подготовка/', 2015), (KU + 'Тактико-специальная подготовка/', 2013), (U + 'Тактико-специальная подготовка/', 2013),
                   (KE + 'Тактико-специальная подготовка/', 2013), (BP + '17. Тактико-специальная подготовка/', 0), (E_ + 'Личная безопасность/', 2016), (KU + 'Личная безопасность/', 2014),
                   (E_ + 'Проф. подготовка полицейских/', 2018), (E_ + 'Противодействие терроризму/', 2018)], bad=r'Огнев|Физич|англ'),
}
def size(s):
    m = re.match(r'([\d.]+)([KMG]?)', s or '')
    return int(float(m.group(1)) * {'': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3}[m.group(2)]) if m else 0
rows = {}
for f in LISTS:
    if not os.path.exists(f): continue
    for l in open(f, encoding='utf-8'):
        r = l.rstrip('\n').split('\t')
        if len(r) >= 2 and r[1] not in ('каталог', 'ОШИБКА') and P in r[0]: rows[r[0]] = r
def run(code, show=False):
    cfg = CFG[code]; out = []; seen = set(); stat = collections.Counter()
    for url, r in sorted(rows.items()):
        rel = url.split(P)[1]
        hit = [(d, y) for d, y in cfg['dirs'] if rel.startswith(d)]
        if not hit: continue
        d, miny = hit[0]; stat['всего'] += 1
        if not rel.lower().endswith('.pdf'): stat['не pdf'] += 1; continue
        sub = rel[len(d):].split('/')
        dname = sub[0] if len(sub) > 1 else ''
        m = re.match(r'\s*(?:0+\s+)?((?:19|20)\d\d)\s*(.*)', dname)
        year = int(m.group(1)) if m else 0
        if miny and year < miny: stat['старые'] += 1; continue
        if re.search(cfg['bad'], rel[len(d):], re.I): stat['не по теме'] += 1; continue
        sz = size(r[1])
        if sz > 45 * 1024 ** 2: stat['крупнее 45 МБ'] += 1; continue
        k = (os.path.basename(rel).lower(), r[1])
        if k in seen: stat['повтор'] += 1; continue
        seen.add(k)
        out.append(dict(url=url, rel=rel, year=year, short=(m.group(2) if m else dname).strip(), size=sz))
    L = {'upp': 'pb', 'up': 'ub', 'gpp': 'gb', 'tp': 'tb', 'tsp': 'sb'}[code]
    import hashlib
    for o in out: o['n'] = L + hashlib.sha1(o['url'].encode('utf-8')).hexdigest()[:6]  # номер не зависит от состава списка
    json.dump(out, open(D5 + 'lib_%s_list.json' % code, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(code, 'отобрано:', len(out), 'МБ: %.0f' % (sum(o['size'] for o in out) / 1024 ** 2), dict(stat), 'по годам:', dict(sorted(collections.Counter(o['year'] for o in out).items())))
    if show:
        for o in out: print(o['n'], o['year'], '|', o['short'][:50], '|', os.path.basename(o['rel'])[:40], o['size'] // 1024)
    return out
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in CFG] or list(CFG): run(code, '--show' in sys.argv)
