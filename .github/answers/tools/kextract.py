#!/usr/bin/env python3
"""kextract.py OUT [ДИСЦИПЛИНА] — текст всех источников дисциплины (по умолчанию «Криминалистика») со страницами.

Каждый PDF, HTML, TXT из папки «2. Источники» превращается в OUT/<код> <имя>.txt. Перед текстом каждой страницы PDF
стоит строка «@@ N | M»: N — номер страницы файла, M — номер, напечатанный на самой странице (если программа его
нашла: отдельная строка из одного числа в начале или в конце страницы; иначе «-»). OUT/_index.tsv — таблица
«файл текста — путь источника — страниц — знаков». Нужен pymupdf.

Распознавание. У части статей шрифты вшиты без таблицы соответствия символов: текст на экране обычный, а извлекается
набор служебных знаков (поиск по такому файлу ничего не находит). Часть страниц — картинки (образцы протоколов,
схемы, отсканированные издания). Такие страницы программа распознаёт заново с изображения, если установлены
tesserocr и pillow, а в переменной TESSDATA указана папка с rus.traineddata и eng.traineddata (без этого страницы
остаются как есть, а их число печатается в конце). Список распознанных страниц — OUT/_ocr.tsv.
"""
import sys, os, glob, re, hashlib, html as _h
import pymupdf
HERE = os.path.dirname(os.path.abspath(__file__))
disc = sys.argv[2] if len(sys.argv) > 2 else 'Криминалистика'
ROOT = os.path.join(HERE, '..', '..', '..', disc, '2. Источники')
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
rows = []; ocr_rows = []; skipped = 0
BAD = re.compile('[\\x00-\\x08\\x0b-\\x1f\\x7f-\\xa6\\xa8-\\xaa\\xac-\\xaf\\xb2-\\xba\\xbc-\\xbf\\u0180-\\u03ff\\u0500-\\u1fff\\ue000-\\uf8ff\\ufffd]')
API = None
try:
    import io, tesserocr
    from PIL import Image
    if os.environ.get('TESSDATA'): API = tesserocr.PyTessBaseAPI(path=os.environ['TESSDATA'], lang='rus+eng')
except Exception as e:
    API = None
def need_ocr(p, t):
    s = re.sub(r'\s', '', t)
    if len(s) < 40: return bool(p.get_images()) or len(p.get_drawings()) > 20
    return len(BAD.findall(s)) / len(s) > 0.03
def words(t):
    # число «настоящих» слов: в мусоре от перевёрнутой страницы строчных слов из 4 и более букв почти нет
    return len(re.findall(r'(?<![А-Яа-яЁёA-Za-z])(?:[а-яё]{4,}|[a-z]{4,})(?![А-Яа-яЁёA-Za-z])', t))
def ocr(p):
    img = Image.open(io.BytesIO(p.get_pixmap(dpi=300).tobytes('png')))
    API.SetImage(img); best = API.GetUTF8Text()
    if words(best) < len(best) / 25:  # похоже на страницу, набранную боком (альбомные таблицы): пробуем повернуть
        for a in (90, 270):
            API.SetImage(img.rotate(a, expand=True)); t = API.GetUTF8Text()
            if words(t) > 2 * words(best) + 5: best = t
    return best
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
                t = p.get_text()
                if need_ocr(p, t):
                    if API:
                        t = ocr(p); ocr_rows.append('%s\t%d\t%d' % (name, i, len(t)))
                    else: skipped += 1
                parts.append('@@ %d | %s\n%s' % (i, printed(t), t))
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
open(os.path.join(out, '_ocr.tsv'), 'w', encoding='utf-8').write('\n'.join(ocr_rows) + '\n')
print('файлов', len(rows), '| распознано страниц', len(ocr_rows), '| не распознано (нет tesserocr или TESSDATA)', skipped)
