#!/usr/bin/env python3
"""kextract.py OUT [ДИСЦИПЛИНА] — текст всех источников дисциплины (по умолчанию «Криминалистика») со страницами.

Каждый PDF, HTML, TXT из папки «2. Источники» превращается в OUT/<код> <имя>.txt. Перед текстом каждой страницы PDF
стоит строка «@@ N | M»: N — номер страницы файла, M — номер, напечатанный на самой странице (если программа его
нашла: отдельная строка из одного числа в начале или в конце страницы; иначе «-»). OUT/_index.tsv — таблица
«файл текста — путь источника — страниц — знаков». Нужен pymupdf.
"""
import sys, os, glob, re, hashlib, html as _h
import pymupdf
HERE = os.path.dirname(os.path.abspath(__file__))
disc = sys.argv[2] if len(sys.argv) > 2 else 'Криминалистика'
ROOT = os.path.join(HERE, '..', '..', '..', disc, '2. Источники')
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
rows = []
def printed(t):
    ls = [l.strip() for l in t.split('\n') if l.strip()]
    for l in ls[-2:][::-1] + ls[:2]:
        if re.fullmatch(r'[-–— ]*\d{1,4}[-–— ]*', l): return re.sub(r'\D', '', l)
    return '-'
for f in sorted(glob.glob(os.path.join(ROOT, '**', '*'), recursive=True)):
    if not os.path.isfile(f): continue
    ext = f.rsplit('.', 1)[-1].lower()
    if ext not in ('pdf', 'html', 'txt'): continue
    rel = os.path.relpath(f, ROOT)
    if rel.startswith(('Реестр', 'Литература', 'Контрольные')): continue
    name = hashlib.md5(rel.encode()).hexdigest()[:6] + ' ' + os.path.basename(rel).rsplit('.', 1)[0][:80] + '.txt'
    dst = os.path.join(out, name)
    if ext == 'pdf':
        try:
            doc = pymupdf.open(f); parts = []
            for i, p in enumerate(doc, 1):
                t = p.get_text(); parts.append('@@ %d | %s\n%s' % (i, printed(t), t))
            t = '\n'.join(parts); n = len(doc)
        except Exception as e:
            t = ''; n = 0; print('ОШИБКА', rel, e)
    else:
        raw = open(f, 'rb').read()
        try: t = raw.decode('utf-8')
        except UnicodeDecodeError: t = raw.decode('cp1251', 'replace')
        if ext == 'html':
            m = re.search(r'charset=["\']?([\w-]+)', t[:3000])
            if m and m.group(1).lower() in ('windows-1251', 'cp1251'): t = raw.decode('cp1251', 'replace')
            t = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', t); t = re.sub(r'(?i)<(br|/p|/div|/tr|/h\d)[^>]*>', '\n', t)
            t = re.sub(r'(?s)<[^>]+>', ' ', t); t = _h.unescape(t)
        n = 0
    open(dst, 'w', encoding='utf-8').write(t)
    rows.append('%s\t%s\t%d\t%d' % (name, rel, n, len(re.sub(r'@@ \d+ \| \S+\n', '', t).strip())))
open(os.path.join(out, '_index.tsv'), 'w', encoding='utf-8').write('\n'.join(rows) + '\n')
print('файлов', len(rows))
