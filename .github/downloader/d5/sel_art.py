# -*- coding: utf-8 -*-
"""Отбор статей по результатам поиска в cyberleninka.ru (cyber_<код>.tsv) -> cyber_<код>_selected.json.
Статья берётся, если в её названии есть ключевые слова темы; на тему — до K статей (ВАК и свежие — в первую очередь)."""
import os, re, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, DISC, D5, topics
os.chdir(ROOT)
STOP = set('''понятие понятия виды вид признаки признак значение система системы общая общие характеристика порядок основания основание его ее их как
для при или также данного данное состав особенности особенность содержание сущность формы форма классификация структура роль цель цели задачи задача
отличие отличия иных иные другие российской федерации россии российского права право правовое правовой правовые правового вопросы вопрос проблемы
элементы элемент условия условие соотношение практическое юридическое общих основные основных методы метод принципы принцип современные
назначение тактика действий действия группы группа боевой способы способ определение'''.split())
CTX = {'upp': 'уголовн процесс судопроизводств', 'up': 'уголовн преступлен', 'gpp': 'гражданск процесс процессуальн', 'tp': 'трудов труда', 'tsp': 'органов внутренних дел полиции специальн'}
BAD = re.compile(r'казахстан|кыргыз|киргиз|узбекистан|беларус|таджикистан|армени|азербайджан|монголи|вьетнам|китая|китайск|кнр|зарубежн|иностранн(ых|ого) государств|'
                 r'истори|дореволюц|советск|xix|xviii|xx век|рецензи|юбилей|памяти |обзор конференц|международн\w+ уголовн\w+ суд|республики (корея|молдова)|украин|германи|франци|сша|еаэс|государств-член|снг', re.I)
NEG = {'up': r'уголовн\w+ (процесс|судопроизводств)|уголовно-процессуальн|криминалистич|оперативно-розыскн|досудебн|судебно(го|м) разбирательств|предварительн\w+ (следстви|расследован)',
       'gpp': r'уголовн|административн\w+ судопроизводств|арбитражн\w+ процесс', 'tp': r'уголовн|осужденн|гражданск\w+ процесс', 'upp': r'гражданск\w+ (процесс|судопроизводств)|арбитражн', 'tsp': r'уголовн\w+ (процесс|судопроизводств)'}
def stem(w):
    w = w.lower().replace('ё', 'е')
    return w[:6] if len(w) > 7 else (w[:5] if len(w) > 5 else w)
def keys(code, text):
    ws = re.findall(r'[а-яёА-ЯЁ]{4,}', re.sub(r'\([^)]*\)', ' ', text))
    ctx = CTX[code].split()
    out = []
    for w in ws:
        wl = w.lower().replace('ё', 'е')
        if wl in STOP or any(wl.startswith(c) for c in ctx): continue
        s = stem(w)
        if s not in out: out.append(s)
    return out
def run(code, K):
    tt = topics(code); tk = {t['id']: keys(code, t['text']) for t in tt}
    rows = [l.rstrip('\n').split('\t') for l in open(D5 + 'cyber_%s.tsv' % code, encoding='utf-8')]
    cand = collections.defaultdict(list); info = {}
    rank = collections.Counter()
    for r in rows:
        if len(r) < 8 or r[1] == 'ОШИБКА': continue
        tid, year, vak, journal, authors, title, link, abstr = r[:8]
        rank[tid] += 1
        if not link or BAD.search(title) or BAD.search(journal) or re.search(NEG[code], title, re.I): continue
        if sum(1 for c in title if 'a' <= c.lower() <= 'z') > len(title) * 0.4: continue
        if not authors.strip(): continue
        tl = title.lower().replace('ё', 'е'); al = abstr.lower().replace('ё', 'е')
        ks = tk[tid]
        if not ks: continue
        ht = sum(1 for k in ks if k in tl); ha = sum(1 for k in ks if k in al)
        need = 1 if len(ks) <= 2 else 2
        ctx_ok = any(c in tl or c in al or c in journal.lower() for c in CTX[code].split())
        if ht < need and not (ht >= 1 and ha >= max(2, len(ks) // 2)): continue
        if not ctx_ok and code != 'tsp': continue
        score = 3.0 * ht / len(ks) + 1.0 * ha / len(ks) + (0.6 if vak else 0) + {'2026': 0.5, '2025': 0.4, '2024': 0.2}.get(year, 0) - 0.03 * rank[tid]
        info[link] = dict(slug=link, year=year, vak=bool(vak), journal=journal, authors=authors, title=title)
        cand[tid].append((score, link))
    chosen = collections.OrderedDict()
    for t in tt:
        got = 0
        for score, link in sorted(cand[t['id']], reverse=True):
            if got >= K: break
            if link in chosen:
                if t['id'] not in chosen[link]['t']: chosen[link]['t'].append(t['id'])
                got += 1; continue
            chosen[link] = dict(info[link], t=[t['id']]); got += 1
    # статья, найденная по одной теме, может подходить и другим: добавляем по названию
    for link, c in chosen.items():
        tl = c['title'].lower().replace('ё', 'е')
        for t in tt:
            ks = tk[t['id']]
            if t['id'] in c['t'] or len(ks) < 2: continue
            if sum(1 for k in ks if k in tl) >= max(2, (len(ks) * 2 + 2) // 3): c['t'].append(t['id'])
    sel = []
    import hashlib
    for link, c in chosen.items():
        c['n'] = {'upp': 'p', 'up': 'u', 'gpp': 'g', 'tp': 't', 'tsp': 's'}[code] + hashlib.sha1(link.encode('utf-8')).hexdigest()[:6]; sel.append(c)
    json.dump(sel, open(D5 + 'cyber_%s_selected.json' % code, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    cov = collections.Counter(tid for c in sel for tid in c['t'])
    empty = [t['refs'][0] for t in tt if cov[t['id']] == 0]
    print(code, 'статей:', len(sel), 'ВАК:', sum(c['vak'] for c in sel), 'тем без статей:', len(empty), ' '.join(empty[:60]))
    return sel
if __name__ == '__main__':
    KK = {'upp': 2, 'up': 2, 'gpp': 3, 'tp': 3, 'tsp': 3}
    for code in (sys.argv[1:] or DISC):
        if os.path.exists(D5 + 'cyber_%s.tsv' % code): run(code, KK[code])
