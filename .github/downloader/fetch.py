#!/usr/bin/env python3
"""Загрузчик источников. Выполняется на серверах GitHub Actions.

Файл заданий — TSV, по одному заданию в строке:  операция <TAB> адрес <TAB> путь_для_сохранения
Операции:
  get  — скачать файл как есть (байт в байт);
  pdf  — открыть страницу в браузере Chrome и сохранить её как PDF;
  kremlin — найти акт в Банке документов kremlin.ru и сохранить полный текст
         в действующей редакции (версия для печати);
  ips  — сохранить текст акта в действующей редакции из системы «Законодательство России»
         (ips.pravo.gov.ru): исходная страница и PDF с неё;
  kontur — действующая редакция акта из справочной системы «Контур.Норматив»
         (для приказов МВД и постановлений Пленума ВС РФ, которых нет в «Законодательстве России»);
  sudact, cons — тексты актов с внесёнными изменениями из sudact.ru (версия для печати)
         и consultant.ru; после адреса через # указываются реквизиты для сверки с заголовком страницы;
  post — запрос методом POST (параметры после знака вопроса);
  pub  — найти акт на портале официального опубликования publication.pravo.gov.ru
         и скачать PDF официальной публикации.
Каждая попытка записывается в журнал .github/downloader/log.tsv:
время (UTC), операция, адрес, путь, результат, код HTTP, размер, тип, SHA-256.
"""
import csv, hashlib, os, subprocess, sys, time, datetime

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
LOG = '.github/downloader/log.tsv'
MAX_BYTES = 80 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def op_get(url, out, post=False):
    tmp = out + '.part'
    data = []
    if post:
        url, _, body = url.partition('?')
        data = ['--data', body]
    cmd = ['curl', '-sS', '-L', '--connect-timeout', '15', '--max-time', '150', '--retry', '1', '--retry-delay', '3',
           '--max-filesize', str(MAX_BYTES), '-A', UA,
           '-H', 'Accept-Language: ru-RU,ru;q=0.9', '-o', tmp,
           '-w', '%{http_code}\t%{content_type}'] + data + [url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    code, _, ctype = r.stdout.partition('\t')
    ok = r.returncode == 0 and code.startswith('2') and os.path.exists(tmp) and os.path.getsize(tmp) > 0
    if ok:
        os.replace(tmp, out)
        return 'ok', code, ctype
    if os.path.exists(tmp):
        if out.startswith('.work/') and os.path.getsize(tmp) > 0:
            os.replace(tmp, out + '.err')
        else:
            os.remove(tmp)
    return 'ошибка: ' + (' '.join(r.stderr.split())[:200] or 'HTTP ' + code), code, ctype


def op_pdf(url, out):
    """Сохранить страницу как PDF через Chrome (страница печатается так, как её отдаёт сайт)."""
    import shutil, tempfile
    tmp = os.path.abspath(out + '.part.pdf')
    if not url.endswith('.print.html'):
        # сайт отдаёт страницу по http, а Chrome на сборочной машине такие адреса блокирует,
        # поэтому печатается локальная копия. Текст не меняется: во временную копию только
        # добавляется указание кодировки и убирается автозапуск окна печати.
        tmp_html = os.path.abspath(out + '.print.html')
        if url.startswith('file://'):
            page = open(url[7:], encoding='utf-8', errors='replace').read()
        else:
            res, code, ctype = op_get(url, tmp_html)
            if res != 'ok':
                return res, code, ctype
            page = open(tmp_html, encoding='utf-8', errors='replace').read()
        page = page.replace('<head>', '<head><meta charset="utf-8">', 1).replace(' onload="window.print()"', '')
        page = page.replace('<link rel="stylesheet" href="/static/css/all_fonts.css">', '')
        # ips.pravo.gov.ru: «Список изменяющих документов» на странице свёрнут — в PDF печатается развёрнутым
        page = page.replace('<input class="cap" ', '<input class="cap" checked ')
        open(tmp_html, 'w', encoding='utf-8').write(page)
        try:
            return op_pdf('file://' + tmp_html, out)
        finally:
            os.remove(tmp_html)
    exe = shutil.which('google-chrome') or shutil.which('chromium-browser') or shutil.which('chromium') or 'google-chrome'
    err = ''
    for mode in ('--headless=new', '--headless=old', '--headless'):
        prof = tempfile.mkdtemp(prefix='chr')
        cmd = [exe, mode, '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--no-first-run',
               '--user-data-dir=' + prof, '--lang=ru-RU', '--no-pdf-header-footer', '--timeout=60000',
               '--print-to-pdf=' + tmp, url]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            err = 'код %s; %s' % (r.returncode, r.stderr)
        except subprocess.TimeoutExpired as e:
            err = 'превышено время; %s' % (e.stderr or '')
        shutil.rmtree(prof, ignore_errors=True)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
            os.replace(tmp, out)
            return 'ok', '', 'application/pdf; ' + mode
        if os.path.exists(tmp):
            os.remove(tmp)
        with open(out + '.chrome-error.txt', 'a', encoding='utf-8') as f:
            f.write('=== %s\n%s\n' % (' '.join(cmd), err))
    return 'ошибка: ' + ' '.join(err.split())[-200:], '', ''


def op_kremlin(url, out):
    """Банк документов kremlin.ru: найти акт поиском и сохранить версию для печати —
    полный текст акта в действующей редакции. Адрес = поисковый запрос; после # можно
    указать дату акта ДД.ММ.ГГГГ (нужно для актов до 2000 года: поиск по дате их не находит)."""
    import re, urllib.parse
    if '/acts/bank/search' not in url:
        return kremlin_save(url, out)
    search, _, date = url.partition('#')
    num = urllib.parse.parse_qs(urllib.parse.urlparse(search).query).get('title', [''])[0]
    found, code, ctype = [], '', ''
    for page_no in range(1, 9):
        tmp = out + '.search'
        res, code, ctype = op_get(search + ('&page=%d' % page_no if page_no > 1 else ''), tmp)
        if res != 'ok':
            return res, code, ctype, url
        page = open(tmp, encoding='utf-8', errors='replace').read()
        os.remove(tmp)
        links = re.findall(r'href="/acts/bank/(\d+)"[^>]*>(.*?)</a>', page, re.S)
        for ident, raw in links:
            title = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', raw)).replace('\xa0', ' ') + ' '
            if num and ('№ ' + num + ' ') not in title:
                continue
            if date and ('от ' + date) not in title:
                continue
            found.append((ident, title.strip()[:120]))
        if found or not links or ('page=%d' % (page_no + 1)) not in page:
            break
        time.sleep(1.0)
    ids = sorted({f[0] for f in found})
    if len(ids) != 1:
        return 'ошибка: найдено актов: %d %s' % (len(ids), '; '.join('%s %s' % f for f in found[:4])), code, ctype, url
    time.sleep(1.0)
    return kremlin_save('http://www.kremlin.ru/acts/bank/%s/print' % ids[0], out)


def kremlin_save(purl, out):
    """Сохранить страницу с полным текстом акта (kremlin.ru — версия для печати;
    ips.pravo.gov.ru — выгрузка текста в действующей редакции). Если путь оканчивается на .pdf, рядом в папке
    «Исходные страницы (HTML)» сохраняется страница в том виде, в каком её отдал сайт,
    а PDF печатается с неё (для чтения)."""
    if not out.lower().endswith('.pdf'):
        res, code, ctype = op_get(purl, out)
        return res, code, ctype, purl
    folder = os.path.join(os.path.dirname(out), 'Исходные страницы (HTML)')
    os.makedirs(folder, exist_ok=True)
    src = os.path.join(folder, os.path.basename(out)[:-4] + '.html')
    res, code, ctype = op_get(purl, src)
    if res != 'ok':
        return res, code, ctype, purl
    res, _, kind = op_pdf('file://' + os.path.abspath(src), out)
    return res, code, kind + '; html sha256=' + sha256(src), purl


def op_ipscard(url, out):
    """«Законодательство России»: найти акт поиском (после # — точные реквизиты акта)
    и сохранить его карточку со списком редакций."""
    import json, urllib.parse
    search, _, adoption = url.partition('#')
    tmp = out + '.search'
    res, code, ctype = op_get(search, tmp, post=True)
    if res != 'ok':
        return res, code, ctype, url
    docs = json.load(open(tmp, encoding='utf-8')).get('docs') or []
    os.remove(tmp)
    hits = [d for d in docs if d.get('adoption') == adoption]
    if len(hits) != 1:
        return 'ошибка: найдено актов: %d из %d' % (len(hits), len(docs)), code, ctype, url
    curl = ('http://ips.pravo.gov.ru/api/ips/legislation/document_card.json?' +
            urllib.parse.urlencode({'bpa': hits[0]['baseid'], 'nd': hits[0]['nd']}))
    time.sleep(1.0)
    res, code, ctype = op_get(curl, out)
    return res, code, ctype, curl


def op_kontur(url, out):
    """Справочная система «Контур.Норматив» (тексты актов с внесёнными изменениями).
    По адресу любой редакции акта находит действующую (по списку редакций на странице),
    проверяет пометку сайта «действующая редакция», сохраняет страницу как есть
    в «Исходные страницы (HTML)» и печатает PDF с текстом акта."""
    import json, re, html as htmlmod
    folder = os.path.join(os.path.dirname(out), 'Исходные страницы (HTML)')
    os.makedirs(folder, exist_ok=True)
    src = os.path.join(folder, os.path.basename(out)[:-4] + '.html')
    tried = set()
    for attempt in range(3):
        res, code, ctype = op_get(url, src)
        if res != 'ok':
            return res, code, ctype, url
        page = open(src, encoding='utf-8', errors='replace').read()
        i = page.find('revisionsJSON:')
        revs = json.JSONDecoder().raw_decode(page[page.find('[', i):])[0] if i >= 0 else []
        m = re.search(r'id="js-revisions-status"[^>]*data-status="([^"]*)"[^>]*>(.*?)</div>', page, re.S)
        status = m.group(1) if m else ''
        label = re.sub(r'<[^>]+>', '', m.group(2)).strip() if m else ''
        if status == 'Actual':
            break
        tried.add(url)
        nxt = [r for r in revs if r.get('status') == 0]
        if not nxt:
            os.remove(src)
            return 'ошибка: действующая редакция не найдена (пометка сайта: %s)' % (status or 'нет'), code, ctype, url
        url = 'https://normativ.kontur.ru/document?moduleId=%s&documentId=%s' % (nxt[0]['moduleId'], nxt[0]['documentId'])
        if url in tried:
            os.remove(src)
            return 'ошибка: редакция не помечена как действующая', code, ctype, url
        time.sleep(1.0)
    else:
        os.remove(src)
        return 'ошибка: действующая редакция не найдена', code, ctype, url
    st = re.search(r'<dt>Статус</dt><dd>(.*?)</dd>', page)
    st = st.group(1) if st else '?'
    title = re.search(r'<h1 class="doc_titlebar-title">(.*?)</h1>', page, re.S)
    title2 = re.search(r'<div class="doc_titlebar-title-second">(.*?)</div>', page, re.S)
    body = re.sub(r'<script.*?</script>', '', page, flags=re.S)
    a = body.rfind('<div class="doc_text ')
    b = body.find('<iframe id="js-doc-download-frame"')
    if a < 0 or b < a:
        return 'ошибка: текст акта на странице не найден', code, ctype, url
    printable = ('<html><head><meta charset="utf-8"><style>body{font-family:serif;font-size:12pt;line-height:1.35}'
                 'table{border-collapse:collapse}td,th{border:1px solid #888;padding:2px 4px;vertical-align:top}'
                 '.src{font-family:sans-serif;font-size:9pt;color:#444;border-bottom:1px solid #888;padding-bottom:6px}</style></head><body>'
                 '<div class="src">Источник: %s (справочная система «Контур.Норматив»). %s. Статус: %s. Сохранено %s.</div>'
                 '<h2>%s</h2><p><b>%s</b></p>%s</body></html>') % (
                     htmlmod.escape(url), label, st, datetime.datetime.now(datetime.timezone.utc).strftime('%d.%m.%Y'),
                     title.group(1) if title else '', title2.group(1) if title2 else '', body[a:b])
    tmp_html = os.path.abspath(out + '.print.html')
    open(tmp_html, 'w', encoding='utf-8').write(printable)
    try:
        res, _, kind = op_pdf('file://' + tmp_html, out)
    finally:
        os.remove(tmp_html)
    return res, code, '%s; %s; статус: %s; html sha256=%s' % (kind, label, st, sha256(src)), url


def _reference_copy(src_url, site, title, body_html, out, src, code, expect):
    """Общая часть для справочных систем: проверка реквизитов и объёма текста, печать PDF из локальной копии."""
    import re, html as htmlmod
    plain = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', body_html)))
    title = ' '.join(htmlmod.unescape(title).split())
    if expect and expect not in title:
        os.remove(src)
        return 'ошибка: на странице другой документ: ' + title[:120], code, 'text/html', src_url
    if len(plain) < 3000:
        os.remove(src)
        return 'ошибка: на странице нет полного текста (%d знаков)' % len(plain), code, 'text/html', src_url
    printable = ('<html><head><meta charset="utf-8"><style>body{font-family:serif;font-size:12pt;line-height:1.35}'
                 'table{border-collapse:collapse}td,th{border:1px solid #888;padding:2px 4px;vertical-align:top}'
                 'pre{white-space:pre-wrap;font-size:9pt}a{color:inherit;text-decoration:none}'
                 '.src{font-family:sans-serif;font-size:9pt;color:#444;border-bottom:1px solid #888;padding-bottom:6px}</style></head><body>'
                 '<div class="src">Источник: %s (%s). Сохранено %s.</div><h3>%s</h3>%s</body></html>') % (
                     htmlmod.escape(src_url), site, datetime.datetime.now(datetime.timezone.utc).strftime('%d.%m.%Y'),
                     htmlmod.escape(title), body_html)
    tmp_html = os.path.abspath(out + '.print.html')
    open(tmp_html, 'w', encoding='utf-8').write(printable)
    try:
        res, _, kind = op_pdf('file://' + tmp_html, out)
    finally:
        os.remove(tmp_html)
    return res, code, '%s; %s; знаков текста: %d; html sha256=%s' % (kind, title[:150], len(plain), sha256(src)), src_url


def _src_path(out):
    folder = os.path.join(os.path.dirname(out), 'Исходные страницы (HTML)')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, os.path.basename(out)[:-4] + '.html')


def op_sudact(url, out):
    """sudact.ru: версия для печати содержит полный текст акта одной страницей.
    Адрес: https://sudact.ru/law/<имя>/#<реквизиты, которые должны быть в заголовке>."""
    import re
    url, _, expect = url.partition('#')
    slug = re.search(r'/law/(?:print/)?([^/]+)/?', url).group(1)
    purl = 'https://sudact.ru/law/print/%s/' % slug
    src = _src_path(out)
    res, code, ctype = op_get(purl, src)
    if res != 'ok':
        return res, code, ctype, purl
    page = open(src, encoding='utf-8', errors='replace').read()
    t = re.search(r'<title>(.*?)</title>', page, re.S)
    title = (t.group(1) if t else '').split(' :: ')[0]
    b = re.search(r'<body[^>]*>(.*)</body>', page, re.S)
    body = re.sub(r'<h1>.*?</h1>', '', re.sub(r'<script.*?</script>', '', b.group(1) if b else '', flags=re.S), count=1, flags=re.S)
    return _reference_copy(purl, 'sudact.ru, версия для печати', title, body, out, src, code, expect)


def op_cons(url, out):
    """consultant.ru: документ, размещённый одной страницей.
    Адрес: https://www.consultant.ru/document/cons_doc_LAW_<n>/#<реквизиты, которые должны быть в заголовке>."""
    import re
    url, _, expect = url.partition('#')
    src = _src_path(out)
    res, code, ctype = op_get(url, src)
    if res != 'ok':
        return res, code, ctype, url
    page = open(src, encoding='utf-8', errors='replace').read()
    t = re.search(r'<title>(.*?)</title>', page, re.S)
    title = (t.group(1) if t else '').split(' \\ ')[0]
    a = page.find('<div class="document-page__content')
    ends = [i for i in (page.find(m, a) for m in ('<div class="document-page__notes', '<div class="full-text', '<div class="document-page__separator')) if i > 0]
    body = re.sub(r'<script.*?</script>', '', page[a:min(ends)] if a > 0 and ends else '', flags=re.S)
    return _reference_copy(url, 'consultant.ru, некоммерческая интернет-версия КонсультантПлюс', title, body, out, src, code, expect)


def op_pub(url, out):
    """Официальное опубликование (publication.pravo.gov.ru): найти акт через поиск портала
    (адрес = запрос к /api/Documents, после # — дата акта ГГГГ-ММ-ДД) и скачать PDF."""
    import json
    api, _, date = url.partition('#')
    tmp = out + '.search'
    res, code, ctype = op_get(api, tmp)
    if res != 'ok':
        return res, code, ctype, url
    data = json.load(open(tmp, encoding='utf-8'))
    os.remove(tmp)
    items = [i for i in data.get('items', []) if not date or (i.get('documentDate') or '').startswith(date)]
    if len(items) != 1:
        seen = '; '.join('%s %s' % ((i.get('documentDate') or '')[:10], i.get('number')) for i in data.get('items', [])[:8])
        return 'ошибка: найдено публикаций: %d из %d (%s)' % (len(items), len(data.get('items', [])), seen), code, ctype, url
    purl = 'http://publication.pravo.gov.ru/file/pdf?eoNumber=' + items[0]['eoNumber']
    time.sleep(1.0)
    res, code, ctype = op_get(purl, out)
    return res, code, ctype, purl


def main(tasks_path):
    new_log = not os.path.exists(LOG)
    with open(tasks_path, encoding='utf-8') as f, open(LOG, 'a', encoding='utf-8', newline='') as lf:
        log = csv.writer(lf, delimiter='\t', lineterminator='\n')
        if new_log:
            log.writerow(['время_UTC', 'операция', 'адрес', 'файл', 'результат', 'HTTP', 'байт', 'тип', 'sha256'])
        for line in f:
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) != 3:
                print('пропуск (не 3 поля):', line)
                continue
            op, url, out = (p.strip() for p in parts)
            os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
            if op == 'kremlin':
                res, code, ctype, url = op_kremlin(url, out)
            elif op == 'kontur':
                res, code, ctype, url = op_kontur(url, out)
            elif op == 'sudact':
                res, code, ctype, url = op_sudact(url, out)
            elif op == 'cons':
                res, code, ctype, url = op_cons(url, out)
            elif op == 'ipscard':
                res, code, ctype, url = op_ipscard(url, out)
            elif op == 'ips':
                res, code, ctype, url = kremlin_save(url, out)
            elif op == 'pub':
                res, code, ctype, url = op_pub(url, out)
            elif op == 'pdf':
                res, code, ctype = op_pdf(url, out)
            elif op == 'post':
                res, code, ctype = op_get(url, out, post=True)
            else:
                res, code, ctype = op_get(url, out)
            size = os.path.getsize(out) if res == 'ok' else 0
            digest = sha256(out) if res == 'ok' else ''
            now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            log.writerow([now, op, url, out, res, code, size, ctype, digest])
            lf.flush()
            print(res, code, size, url, '->', out)
            time.sleep(1.0)


if __name__ == '__main__':
    main(sys.argv[1])
