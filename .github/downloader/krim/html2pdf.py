# -*- coding: utf-8 -*-
"""Собрать чистый PDF судебного акта из сохранённой страницы справочного сайта (legalacts.ru, garant.ru).
Запуск: /tmp/venv/bin/python html2pdf.py <html> <pdf> <адрес источника> <сайт> <начало текста (regex)> <конец текста (regex)> [кодировка]"""
import sys, re, html, fitz
def build(src, out, url, site, start, end, enc='utf-8', title='', date='15.11.2026'):
    h = open(src, encoding=enc, errors='replace').read()
    h = re.sub(r'<(script|style)\b.*?</\1>', '', h, flags=re.S | re.I)
    b = re.sub(r'<br\s*/?>', '\n', h); b = re.sub(r'</(p|div|h\d|pre|li|tr)>', '\n', b, flags=re.I); b = re.sub(r'<[^>]+>', '', b); b = html.unescape(b)
    ms = re.search(start, b); assert ms, 'нет начала'
    me = None
    for me in re.finditer(end, b[ms.start():]): break
    assert me, 'нет конца'
    body = b[ms.start(): ms.start() + me.end()]
    paras = [' '.join(p.split()) for p in body.split('\n')]; paras = [p for p in paras if p]
    def cls(p):
        if p.upper() == p and len(p) < 120 and re.search('[А-Я]', p): return 'c'
        if len(p) < 45 and re.match(r'^(Председатель|Конституционного Суда|Российской Федерации|В\.\s?Д\.\s?З)', p): return 'r'
        return 'j'
    note = 'Источник: %s (%s). Сохранено %s. Текст извлечён из сохранённой страницы без изменений; источник неофициальный.' % (url, site, date)
    doc = '<p class="s">%s</p>' % html.escape(note) + ''.join('<p class="%s">%s</p>' % (cls(p), html.escape(p)) for p in paras)
    css = 'body{font-family:serif;font-size:11pt;line-height:1.3} p{margin:0 0 6pt 0} .j{text-align:justify;text-indent:20pt} .c{text-align:center;font-weight:bold} .r{text-align:right} .s{font-size:8.5pt;color:#444;margin-bottom:12pt}'
    story = fitz.Story(html=doc, user_css=css); w = fitz.DocumentWriter(out); mb = fitz.paper_rect('a4'); where = mb + (56, 56, -56, -56); more = 1
    while more:
        dev = w.begin_page(mb); more, _ = story.place(where); story.draw(dev); w.end_page()
    w.close()
    return paras
if __name__ == '__main__':
    a = sys.argv[1:]
    p = build(a[0], a[1], a[2], a[3], a[4], a[5], a[6] if len(a) > 6 else 'utf-8', a[7] if len(a) > 7 else '')
    print(len(p), 'абзацев |', ' '.join(p[:8])[:330], '...', ' '.join(p[-3:])[-160:])
