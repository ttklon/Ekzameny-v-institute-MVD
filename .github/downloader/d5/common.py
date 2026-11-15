# -*- coding: utf-8 -*-
"""Общие данные для пяти дисциплин (УПП, УП, ГПП, ТП, ТСП): папки, перечни вопросов, темы.
Тема — один вопрос; одинаковые формулировки из двух перечней одной дисциплины сливаются в одну тему."""
import os, re, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
D5 = '.github/downloader/d5/'
Q = '1. Примерный перечень вопросов/'
DISC = {
    'upp': dict(dir='Уголовно-процессуальное право', short='УПП', lists=[
        ('Э', 'Примерный перечень вопросов к экзамену по уголовно-процессуальному праву.txt', 'экзамен'),
        ('З', 'Примерный перечень вопросов для подготовки к зачету УПП.txt', 'зачёт')]),
    'up': dict(dir='Уголовное право', short='УП', lists=[
        ('А', 'Примерный перечень вопросов для подготовки к экзамену УП.txt', 'перечень 1'),
        ('Б', 'еще один Примерный перечень вопросов для подготовки к экзамену УП.txt', 'перечень 2')]),
    'gpp': dict(dir='Гражданско-процессуальное право', short='ГПП', lists=[
        ('', 'Примерный перечень вопросов для подготовки к экзамену ГПП.txt', 'экзамен')]),
    'tp': dict(dir='Трудовое право', short='ТП', lists=[
        ('', 'Примерный перечень вопросов для подготовки к экзамену ТП.txt', 'экзамен')]),
    'tsp': dict(dir='Тактико-специальная подготовка', short='ТСП', lists=[
        ('', 'Примерный перечень вопросов к зачёту по тактике специальной подготовки.txt', 'зачёт')]),
}
def norm(t):
    return re.sub(r'[^а-яёa-z0-9]+', ' ', t.lower().replace('ё', 'е')).strip()
def read_list(code, tag, fn):
    """-> [(метка, текст)]; метка: 'Э12', 'Б-О7' (общая часть), 'Б-С7' (особенная часть), 'Д3' (ТСП, ненумерованные)."""
    raw = open(os.path.join(ROOT, DISC[code]['dir'], Q, fn), encoding='utf-8').read().replace('\r', '')
    out, cur, part, seen1 = [], None, '', False
    extra = ''
    for l in raw.split('\n'):
        s = l.strip()
        if not s: continue
        if code == 'tsp' and s.lower().startswith('еще'):
            extra = []; continue
        if extra != '':
            if s[0].isupper() or not extra: extra.append(s)
            else: extra[-1] += ' ' + s
            continue
        m = re.match(r'^(\d+)\s*[.)]?\s*(.*)$', s)
        if m and (re.match(r'^\d+\s*[.)]', s) or re.match(r'^\d+\s+[А-ЯЁ]', s)):
            n = int(m.group(1))
            if code == 'up' and tag == 'Б':
                if n == 1 and seen1: part = '-С'
                elif n == 1: part = '-О'; seen1 = True
            cur = [tag + part + str(n), m.group(2)]; out.append(cur)
        elif cur is not None and not s.isupper():
            cur[1] += ' ' + s
    res = [(a, ' '.join(b.split())) for a, b in out]
    if code == 'up' and tag == 'А':  # в перечне номер 63 стоит дважды, 64 пропущен: второй «63» считается 64-м
        k = [i for i, (a, _) in enumerate(res) if a == 'А63']
        if len(k) == 2: res[k[1]] = ('А64', res[k[1]][1])
    if extra:
        res += [('Д%d' % (i + 1), ' '.join(x.split())) for i, x in enumerate(extra)]
    return res
def topics(code):
    """-> [dict(id, refs=[метки], text)] в порядке первого появления."""
    tt, idx = [], {}
    for tag, fn, _ in DISC[code]['lists']:
        for lab, text in read_list(code, tag, fn):
            k = norm(text)
            if k in idx: idx[k]['refs'].append(lab)
            else:
                idx[k] = dict(id='%s%03d' % (code, len(tt) + 1), refs=[lab], text=text); tt.append(idx[k])
    return tt
if __name__ == '__main__':
    for c in DISC:
        t = topics(c)
        print(c, 'тем:', len(t), 'меток:', sum(len(x['refs']) for x in t), '| последние:', t[-1]['refs'], t[-1]['text'][:70])
        if c == 'tsp':
            for x in t[60:]: print('  ', x['refs'][0], x['text'][:90])
