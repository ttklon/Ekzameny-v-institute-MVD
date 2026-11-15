# -*- coding: utf-8 -*-
"""Вторая волна заданий: загрузка отобранных изданий библиотеки и статей (по дисциплинам, параллельными списками)."""
import os, sys, json, glob, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5
os.chdir(ROOT)
SH = '.github/downloader/shards/'
for f in glob.glob(SH + '*.tsv'): os.remove(f)
def write(name, rows):
    with open(SH + name + '.tsv', 'w', encoding='utf-8') as f:
        for r in rows: f.write('\t'.join(r) + '\n')
    print(name, len(rows))
for code in DISC:
    p = D5 + 'lib_%s_list.json' % code
    if os.path.exists(p):
        L = json.load(open(p, encoding='utf-8'))
        rows = [('get', urllib.parse.quote(o['url'], safe=':/'), '.work/d5/%s/lib/%s.pdf' % (code, o['n'])) for o in L if not os.path.exists('.work/d5/%s/lib/%s.pdf' % (code, o['n']))]
        if rows: write('lib_' + code, rows)
    p = D5 + 'cyber_%s_selected.json' % code
    if os.path.exists(p):
        S = json.load(open(p, encoding='utf-8'))
        rows = [('get', 'https://cyberleninka.ru%s/pdf' % c['slug'], '.work/d5/%s/art/%s.pdf' % (code, c['n'])) for c in S if not os.path.exists('.work/d5/%s/art/%s.pdf' % (code, c['n']))]
        k = max(1, (len(rows) + 179) // 180)
        for i in range(k): write('art_%s%s' % (code, '' if k == 1 else '_%d' % (i + 1)), rows[i::k])
# --- дополнительно: статистика Судебного департамента, акты взамен утративших силу, тематический поиск статей для ТСП
C = 'https://cdep.ru/userimages/'
ST = [('Statistika_2023/F3-svod-vse_sudy-2023.xls', 'f3_2023'), ('Statistika_2024/F3-svod_vse_sudy-2024.xls', 'f3_2024'), ('Statistika_2025_all/F3-svod_vse_sudy-2025.xls', 'f3_2025'),
      ('Statistika_2025_all/F6-svod_vse_sudy-2025.xls', 'f6_2025'), ('Statistika_2025_all/F7-svod_vse_sudy-2025.xls', 'f7_2025'), ('Statistika_2025_all/F8-svod_vse_sudy-2025.xls', 'f8_2025'),
      ('Statistika_2025_all/F9-svod_vse_sudy-2025.xls', 'f9_2025'), ('Statistika_2025_all/F11-8n-svod-2025.xls', 'f8n_2025'), ('Statistika_2025_all/F10-9n-svod-2025.xls', 'f9n_2025'),
      ('Statistika_2024/k3-svod_vse_sudy-2024.xls', 'k3_2024'), ('Statistika_2024/k4-svod_vse_sudy-2024.xls', 'k4_2024'), ('Statistika_2024/k5.2-svod_vse_sudy-2024.xls', 'k52_2024'),
      ('Statistika_2024/k1-svod_vse_sudy-2024.xls', 'k1_2024'), ('Statistika_2024/k6-svod_vse_sudy-2024.xls', 'k6_2024')]
import urllib.parse as _u
def ips(req): return 'http://ips.pravo.gov.ru/api/ips/legislation/search.json?query=%s&limit=10&page=1#%s' % (_u.quote_plus(req), req)
rows = [('get', C + u, '.work/d5/stat/cdep_%s.xls' % n) for u, n in ST]
rows += [('ipsact', ips('Постановление Правительства Российской Федерации от 24.04.2025 № 540'), '.work/d5/acts/p540.pdf'),
         ('ipsact', ips('Указ Президента Российской Федерации от 25.11.2020 № 787'), '.work/d5/acts/u787.pdf'),
         ('consauto', 'Приказ Минздрава России от 08.04.2025 N 172н#от 08.04.2025 N 172н', '.work/d5/cons/mz172n.pdf'),
         ('consauto', 'Указ Президента РФ от 25.11.2020 N 787#от 25.11.2020 N 787', '.work/d5/cons/u787.pdf'),
         ('consauto', 'Постановление Правительства РФ определение степени тяжести вреда, причиненного здоровью человека 2025#степени тяжести вреда', '.work/d5/cons/vred2025.pdf')]
write('extra', rows)
write('cyber_tsp2', [('cybersearch', D5 + 'cyber_q_tsp2.txt#40', D5 + 'cyber_tsp2.tsv')])
