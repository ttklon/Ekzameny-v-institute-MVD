# -*- coding: utf-8 -*-
"""Описания четырёх изданий последнего добора (не из библиотеки lib.eioskuimvd.ru) — по титульным листам и оглавлениям, вручную.
Вопросы привязаны по оглавлению. Запускается после books5.py."""
import os, json
D5 = os.path.dirname(os.path.abspath(__file__)) + '/'
HOW = 'титульный лист и оглавление (описание составлено вручную)'
T = lambda *n: ['tsp%03d' % i for i in n]
P = lambda *n: ['tp%03d' % i for i in n]
FIX = {
 'tsp': {
  'sx000001': dict(title='Общая тактика', authors='Байрамуков, Янович, Гончарик и др.', kind='учебник (2-е изд.), ред. Торгованов', pub='СФУ', year=2017,
                   q=T(*range(94, 104)), general=False, off=False, how=HOW, lib='сайт Военно-инженерного института СФУ (vii.sfu-kras.ru)'),
  'sx000002': dict(title='Военная топография', authors='Евдокимов', kind='пособие для практических занятий', pub='ГУАП', year=2008,
                   q=T(20, 23, 42, 45, 46, 48, 62, 63, 64, 65, 67, 69, 70, 73, 74, 75, 76, 77, 78), general=False, off=False, how=HOW, lib='сайт ГУАП (fs.guap.ru)'),
  # файл на сайте подписан как издание 2018 года; на титульном листе и в записи на обороте — 2014 год
  'sx000003': dict(title='Тактическая подготовка курсантов учебных военных центров', authors='Торгованов, Байрамуков, Янович и др.', kind='учебник', pub='СФУ', year=2014,
                   q=T(20, 23, 25, 42, 45, 46, 48, *range(61, 79), *range(81, 86), *range(87, 104)), general=False, off=False, how=HOW, lib='сайт Военно-инженерного института СФУ (vii.sfu-kras.ru)'),
  'sx000004': dict(title='Радиационная, химическая и биологическая защита', authors='Байрамуков, Анакин и др.', kind='учебник, ред. Торгованов', pub='СФУ', year=2015,
                   q=T(*range(81, 86), *range(87, 94)), general=False, off=False, how=HOW, lib='сайт Военно-инженерного института СФУ (vii.sfu-kras.ru)'),
  'sx000005': dict(title='Общая тактика. Управление подразделениями в бою', authors='Драбатулин, Байрамуков', kind='учебное пособие', pub='СФУ', year=2011,
                   q=T(97, 102), general=False, off=False, how=HOW, lib='сайт Военно-инженерного института СФУ (vii.sfu-kras.ru)'),
 },
 'tp': {
  'tx000001': dict(title='Трудовое право', authors='Минкина', kind='учебное пособие (2-е изд.; планы занятий, задачи, тесты)', pub='Алтайский филиал РАНХиГС', year=2025,
                   q=[], general=True, off=False, how=HOW, lib='сайт Алтайского филиала РАНХиГС (alt.ranepa.ru)'),
  'tx000002': dict(title='Сроки в трудовом праве', authors='Демидо, Присекин', kind='учебное пособие', pub='ДВЮИ (филиал) Университета прокуратуры РФ', year=2023,
                   q=P(18, 20, 21, 24, 25, 45, 51, 52, 67), general=False, off=False, how=HOW, lib='сайт Университета прокуратуры РФ (agprf.org)'),
 },
}
for code, fx in FIX.items():
    p = D5 + 'books_%s.json' % code
    B = json.load(open(p, encoding='utf-8')); n = 0
    for b in B:
        if b['n'] in fx: b.update(fx[b['n']]); n += 1
    json.dump(B, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(code, 'исправлено:', n)
