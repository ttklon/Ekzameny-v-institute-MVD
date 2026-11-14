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
    cmd = ['curl', '-sS', '-L', '--connect-timeout', '20', '--max-time', '150', '--retry', '1', '--retry-delay', '3',
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
