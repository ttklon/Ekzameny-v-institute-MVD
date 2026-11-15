# -*- coding: utf-8 -*-
"""Описание скачанных изданий библиотеки: .work/d5/<код>/lib/<номер>.pdf -> books_<код>.json.
Описание берётся с первых страниц PDF (bib.py) и сверяется с названием каталога библиотеки; запускать: /tmp/venv/bin/python books5.py [коды]."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
import bib, fitz
from sel_art import keys, stem
os.chdir(ROOT)
fitz.TOOLS.mupdf_display_errors(False)
GEN = {'upp': r'^(уголовн(ый|о-процессуальное) (процесс|право)|уголовно-процессуальное право|уголовный процесс)( российской федерации| россии| \(уголовный процесс\))?(\. (общая|особенная) часть)?(\. часть \d)?$|основы уголовного процесса',
       'up': r'^уголовное право( российской федерации| россии)?(\. (общая|особенная) часть)?(\. часть \d)?$|основы уголовного права|^(общая|особенная) часть уголовного права',
       'gpp': r'^граждански[йо] (процесс|процессуальное право)( российской федерации| россии)?$|^гражданское процессуальное право',
       'tp': r'^трудовое право( российской федерации| россии)?$',
       'tsp': r'^тактико-специальная подготовка( сотрудников (органов внутренних дел|полиции))?$|^тактико-специальная подготовка'}
def prefixes(short):
    """Сокращённое название каталога («Уг.проц.компетенция») -> начала слов."""
    return [w.lower().replace('ё', 'е')[:4] for w in re.findall(r'[А-Яа-яЁё]{3,}', short) if w.lower() not in ('для', 'при', 'учеб', 'пособ', 'пособие', 'часть', 'ред', 'под')]
def agree(short, title):
    ps = prefixes(short)
    if not ps: return None
    t = title.lower().replace('ё', 'е')
    ws = re.findall(r'[а-я]+', t)
    hit = sum(1 for p in ps if any(w.startswith(p[:3]) for w in ws))
    return hit / len(ps)
def run(code):
    L = json.load(open(D5 + 'lib_%s_list.json' % code, encoding='utf-8'))
    P = D5 + 'books_%s.json' % code
    old = {b['n']: b for b in (json.load(open(P, encoding='utf-8')) if os.path.exists(P) else [])}
    tt = topics(code); tk = {t['id']: keys(code, t['text']) for t in tt}
    out = []; st = {'запись': 0, 'титул': 0, 'каталог': 0, 'нет файла': 0, 'не pdf': 0}
    for o in L:
        p = '.work/d5/%s/lib/%s.pdf' % (code, o['n'])
        if o['n'] in old and old[o['n']].get('done'): out.append(old[o['n']]); continue
        if not os.path.exists(p): st['нет файла'] += 1; continue
        b = dict(n=o['n'], url=o['url'], lib=o['rel'], lyear=o['year'], short=o['short'], size=os.path.getsize(p), done=True)
        try:
            text, pages = bib.first_pages(p, 6)
        except Exception as e:
            b.update(bad='не открывается: %s' % str(e)[:60]); out.append(b); st['не pdf'] += 1; continue
        b['pages'] = pages; b['textlayer'] = len(text.strip()) > 300
        d = None
        try: d = bib.describe(text)
        except Exception: d = None
        how = d and d.get('how')
        ok = bool(d) and not bib.suspicious(d)
        if ok and o['short']:
            a = agree(o['short'], d['title'])
            if a is not None and a < 0.34: ok = False
        if ok and o['year'] and d.get('year') and abs(int(d['year']) - o['year']) > 1: ok = False
        if not ok:
            try: d2 = bib.title_page(p)
            except Exception: d2 = None
            if d2 and not bib.suspicious(d2) and (not o['short'] or (agree(o['short'], d2['title']) or 0) >= 0.5): d = d2; ok = True
        if ok:
            b.update(title=d['title'], kind=d.get('kind') or '', authors=d.get('authors') or '', pub=d.get('pub') or '', year=int(d.get('year') or o['year'] or 0), how=d['how'])
            st['запись' if d['how'].startswith('запись') else 'титул'] += 1
        else:
            base = os.path.splitext(os.path.basename(o['rel']))[0]
            name = o['short'] or re.sub(r'^\d{4}\s*', '', base)
            if len(base) > len(name) + 8 and not re.match(r'^[\dA-Za-zЭР_.\- ]+$', base): name = re.sub(r'^\d{4}\s*', '', base)
            yr = o['year'] or 0
            if not yr:
                ys = [int(y) for y in re.findall(r'(?<!\d)(20[012]\d)(?!\d)', text[:3000]) if int(y) <= 2026]
                yr = max(ys) if ys else 0
            b.update(title=' '.join(name.replace('_', ' ').split()), kind='', authors='', pub='', year=yr, how='каталог'); st['каталог'] += 1
        # вопросы: по названию и по тексту первых страниц (аннотация, оглавление)
        tl = (b['title'] + ' ' + b.get('short', '')).lower().replace('ё', 'е'); xl = ' '.join(text.lower().replace('ё', 'е').split())
        q = []
        for t in tt:
            ks = tk[t['id']]
            if not ks: continue
            ht = sum(1 for k in ks if k in tl)
            if ht >= (1 if len(ks) <= 2 else 2) and ht * 2 >= len(ks): q.append(t['id'])
            elif len(ks) >= 3 and ht >= 1 and sum(1 for k in ks if k in xl) >= max(3, (len(ks) * 3 + 3) // 4): q.append(t['id'])
        b['q'] = q
        b['general'] = bool(re.search(GEN[code], ' '.join(b['title'].lower().replace('ё', 'е').split()).strip(' .')))
        out.append(b)
    json.dump(out, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(code, 'описано:', len(out), st, 'без вопросов и не общие:', sum(1 for b in out if not b.get('q') and not b.get('general') and not b.get('bad')))
    return out
if __name__ == '__main__':
    for code in [a for a in sys.argv[1:] if a in DISC] or list(DISC):
        out = run(code)
        if '--show' in sys.argv:
            for b in out: print(b['n'], b.get('how'), '|', b.get('authors'), '|', (b.get('title') or '')[:70], '|', b.get('kind'), '|', b.get('pub'), b.get('year'), '| кат:', b['short'][:30], '| q', len(b.get('q', [])), 'G' if b.get('general') else '')
