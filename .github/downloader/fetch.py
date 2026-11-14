#!/usr/bin/env python3
"""Загрузчик источников. Выполняется на серверах GitHub Actions.

Файл заданий — TSV, по одному заданию в строке:  операция <TAB> адрес <TAB> путь_для_сохранения
Операции:
  get  — скачать файл как есть (байт в байт);
  pdf  — открыть страницу в браузере Chrome и сохранить её как PDF
         (в колонтитулах PDF остаются адрес страницы и дата сохранения).
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
    cmd = ['curl', '-sS', '-L', '--max-time', '180', '--retry', '2', '--retry-delay', '3',
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
    return 'ошибка: ' + (r.stderr.strip()[:200] or 'HTTP ' + code), code, ctype


def op_pdf(url, out):
    tmp = os.path.abspath(out + '.part.pdf')
    cmd = ['google-chrome', '--headless=new', '--no-sandbox', '--disable-gpu',
           '--hide-scrollbars', '--lang=ru-RU', '--user-agent=' + UA,
           '--virtual-time-budget=20000', '--run-all-compositor-stages-before-draw',
           '--print-to-pdf=' + tmp, url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return 'ошибка: превышено время', '', ''
    if os.path.exists(tmp) and os.path.getsize(tmp) > 2000:
        os.replace(tmp, out)
        return 'ok', '', 'application/pdf'
    if os.path.exists(tmp):
        os.remove(tmp)
    return 'ошибка: ' + r.stderr.strip()[-200:], '', ''


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
            res, code, ctype = (op_get if op == 'get' else op_pdf)(url, out)
            size = os.path.getsize(out) if res == 'ok' else 0
            digest = sha256(out) if res == 'ok' else ''
            now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            log.writerow([now, op, url, out, res, code, size, ctype, digest])
            lf.flush()
            print(res, code, size, url, '->', out)
            time.sleep(1.0)


if __name__ == '__main__':
    main(sys.argv[1])
