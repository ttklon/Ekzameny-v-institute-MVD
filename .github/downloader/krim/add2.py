# -*- coding: utf-8 -*-
"""Криминалистика, вторая раскладка: издания из дополнительных каталогов библиотеки (lib2–lib4) и статьи (cyber3, cyber4).
Повторный запуск безопасен: записи, уже внесённые в manifest.json, пропускаются. Запуск: /tmp/venv/bin/python add2.py [--do]"""
import os, re, sys, json, subprocess, urllib.parse
sys.dont_write_bytecode = True
ROOT = '/home/user/Ekzameny-v-institute-MVD'; os.chdir(ROOT)
K = '.github/downloader/krim/'; sys.path.insert(0, K)
import fitz, topics
S = 'Криминалистика/2. Источники/'
D3 = S + '3. Учебная литература/'; D4 = S + '4. Научные материалы (с 2023 года)/'; D4A = D4 + 'Статьи/'
DO = '--do' in sys.argv
src1 = open(K + 'sort1.py', encoding='utf-8').read()
def grab(a, b): i = src1.index(a); return src1[i:src1.index(b, i)]
exec(grab('def clean(s):', '# ---------- книги'))
exec(grab('TQ = {', 'QFIX = {'))
exec(grab('PATR = re.compile', 'DROP_A = '))
WORD = ('осмотр', 'задерж', 'допрос', 'опозн', 'обыск')
man = json.load(open(K + 'manifest.json', encoding='utf-8')); have = {m['key'] for m in man}
used = {m['name'].lower() for m in man}
# номер: (папка, авторы, название, вид, издатель, год, раздел, вопросы | None — по подсчёту тем, общий курс)
B = {
 'e000': ('lib2', 'Тучков, Ковалев', 'Актуальные проблемы проведения отдельных следственных действий', 'учебное пособие', 'ВИПК МВД', '2020', 3, None, False),
 'e003': ('lib2', 'Каргополов, Урусов', 'Формирование запаховых следов человека. Основы трасологии', 'учебно-методическое пособие', 'РШ СРС МВД', '2021', 3, [9], False),
 'h000': ('lib3', 'Гарипов', 'Получение информации о соединениях между абонентами, контроль и запись переговоров, осмотр и выемка электронных сообщений в уголовном процессе', 'учебное пособие', 'КЮИ МВД', '2021', 3, [11, 41, 42, 43, 44], False),
 'h001': ('lib3', 'Кузнецов', 'Уголовно-процессуальные аспекты применения гипнорепродукции в ходе расследования преступлений', 'учебное пособие', 'КЮИ МВД', '2022', 3, [4, 20], False),
 'h003': ('lib3', 'Амиров', 'Тактика следственного осмотра в деятельности дознавателя органов внутренних дел Российской Федерации', 'учебное пособие', 'КЮИ МВД', '2024', 3, [6, 7, 8, 10, 11, 12], False),
 'h004': ('lib3', 'Кузнецов, Гарипов', 'Задержание в уголовном процессе', 'учебное наглядное пособие', 'КЮИ МВД', '2025', 3, [13, 14], False),
 'h007': ('lib3', 'Бугера, Васильев', 'Особенности допросов лиц по уголовным делам, возбужденным по фактам умышленного причинения тяжкого вреда здоровью', 'учебно-практическое пособие', 'ВА МВД', '2025', 3, [15, 17, 18, 20, 22], False),
 'h008': ('lib3', 'Ермаков и др.', 'Справочник следователя по устройству и алгоритму осмотра объектов информационной среды', 'учебно-практическое пособие', 'МосУ МВД', '2025', 3, [10, 11], False),
 'h009': ('lib3', 'сост. Васильев и др.', 'Процессуальные документы предварительного следствия', 'учебно-практическое пособие', 'ВА МВД', '2026', 3, [10, 14, 22, 27, 33, 40, 44], False),
 'h010': ('lib3', '', 'Проблемы предварительного следствия и дознания. Выпуск 34', 'сборник научных трудов', 'ВНИИ МВД', '2025', 4, None, True),
 'h011': ('lib3', '', 'Проблемы и перспективы развития предварительного следствия в России', 'сборник научных трудов', 'ВА МВД', '2025', 4, None, True),
 'h012': ('lib3', '', 'Предварительное расследование в XXI веке: традиции, новации и практика', 'сборник научных трудов', 'ВА МВД', '2026', 4, None, True),
 'h013': ('lib3', 'Акиев, Сотников', 'Тактика следственного осмотра и исследования цифровой информации средств телекоммуникации и интернета', 'учебно-практическое пособие', 'СПбУ МВД', '2023', 3, [10, 11], False),
 'h014': ('lib3', 'Матюшенко', 'Психологические особенности производства следственных действий', 'учебное наглядное пособие', 'ОмА МВД', '2017', 3, [7, 11, 12, 15, 16, 18, 20, 21, 23, 25, 28, 30, 34, 37], False),
 'h015': ('lib3', 'Насонова и др.', 'Система следственных действий в российском уголовном судопроизводстве', 'учебное пособие', 'ВИ МВД', '2021', 3, None, True),
 'h016': ('lib3', 'Самойлов', 'Особенности осмотра компьютерной техники и электронных документов', 'методические рекомендации', 'УЮИ МВД', '2020', 3, [10, 11], False),
 'h017': ('lib3', 'Реуцкая, Морар', 'Психологические методы получения достоверных показаний от участников уголовного судопроизводства в бесконфликтной ситуации допроса', 'методические рекомендации', 'ВНИИ МВД', '2018', 3, [15, 17, 20], False),
 'h018': ('lib3', 'Яджин', 'Криминалистическая психология для следователей (дознавателей)', 'учебно-практическое пособие', 'ТИПК МВД', '2020', 3, [4, 15, 17, 18, 20, 21], False),
 'h019': ('lib3', 'сост. Терещенко', 'Психологическое сопровождение расследования преступлений, связанных с незаконной миграцией', 'методические рекомендации', 'КрУ МВД', '2020', 3, [15, 18, 28, 29, 30, 32], False),
 'h020': ('lib3', '', 'Юридическая психология', 'учебное пособие', 'Академия управления МВД', '2022', 3, [4, 15, 16, 17, 18, 20], False),
}
DROPB = {
 'e001': ('lib2', 'Организационно-тактические особенности осмотра места ДТП (МосУ МВД, 2021) — повтор: это издание уже есть в базе (Данилкина и др.)'),
 'e002': ('lib2', 'Тактические приемы применения розыскных собак при обследовании различных объектов (Уфимская школа кинологов МВД, 2022) — кинология; о поиске запаховых следов при осмотре в тексте почти ничего'),
 'e004': ('lib2', 'Организационно-тактические особенности расследования отдельных видов преступлений следователями ОВД. Практикум (ТИПК МВД, 2020) — криминалистическая методика, а не тактика следственных действий'),
 'e005': ('lib2', 'Кузнецов Д.В. Выявление и расследование преступлений, связанных с использованием криптовалют (КЮИ МВД, 2022) — криминалистическая методика'),
 'e006': ('lib2', 'Михайлов, Огородников. Тактика и порядок досмотра транспортного средства сотрудниками ДПС (ОмА МВД, 2023) — административный досмотр, не следственное действие'),
 'h002': ('lib3', 'Кузнецов, Литвина. Актуальные проблемы доказывания в уголовном судопроизводстве. Курс лекций (КЮИ МВД, 2023) — уголовный процесс; пригодится для дисциплины «Уголовно-процессуальное право»'),
 'h005': ('lib3', 'Предварительное следствие в органах внутренних дел. Учебно-практическое пособие (КЮИ МВД, 2025) — уголовный процесс; пригодится для дисциплины «Уголовно-процессуальное право»'),
 'h006': ('lib3', 'Шавалеев. Уголовно-правовое противодействие мошенничеству с использованием электронных средств платежа. Монография (КЮИ МВД, 2025) — уголовное право'),
 'h021': ('lib3', 'Деулин, Аникеева. Проведение специальных психофизиологических исследований с применением полиграфа (МосУ МВД, 2021) — кадровые проверки, о допросе нет'),
 'h022': ('lib3', 'Уразаева. Психологические возможности правомерного коммуникативного воздействия на личность гражданина (КЮИ МВД, 2021) — морально-психологическая подготовка, о следственных действиях нет'),
}
# статьи: поправки вопросов после сверки названия с перечнем
QA = {'g002': [26], 'd003': [30], 'd004': [34], 'd005': [37, 38], 'd006': [37, 38], 'd007': [34, 35], 'd009': [29, 30], 'd010': [13, 14], 'g010': [11, 28, 30]}
if os.path.exists(K + 'add2_extra.json'):
    x = json.load(open(K + 'add2_extra.json', encoding='utf-8'))
    for k, v in x.get('B', {}).items(): B[k] = tuple(v)
    for k, v in x.get('DROPB', {}).items(): DROPB[k] = tuple(v)
lst = {}
for f in ('lib2_list.json', 'lib3_list.json', 'lib4_list.json'):
    if os.path.exists(K + f):
        for o in json.load(open(K + f, encoding='utf-8')): lst[o['n']] = o
def bookq(c, pages):
    pg = min(pages, 170); q = []; got = []
    for k, qq in TQ.items():
        thr = 40 if k == 'общ' else (max(25, 0.35 * pg) if k in WORD else max(12, 0.12 * pg))
        if c[k] >= thr: q += qq; got.append(k)
    if 'допрос' in got and c['несов'] >= 15: q.append(21)
    return sorted(set(q))
ops = []; new = []
for n, (d0, au, title, kind, pub, year, cat, qn, general) in sorted(B.items()):
    if 'b' + n in have: continue
    src = '.work/krim/%s/%s.pdf' % (d0, n); assert os.path.exists(src), src
    d = fitz.open(src); c = topics.count(' '.join(p.get_text() for p in d)); pages = len(d)
    q = qn if qn is not None else bookq(c, pages)
    kcap = kind[0].upper() + kind[1:]
    name = uniq(fit(lambda t: '%s%s. %s. %s, %s.pdf' % ((au.rstrip('.') + '. ') if au else '', t, kcap, pub, year), title, cap=127))
    dst = (D3 if cat == 3 else D4) + name
    new.append(dict(key='b' + n, cat=cat, old=False, authors=au, title=title, kind=kind, pub=pub, year=year, pages=pages, size=os.path.getsize(src), qn=q, q=rng(q), general=general,
                    collection=(cat == 4), name=name, dst=dst, type='book', url=urllib.parse.quote(lst[n]['url'], safe=':/'), lib=lst[n]['rel'], topics=c, garbled=False))
    ops.append(('mv', src, dst))
rem = json.load(open(K + 'removed2.json', encoding='utf-8')) if os.path.exists(K + 'removed2.json') else []
remk = {r['key'] for r in rem}
for n, (d0, why) in sorted(DROPB.items()):
    if n in remk: continue
    src = '.work/krim/%s/%s.pdf' % (d0, n)
    rem.append(dict(key=n, why=why, url=urllib.parse.quote(lst[n]['url'], safe=':/')))
    if os.path.exists(src): ops.append(('rm', src, why))
for f, d0 in (('cyber3_selected.json', 'cyber3'), ('cyber4_selected.json', 'cyber4')):
    for c in json.load(open(K + f, encoding='utf-8')):
        n = c['n']
        if n in have: continue
        src = '.work/krim/%s/%s.pdf' % (d0, n); assert os.path.exists(src), src
        d = fitz.open(src); t = ' '.join(' '.join(p.get_text() for p in d).split())
        garbled = sum('а' <= ch <= 'я' for ch in t.lower()) < 0.4 * max(1, len(t))
        au = [author(x) for x in c['authors'].split(';') if x.strip()]
        afull = ', '.join(('%s %s' % a).strip() for a in au)
        ash = au[0][0] + ' и др.' if len(au) >= 3 else ', '.join(a[0] for a in au)
        title = sentence(c['title'])
        jr = clean(c['journal']).replace('Министерства внутренних дел Российской Федерации', 'МВД РФ').replace('Министерства внутренних дел России', 'МВД России')
        if len(jr) > 75: jr = jr.split('. ')[0]
        if len(jr) > 75: jr = cut(jr, 75)
        name = fit(lambda t: '%s. %s. %s, %s.pdf' % (ash.rstrip('.'), t, jr, c['year']), title, cap=127)
        if len(name.encode('utf-8')) > 225 or len(name) > 135:
            jr = cut(jr.split('. ')[0], 45); ash = cut(ash, 40) if len(ash) > 40 else ash
            name = fit(lambda t: '%s. %s. %s, %s.pdf' % (ash.rstrip('.'), t, jr, c['year']), title, cap=127)
        name = uniq(name); q = QA.get(n, [x for x in c['q'] if x])
        new.append(dict(key=n, cat=4, old=False, authors=afull, title=title, kind='статья (журнал из перечня ВАК)' if c['vak'] else 'статья', pub=c['journal'], year=c['year'], pages=len(d),
                        size=os.path.getsize(src), qn=q, q=rng(q), general=False, collection=False, name=name, dst=D4A + name, type='article', url='https://cyberleninka.ru' + c['slug'], garbled=garbled))
        ops.append(('mv', src, D4A + name))
for m in new: print(m['key'], '|', m['q'] or '-', '| общ' if m['general'] else '', '|', len(m['name'].encode()), '|', m['name'])
print('перенос:', sum(o[0] == 'mv' for o in ops), 'удаление:', sum(o[0] == 'rm' for o in ops))
assert all(len(m['name'].encode()) <= 225 for m in new) and all(not os.path.exists(m['dst']) for m in new)
if not DO: sys.exit()
tracked = set(subprocess.run(['git', 'ls-files', '.work/krim'], capture_output=True, text=True).stdout.split('\n'))
for op, a, b in ops:
    if op == 'mv':
        if a in tracked: subprocess.run(['git', 'mv', a, b], check=True)
        else: os.rename(a, b)
    else:
        if a in tracked: subprocess.run(['git', 'rm', '-q', a], check=True)
        else: os.remove(a)
json.dump(man + new, open(K + 'manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
json.dump(rem, open(K + 'removed2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('готово, записей в manifest.json:', len(man) + len(new))
