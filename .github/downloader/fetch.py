#!/usr/bin/env python3
"""Загрузчик источников. Выполняется на серверах GitHub Actions.

Файл заданий — TSV, по одному заданию в строке:  операция <TAB> адрес <TAB> путь_для_сохранения
Операции:
  get  — скачать файл как есть (байт в байт);
  pdf  — открыть страницу в браузере Chrome и сохранить её как PDF;
  kremlin — найти акт в Банке документов kremlin.ru и сохранить полный текст
         в действующей редакции (версия для печати);
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


def op_get(url, out):
    tmp = out + '.part'
    cmd = ['curl', '-sS', '-L', '--connect-timeout', '20', '--max-time', '150', '--retry', '1', '--retry-delay', '3',
           '--max-filesize', str(MAX_BYTES), '-A', UA,
           '-H', 'Accept-Language: ru-RU,ru;q=0.9', '-o', tmp,
           '-w', '%{http_code}\t%{content_type}', url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    code, _, ctype = r.stdout.partition('\t')
    ok = r.returncode == 0 and code.startswith('2') and os.path.exists(tmp) and os.path.getsize(tmp) > 0
    if ok:
        os.replace(tmp, out)
        return 'ok', code, ctype
    if os.path.exists(tmp):
        os.remove(tmp)
    return 'ошибка: ' + (' '.join(r.stderr.split())[:200] or 'HTTP ' + code), code, ctype


def op_pdf(url, out):
    tmp = os.path.abspath(out + '.part.pdf')
    base = ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--lang=ru-RU',
            '--user-agent=' + UA, '--print-to-pdf=' + tmp, url]
    variants = [
        ['google-chrome', '--headless=new', '--virtual-time-budget=15000'],
        ['google-chrome', '--headless=new'],
        ['google-chrome', '--headless'],
    ]
    err = ''
    for v in variants:
        try:
            r = subprocess.run(v + base, capture_output=True, text=True, timeout=180)
            err = ' '.join(r.stderr.split())[-300:]
        except subprocess.TimeoutExpired:
            err = 'превышено время'
        if os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
            os.replace(tmp, out)
            return 'ok', '', 'application/pdf; ' + ' '.join(v[1:])
        if os.path.exists(tmp):
            os.remove(tmp)
    return 'ошибка: ' + err, '', ''


def op_kremlin(url, out):
    """Банк документов kremlin.ru: найти акт поиском (адрес = поисковый запрос) и
    сохранить версию для печати — полный текст акта в действующей редакции."""
    import re, urllib.parse
    tmp = out + '.search'
    res, code, ctype = op_get(url, tmp)
    if res != 'ok':
        return res, code, ctype, url
    page = open(tmp, encoding='utf-8', errors='replace').read()
    os.remove(tmp)
    num = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get('title', [''])[0]
    found = []
    for m in re.finditer(r'href="/acts/bank/(\d+)"[^>]*>(.*?)</a>', page, re.S):
        title = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(2))).replace('\xa0', ' ')
        if not num or ('№ ' + num + ' ') in title + ' ':
            found.append((m.group(1), title.strip()[:120]))
    ids = sorted({f[0] for f in found})
    if len(ids) != 1:
        return 'ошибка: найдено актов: %d %s' % (len(ids), '; '.join('%s %s' % f for f in found[:4])), code, ctype, url
    purl = 'http://www.kremlin.ru/acts/bank/%s/print' % ids[0]
    time.sleep(1.0)
    res, code, ctype = op_get(purl, out)
    return res, code, ctype, purl


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
        return 'ошибка: найдено публикаций: %d' % len(items), code, ctype, url
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
            elif op == 'pub':
                res, code, ctype, url = op_pub(url, out)
            elif op == 'pdf':
                res, code, ctype = op_pdf(url, out)
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
