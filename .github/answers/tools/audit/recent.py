#!/usr/bin/env python3
"""recent.py ФАЙЛ_ВСЕХ_ССЫЛОК ФАЙЛ_АКТА КОД_АКТА [ГОДЫ] [-l]

Нормы, изменённые недавно, и предложения ответов, которые на них ссылаются.
ФАЙЛ_ВСЕХ_ССЫЛОК — вывод «refcheck.py … -a» (все сверенные предложения); ФАЙЛ_АКТА — текст акта из папки
kextract.py; КОД_АКТА — первые знаки имени файла акта, как в заголовках блоков refcheck («fc7900»).
ГОДЫ — через запятую (по умолчанию 2025,2026): берутся отметки «(В редакции … от ДД.ММ.ГГГГ № …)»,
«(Дополнение … )», «(Утратил силу …)» с такими годами. Печатается предложение ответа и отметки об изменении
той части статьи, на которую оно ссылается (если часть не названа — всех частей статьи).
  -l   только перечень изменённых статей и частей, без ответов.
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lawtext as L

def changed(path, years):
    yr = '|'.join(years)
    note = re.compile(r'\((?:В редакции|Дополнение|Утратил[аио]? силу|Статья в редакции|Наименование в редакции|Часть|Пункт|Абзац|Примечани)[^()]*?\)')
    date = re.compile(r'от \d\d\.\d\d\.(?:%s) № ?[\d\w-]+' % yr)
    out = {}
    for art, body in L.articles(path).items():
        ps = L.parts(body)
        units = ps.items() if ps else [('', body)]
        for p, txt in units:
            hits = []
            for m in note.finditer(txt):
                ds = date.findall(m.group(0))
                if ds: hits.append((m.start(), ds))
            if hits: out[(art, p)] = (txt, hits)
        # отметка на всю статью стоит после последней части
        tail = [m for m in note.finditer(body) if m.group(0).startswith(('(Статья в редакции', '(Дополнение статьей'))]
        for m in tail:
            ds = date.findall(m.group(0))
            if ds: out[(art, '*')] = (body, [(m.start(), ds)])
    return out

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    refs, path, code = args[0], args[1], args[2]
    years = args[3].split(',') if len(args) > 3 else ['2025', '2026']
    ch = changed(path, years)
    if '-l' in sys.argv:
        for (a, p) in sorted(ch, key=lambda k: ([float(x) if x.isdigit() else 0 for x in k[0].split('.')], k[1])):
            print('ст.', a, 'ч.', p or '—', '|', '; '.join(sorted({d for _, ds in ch[(a, p)][1] for d in ds})))
        sys.exit()
    blocks = re.split(r'\n\s*\n', open(refs, encoding='utf-8').read())
    n = 0
    for b in blocks:
        m = re.match(r'(\S+)\s+(\S.*?)\s+\[(.*?) ← (\S+)', b)
        if not m or m.group(4) != code: continue
        ref = m.group(3)
        am = re.search(r'ст ([\d.,]+)', ref)
        if not am: continue
        pm = re.search(r'ч ([\d.,]+)', ref)
        pnt = re.search(r'п ([\w.,]+)', ref)
        for art in am.group(1).split(','):
            keys = [k for k in ch if k[0] == art]
            if pm:
                want = pm.group(1).split(',')
                keys = [k for k in keys if k[1] in want or k[1] == '*']
            elif pnt and not pm:
                pass
            if not keys: continue
            n += 1
            sent = b.split('\n')[1].strip() if '\n' in b else ''
            print('%s  [%s]' % (m.group(1), ref))
            print('   ' + sent)
            for k in sorted(keys):
                txt, hits = ch[k]
                marks = '; '.join(sorted({d for _, ds in hits for d in ds}))
                print('      ст. %s ч. %s: %s' % (k[0], k[1] or '—', marks))
            print()
    print('-- предложений со ссылкой на недавно изменённую норму:', n)
