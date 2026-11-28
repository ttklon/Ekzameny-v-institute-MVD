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
  consfind — поиск по сайту consultant.ru: краткий список найденного (название с пометкой редакции, ссылка);
  consauto — найти документ на consultant.ru поиском (запрос#реквизиты) и сохранить его текст;
  ipsact — то же, что ips, но акт сначала находится поиском по реквизитам (указываются после #);
  ipswide — то же, что ips, но PDF печатается в альбомной ориентации (для актов с широкими таблицами);
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
LOG = os.environ.get('FETCH_LOG') or '.github/downloader/log.tsv'
MAX_BYTES = 98 * 1024 * 1024


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


WIDE = False


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
        if WIDE:
            # акт с широкими таблицами: альбомная страница и уменьшенный масштаб, чтобы правые графы не обрезались
            page = page.replace('</head>', '<style>@page{size:A4 landscape;margin:10mm}body{zoom:0.7}</style></head>', 1)
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


def op_ipsact(url, out):
    """«Законодательство России»: найти акт поиском по реквизитам (после # — реквизиты акта,
    например «Федеральный закон от 21.11.2011 № 323-ФЗ»), сохранить текст в действующей редакции
    (исходная страница и PDF) и карточку акта со списком редакций (.work/cards)."""
    import json, urllib.parse
    search, _, adoption = url.partition('#')
    wide = adoption.endswith('|wide')
    adoption = adoption.replace('|wide', '')
    os.makedirs('.work/cards', exist_ok=True)
    tmp = '.work/cards/search.tmp'
    res, code, ctype = op_get(search, tmp, post=True)
    if res != 'ok':
        return res, code, ctype, url
    docs = json.load(open(tmp, encoding='utf-8')).get('docs') or []
    os.remove(tmp)
    norm = lambda x: ' '.join((x or '').split())
    hits = [d for d in docs if norm(d.get('adoption')) == adoption]
    if not hits:
        tail = adoption[adoption.index(' от '):]
        hits = [d for d in docs if norm(d.get('adoption')).endswith(tail)]
    if len(hits) != 1:
        seen = '; '.join(norm(d.get('adoption')) for d in docs[:4])
        return 'ошибка: найдено актов: %d из %d (%s)' % (len(hits), len(docs), seen[:300]), code, ctype, url
    q = urllib.parse.urlencode({'bpa': hits[0]['baseid'], 'nd': hits[0]['nd']})
    time.sleep(1.0)
    op_get('http://ips.pravo.gov.ru/api/ips/legislation/document_card.json?' + q, '.work/cards/%s.json' % hits[0]['nd'])
    time.sleep(1.0)
    # Редакцию берём по полю actualrdk карточки: без него сервер может отдать предыдущую редакцию
    # (так было с Земельным кодексом 14.11.2026 — отдана редакция от 01.09.2026 вместо 13.11.2026).
    try:
        rdk = json.load(open('.work/cards/%s.json' % hits[0]['nd'], encoding='utf-8')).get('actualrdk')
    except Exception:
        rdk = None
    if rdk is not None:
        q += '&rdk=%s' % rdk
    globals()['WIDE'] = wide
    try:
        res, code, kind, purl = kremlin_save('http://ips.pravo.gov.ru/api/ips/legislation/document?' + q + '&target_format=html', out)
    finally:
        globals()['WIDE'] = False
    return res, code, kind + '; ' + norm(hits[0].get('adoption')) + '; ' + norm(hits[0].get('state')), purl


def op_consfind(url, out):
    """Поиск по сайту consultant.ru (после паузы — сайт ограничивает частые запросы): в файл пишется
    краткий список найденного — доступность текста, отметка об утрате силы, название, ссылка."""
    import re, html as _h
    time.sleep(14.0)
    tmp = out + '.html'
    res, code, ctype = op_get(url, tmp)
    if res != 'ok':
        return res, code, ctype, url
    s = open(tmp, encoding='utf-8', errors='replace').read()
    os.remove(tmp)
    rows = []
    for m in re.finditer(r'<li class="search-results__item[^"]*"(.*?)</li>', s, re.S):
        it = m.group(1)
        href = re.search(r'href="([^"]+)"', it)
        avail = re.search(r'data-avail="([^"]*)"', it)
        text = ' '.join(_h.unescape(re.sub(r'<[^>]+>', '', re.sub(r'<span class="search-results__number">.*?</span>', '', it, flags=re.S))).split())
        lost = 'утратил' if 'утратил силу' in text else ''
        text = text.replace('Документ утратил силу или отменён', '').strip()
        rows.append('\t'.join([avail.group(1) if avail else '', lost, text[:420], href.group(1) if href else '']))
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(rows) + '\n')
    return 'ok', code, 'найдено: %d' % len(rows), url


def _cons_search(url, tmp):
    """Страница поиска consultant.ru. Сайт при частых запросах отдаёт ответ очень медленно, и загрузка обрывается по времени;
    первые результаты при этом уже получены. Поэтому берётся и неполная страница."""
    r = subprocess.run(['curl', '-sS', '-L', '--connect-timeout', '15', '--max-time', '240', '-A', UA,
                        '-H', 'Accept-Language: ru-RU,ru;q=0.9', '-o', tmp, '-w', '%{http_code}', url], capture_output=True, text=True)
    s = open(tmp, encoding='utf-8', errors='replace').read() if os.path.exists(tmp) else ''
    if os.path.exists(tmp):
        os.remove(tmp)
    return s, ('ok' if r.returncode == 0 and r.stdout.startswith('2') else 'неполный ответ (curl %d, HTTP %s)' % (r.returncode, r.stdout))


def op_consauto(url, out):
    """consultant.ru: найти документ поиском и сразу сохранить его текст. Адрес: <запрос>#<реквизиты для сверки>.
    Берётся первый найденный документ, в названии которого есть реквизиты; дальше — как операция cons.
    Сайт ограничивает частые запросы — запрос повторяется после паузы."""
    import re, html as _h, urllib.parse
    q, _, expect = url.partition('#')
    surl = 'https://www.consultant.ru/search/?q=' + urllib.parse.quote_plus(q)
    tmp = out + '.page'
    items, s, res = [], '', ''
    for pause in (12.0, 40.0, 75.0):
        time.sleep(pause)
        s, res = _cons_search(surl, tmp)
        items = re.findall(r'<li class="search-results__item[^>]*>(.*?)</li>', s, re.S)
        if items or 'ничего не найдено' in s:
            break
    seen, links = [], []
    want = re.sub(r'[\s\u00a0\u200b\u2009]+', '', expect).replace('№', 'N').lower()
    for it in items[:8]:
        href = re.search(r'href="([^"]+)"', it)
        text = ' '.join(_h.unescape(re.sub(r'<[^>]+>', ' ', it)).split())
        seen.append(text[:70])
        have = re.sub(r'[\s\u00a0\u200b\u2009]+', '', text).replace('№', 'N').lower()
        if href and want in have:
            link = _h.unescape(href.group(1))
            links.append(link[:120])
            # ссылка бывает двух видов: /document/cons_doc_LAW_<n>/ и /cons/cgi/online.cgi?req=doc&base=LAW&n=<n>
            m = re.search(r'cons_doc_LAW_(\d+)', link) or re.search(r'base=LAW(?:&amp;|&|;)n=(\d+)', link)
            if not m:
                continue
            time.sleep(1.5)
            return op_cons('https://www.consultant.ru/document/cons_doc_LAW_%s/#%s' % (m.group(1), expect), out)
    return 'ошибка: в поиске нет документа с реквизитами (найдено %d: %s; ссылки подходящих: %s)' % (len(items), ' | '.join(seen[:3]), ' '.join(links[:2]) or 'нет'), '200', 'text/html', surl


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
                 'table{border-collapse:collapse;width:100%%!important;max-width:100%%!important;table-layout:fixed;font-size:9pt}'
                 'td,th{border:1px solid #888;padding:2px 3px;vertical-align:top;width:auto!important;overflow-wrap:anywhere;word-break:break-word}'
                 'col{width:auto!important}div,p{max-width:100%%;overflow:visible!important}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:9pt;margin:0}'
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


MIN_CHARS = 3000


def _reference_copy(src_url, site, title, body_html, out, src, code, expect):
    """Общая часть для справочных систем: проверка реквизитов и объёма текста, печать PDF из локальной копии."""
    import re, html as htmlmod
    plain = re.sub(r'\s+', ' ', htmlmod.unescape(re.sub(r'<[^>]+>', ' ', body_html)))
    title = ' '.join(htmlmod.unescape(title).split())
    if expect and expect not in title:
        os.remove(src)
        return 'ошибка: на странице другой документ: ' + title[:120], code, 'text/html', src_url
    if len(plain) < MIN_CHARS:
        os.remove(src)
        return 'ошибка: на странице нет полного текста (%d знаков)' % len(plain), code, 'text/html', src_url
    printable = ('<html><head><meta charset="utf-8"><style>body{font-family:serif;font-size:12pt;line-height:1.35}'
                 'table{border-collapse:collapse;width:100%%!important;max-width:100%%!important;table-layout:fixed;font-size:9pt}'
                 'td,th{border:1px solid #888;padding:2px 3px;vertical-align:top;width:auto!important;overflow-wrap:anywhere;word-break:break-word}'
                 'col{width:auto!important}div,p{max-width:100%%;overflow:visible!important}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:9pt;margin:0}'
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


# блок страницы, в котором находится текст документа (по сайтам); если сайта в списке нет — берётся <body>
WEB_BOX = [('meganorm.ru', r'<div[^>]*class="contener_doc"'), ('eccis.org', r'<div[^>]*class="word-page"'),
           ('xn--b1aew.xn--p1ai', r'<div[^>]*class="article[^"]*"'),
           ('legalacts.ru', r'<div[^>]*class="main-center-block[^"]*"'), ('rulaws.ru', r'<div[^>]*(?:id="doc"|class="[^"]*\bdoc\b[^"]*")'),
           ('e-ecolog.ru', r'<div[^>]*class="(?:document|doc-text|content)[^"]*"')]


# сайты, оформление которых при печати мешает (пустые страницы, поля): печатается только текст блока
WEB_PLAIN = ('eccis.org', 'xn--b1aew.xn--p1ai')


def web_block(page, rx):
    """Вырезать из страницы блок <div …>…</div>, начало которого задано выражением rx."""
    import re
    m = re.search(rx, page)
    if not m:
        return None
    depth = 0
    for t in re.finditer(r'<(/?)div\b', page[m.start():]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return page[m.start():m.start() + t.end()] + '>'
    return page[m.start():]


def op_web(url, out):
    """Текст акта со страницы сайта (или с нескольких страниц, адреса через « | »).
    Каждая страница сохраняется как есть в «Исходные страницы (HTML)»; из неё берётся блок с текстом
    документа (без меню и рекламы сайта), блоки подряд печатаются в один PDF. В начале PDF указывается,
    с каких адресов и когда взят текст. После # — слова, которые должны быть в заголовке первой страницы."""
    import re, html as htmlmod, urllib.parse, hashlib
    url, _, expect = url.partition('#')
    parts = [u.strip() for u in url.split(' | ') if u.strip()]
    folder = os.path.join(os.path.dirname(out), 'Исходные страницы (HTML)')
    os.makedirs(folder, exist_ok=True)
    base = os.path.basename(out)[:-4]
    blocks, styles, titles, shas, code, ctype = [], [], [], [], '', ''
    for i, u in enumerate(parts):
        src = os.path.join(folder, base + ('' if i == 0 else ' (часть %d)' % (i + 1)) + '.html')
        res, code, ctype = op_get(u, src)
        if res != 'ok':
            return res, code, ctype, u
        raw = open(src, 'rb').read()
        shas.append(hashlib.sha256(raw).hexdigest())
        enc = re.search(rb'charset=["\']?([\w-]+)', raw[:4000])
        page = None
        for e in ([enc.group(1).decode()] if enc else []) + ['utf-8', 'cp1251']:
            try:
                page = raw.decode(e)
                break
            except (UnicodeDecodeError, LookupError):
                pass
        if page is None:
            page = raw.decode('utf-8', 'replace')
        t = re.search(r'<title[^>]*>(.*?)</title>', page, re.S)
        title = ' '.join(htmlmod.unescape(t.group(1)).split()) if t else ''
        titles.append(title)
        if i == 0 and expect and not all(w.lower() in title.lower() for w in expect.split('&&')):
            os.remove(src)
            return 'ошибка: заголовок страницы не тот: %s' % title[:150], code, ctype, u
        real = re.sub(r'^https?://web\.archive\.org/web/\d+(?:id_)?/', '', u)
        host = urllib.parse.urlparse(real).netloc
        rx = next((r for h, r in WEB_BOX if h in host), None)
        block = web_block(page, rx) if rx else None
        if block is None:
            b = re.search(r'<body[^>]*>(.*)</body>', page, re.S)
            block = b.group(1) if b else page
        block = re.sub(r'<(script|noscript|iframe|form|ins)\b.*?</\1>', '', block, flags=re.S)
        block = re.sub(r'(src|href)="(?!https?:|data:|#|mailto:)([^"]*)"',
                       lambda mm: '%s="%s"' % (mm.group(1), urllib.parse.urljoin(u, htmlmod.unescape(mm.group(2)))), block)
        if len(' '.join(re.sub(r'<[^>]+>', ' ', block).split())) < 800:
            return 'ошибка: на странице мало текста (%s)' % title[:100], code, ctype, u
        head = re.search(r'<head[^>]*>(.*?)</head>', page, re.S)
        if head and i == 0 and not any(h in host for h in WEB_PLAIN):
            for st in re.findall(r'<link[^>]*rel="?stylesheet"?[^>]*>|<style[^>]*>.*?</style>', head.group(1), re.S):
                styles.append(re.sub(r'href="(?!https?:)([^"]*)"',
                                     lambda mm: 'href="%s"' % urllib.parse.urljoin(u, htmlmod.unescape(mm.group(1))), st))
        if any(h in host for h in WEB_PLAIN) and title and title.split(' | ')[0][:40].lower() not in re.sub(r'<[^>]+>', ' ', block).lower():
            block = '<h1 style="font-size:14pt;text-align:center">%s</h1>' % htmlmod.escape(title.split(' | ')[0]) + block
        blocks.append(block)
        time.sleep(1.0)
    day = time.strftime('%d.%m.%Y', time.gmtime())
    note = '<p style="font:9pt sans-serif;color:#555;border-bottom:1px solid #999;padding-bottom:4pt">Текст взят со страниц: %s. Сохранено %s.</p>' % (
        '; '.join(htmlmod.escape(u) for u in parts), day)
    doc = ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title>%s'
           '<style>@page{size:A4;margin:15mm}body{background:#fff !important;color:#000;margin:0;padding:0}'
           'body{font-family:serif;font-size:11pt;line-height:1.3}img{max-width:100%%;height:auto}table{max-width:100%%}.webpart{page-break-before:always}</style></head><body>%s%s</body></html>') % (
        htmlmod.escape(titles[0]), ''.join(styles), note,
        ''.join('<div%s>%s</div>' % (' class="webpart"' if i else '', b) for i, b in enumerate(blocks)))
    tmp = os.path.abspath(out + '.print.html')
    open(tmp, 'w', encoding='utf-8').write(doc)
    try:
        res, c2, t2 = op_pdf('file://' + tmp, out)
    finally:
        os.remove(tmp)
    if res != 'ok':
        return res, code, ctype, parts[0]
    return 'ok', code, 'application/pdf; web; %s; частей: %d; html sha256=%s' % (titles[0][:400], len(parts), ','.join(shas)), parts[0]


def op_sh(cmd, out):
    """Служебная операция: выполнить команду на сборочной машине и сохранить её вывод в файл
    (проверка доступности сайтов и подбор адресов до загрузки документов)."""
    r = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True, errors='replace', timeout=1500)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(r.stdout[-400000:])
        if r.stderr.strip():
            f.write('\n--- stderr ---\n' + r.stderr[-20000:])
    return ('ok' if r.returncode == 0 else 'ошибка: код %d' % r.returncode), '', 'text/plain', cmd


def op_wait(url, out):
    """Пауза до времени ЧЧ:ММ (UTC) — для сайтов, которые отдают тексты по расписанию."""
    import datetime
    h, m = [int(x) for x in url.split(':')]
    now = datetime.datetime.utcnow()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t > now:
        time.sleep((t - now).total_seconds())
    return 'ok', '0', '', url


def op_sudauto(url, out):
    """sudact.ru: перебор возможных адресов акта. Адрес: <имя1> <имя2> ...#<реквизиты, которые должны быть в заголовке>."""
    slugs, _, expect = url.partition('#')
    last = ('ошибка: нет вариантов адреса', '0', 'text/html', url)
    for slug in slugs.split():
        last = op_sudact('https://sudact.ru/law/%s/#%s' % (slug, expect), out)
        if last[0] == 'ok':
            return last
        time.sleep(1.0)
    return last


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
    # документ, разбитый на части: части перечислены ссылками на главной странице документа
    # (номер в адресе может отличаться от номера в ссылках на части: сайт перенаправляет на основную карточку)
    found = re.findall(r'href="(/document/cons_doc_LAW_(\d+)/[0-9a-f]{20,}/)"', page)
    ids = [i for _, i in found]
    n = max(set(ids), key=ids.count) if ids else ''
    parts = list(dict.fromkeys(h for h, i in found if i == n))
    for link in parts:
        time.sleep(1.2)
        purl = 'https://www.consultant.ru' + link
        tmp = src + '.part.html'
        res, code2, _ = op_get(purl, tmp)
        if res != 'ok':
            os.remove(src)
            return res + ' (часть ' + purl + ')', code2, ctype, url
        part = open(tmp, encoding='utf-8', errors='replace').read()
        os.remove(tmp)
        a = part.find('<div class="document-page__content')
        ends = [i for i in (part.find(m, a) for m in ('<div class="document-page__notes', '<div class="full-text', '<div class="document-page__separator')) if i > 0]
        if a < 0 or not ends:
            os.remove(src)
            return 'ошибка: в части нет текста: ' + purl, code2, ctype, url
        body += '\n<hr>\n' + re.sub(r'<script.*?</script>', '', part[a:min(ends)], flags=re.S)
        with open(src, 'a', encoding='utf-8') as f:
            f.write('\n<!-- ===== часть документа: %s ===== -->\n' % purl + part)
    if len(re.sub(r'<[^>]+>', '', body).strip()) < 200:
        # часть документов сайт показывает только по расписанию (вечером в будни и в выходные) — в журнал пишется, что на странице вместо текста
        import html as _hh
        vis = ' '.join(_hh.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style|head).*?</\1>', ' ', page, flags=re.S))).split())
        i = max(vis.find(title[:25]) if title else 0, 0)
        os.remove(src)
        return 'ошибка: на странице нет текста документа; на странице: ' + vis[i:i + 400], code, 'text/html', url
    return _reference_copy(url, 'consultant.ru, некоммерческая интернет-версия КонсультантПлюс', title, body, out, src, code, expect)


def op_consqlist(listfile, out):
    """consultant.ru: поиск по списку «ключ <TAB> запрос». Для каждого запроса в файл пишутся до пяти первых
    найденных документов: ключ, номер в выдаче, отметка об утрате силы, название (с пометкой редакции), ссылка.
    Сайт ограничивает частые запросы (отдаёт страницу без результатов) — тогда запрос повторяется после паузы.
    Нужна для сверки действия и редакции ведомственных актов."""
    import re, html as _h, urllib.parse
    rows_in = [l.rstrip('\n').split('\t') for l in open(listfile, encoding='utf-8') if l.strip()]
    rx = r'<li class="search-results__item[^>]*>(.*?)</li>'
    done = 0
    with open(out, 'w', encoding='utf-8') as f:
        for key, q in rows_in:
            url = 'https://www.consultant.ru/search/?q=' + urllib.parse.quote_plus(q)
            tmp = out + '.page'
            items, s, res = [], '', ''
            for pause in (14.0, 45.0, 75.0):
                time.sleep(pause)
                s, res = _cons_search(url, tmp)
                items = re.findall(rx, s, re.S)
                if items or 'ничего не найдено' in s:
                    break
            if not items:
                note = 'ничего не найдено' if 'ничего не найдено' in s else 'ответ не разобран (%s, %d знаков)' % (res, len(s))
                f.write('\t'.join([key, '0', '', note, '']) + '\n')
            if items or 'ничего не найдено' in s:
                done += 1
            for n, it in enumerate(items[:8], 1):
                href = re.search(r'href="([^"]+)"', it)
                text = ' '.join(_h.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<span class="search-results__number">.*?</span>', '', it, flags=re.S))).split())
                lost = 'утратил' if 'утратил силу' in text else ''
                text = text.replace('Документ утратил силу или отменён', '').strip()
                f.write('\t'.join([key, str(n), lost, text[:330], _h.unescape(href.group(1)) if href else '']) + '\n')
            f.flush()
    return ('ok' if done else 'ошибка: ни одного ответа'), '200', 'text/tab-separated-values; запросов с ответом: %d из %d' % (done, len(rows_in)), listfile


def op_constitles(listfile, out):
    """consultant.ru: для каждого номера документа из файла-списка открыть страницу документа и записать
    её заголовок (в нём сайт указывает дату действующей редакции). Нужна для сверки редакций."""
    import re, html
    ids = [x.strip() for x in open(listfile, encoding='utf-8') if x.strip()]
    n = 0
    with open(out, 'w', encoding='utf-8') as f:
        for i in ids:
            tmp = out + '.page'
            cmd = ['curl', '-sS', '-L', '--connect-timeout', '15', '--max-time', '60', '-A', UA,
                   '-H', 'Accept-Language: ru-RU,ru;q=0.9', '-o', tmp, '-w', '%{http_code}\t%{url_effective}',
                   'https://www.consultant.ru/document/cons_doc_LAW_%s/' % i]
            r = subprocess.run(cmd, capture_output=True, text=True)
            code, _, eff = r.stdout.partition('\t')
            title = ''
            if os.path.exists(tmp):
                page = open(tmp, encoding='utf-8', errors='replace').read()
                m = re.search(r'<title>(.*?)</title>', page, re.S)
                title = ' '.join(html.unescape(m.group(1)).split()) if m else ''
                lost = 'утратил силу' in page[:60000].lower() and 'Документ утратил силу' in page
                os.remove(tmp)
                if lost:
                    title += ' [на странице: документ утратил силу]'
            if title:
                n += 1
            f.write('%s\t%s\t%s\t%s\n' % (i, code, eff, title))
            f.flush()
            time.sleep(0.7)
    return ('ok' if n else 'ошибка: ни одного заголовка'), '200', 'text/tab-separated-values; заголовков: %d из %d' % (n, len(ids)), listfile


def op_ipscards(listfile, out):
    """«Законодательство России»: обновить карточки актов (список редакций) по списку «bpa nd»."""
    outdir = os.path.dirname(out)
    os.makedirs(outdir, exist_ok=True)
    n = total = 0
    for line in open(listfile, encoding='utf-8'):
        if not line.strip():
            continue
        bpa, nd = line.split()
        total += 1
        res, code, ctype = op_get('http://ips.pravo.gov.ru/api/ips/legislation/document_card.json?bpa=%s&nd=%s' % (bpa, nd),
                                  os.path.join(outdir, nd + '.json'))
        n += res == 'ok'
        time.sleep(0.6)
    open(out, 'w').write('%d из %d\n' % (n, total))
    return ('ok' if n == total else 'ошибка: карточек %d из %d' % (n, total)), '200', 'карточек: %d из %d' % (n, total), listfile


def op_sudtitles(listfile, out):
    """sudact.ru: по списку «ключ <TAB> реквизиты <TAB> варианты адреса через пробел» найти страницу акта
    и записать её заголовок (в нём указана дата действующей редакции). Нужна для сверки редакций."""
    import re, html
    n = total = 0
    with open(out, 'w', encoding='utf-8') as f:
        for line in open(listfile, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            key, expect, cands = line.split('\t')
            total += 1
            found = ('', '', '')
            for slug in cands.split():
                tmp = out + '.page'
                r = subprocess.run(['curl', '-sS', '-L', '--connect-timeout', '15', '--max-time', '60', '-A', UA,
                                    '-o', tmp, '-w', '%{http_code}', 'https://sudact.ru/law/%s/' % slug],
                                   capture_output=True, text=True)
                time.sleep(0.5)
                if r.stdout.strip() != '200' or not os.path.exists(tmp):
                    continue
                page = open(tmp, encoding='utf-8', errors='replace').read()
                os.remove(tmp)
                m = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S)
                h1 = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1))).split()) if m else ''
                if expect.replace(' ', '') in h1.replace(' ', ''):
                    text = html.unescape(re.sub(r'<[^>]+>', ' ', page))
                    flag = 'утратил силу' if re.search(r'[Уу]тратил\w* силу или отмен|Документ утратил силу', text) else ''
                    found = (slug, h1, flag)
                    break
            n += bool(found[0])
            f.write('\t'.join((key, expect) + found) + '\n')
            f.flush()
    return ('ok' if n else 'ошибка: ничего не найдено'), '200', 'найдено: %d из %d' % (n, total), listfile


def op_conshead(listfile, out):
    """consultant.ru: для каждого номера документа записать заголовок <h1> страницы (в нём — дата действующей редакции;
    <title> страницы бывает устаревшим) и пометку об утрате силы."""
    import re, html
    n = total = 0
    with open(out, 'w', encoding='utf-8') as f:
        for line in open(listfile, encoding='utf-8'):
            cid = line.strip()
            if not cid:
                continue
            total += 1
            tmp = out + '.page'
            r = subprocess.run(['curl', '-sS', '-L', '--connect-timeout', '15', '--max-time', '60', '-A', UA, '-o', tmp,
                                '-w', '%{http_code}', 'https://www.consultant.ru/document/cons_doc_LAW_%s/' % cid],
                               capture_output=True, text=True)
            time.sleep(0.7)
            h1 = flag = ''
            if os.path.exists(tmp):
                page = open(tmp, encoding='utf-8', errors='replace').read()
                os.remove(tmp)
                m = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.S)
                h1 = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1))).split()) if m else ''
                if 'Документ утратил силу или отменен' in page:
                    flag = 'утратил силу'
                elif 'с изменениями, не вступившими в силу' in page:
                    flag = 'есть будущая редакция'
            n += bool(h1)
            f.write('\t'.join((cid, r.stdout.strip(), h1, flag)) + '\n')
            f.flush()
    return ('ok' if n else 'ошибка'), '200', 'заголовков: %d из %d' % (n, total), listfile


def op_yadisk(url, outdir):
    """Яндекс.Диск: скачать файл (или все файлы папки) по публичной ссылке в каталог outdir."""
    import json as _j, urllib.parse as _u
    os.makedirs(outdir, exist_ok=True)
    api = 'https://cloud-api.yandex.net/v1/disk/public/resources'
    meta_path = os.path.join(outdir, '_meta.json')
    res, code, ctype = op_get(api + '?limit=200&public_key=' + _u.quote(url, safe=''), meta_path)
    if res != 'ok':
        return res, code, ctype, url
    meta = _j.load(open(meta_path, encoding='utf-8'))
    items = meta.get('_embedded', {}).get('items') if meta.get('type') == 'dir' else [meta]
    n = 0
    for it in (items or [])[:40]:
        if it.get('type') != 'file' or it.get('size', 0) > 80 * 1024 * 1024:
            continue
        q = api + '/download?public_key=' + _u.quote(url, safe='')
        if meta.get('type') == 'dir':
            q += '&path=' + _u.quote(it['path'], safe='')
        tmp = os.path.join(outdir, '_href.json')
        r1 = op_get(q, tmp)
        if r1[0] != 'ok':
            continue
        href = _j.load(open(tmp, encoding='utf-8')).get('href')
        os.remove(tmp)
        if href and op_get(href, os.path.join(outdir, it['name'].replace('/', '_')))[0] == 'ok':
            n += 1
    return ('ok' if n else 'ошибка: файлы не получены'), '200', 'файлов: %d; %s' % (n, meta.get('name', '')), url


def op_docx2pdf(src, out):
    """Преобразовать файл Word из репозитория в PDF (LibreOffice)."""
    import shutil, tempfile
    if not shutil.which('soffice'):
        subprocess.run('sudo apt-get update -qq && sudo apt-get install -y -qq libreoffice-writer fonts-liberation',
                       shell=True, capture_output=True)
    if not shutil.which('soffice'):
        return 'ошибка: нет LibreOffice', '', '', src
    d = tempfile.mkdtemp()
    r = subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', d, src], capture_output=True, text=True)
    made = [f for f in os.listdir(d) if f.endswith('.pdf')]
    if not made:
        return 'ошибка: ' + ' '.join((r.stderr or r.stdout).split())[:200], '', '', src
    shutil.move(os.path.join(d, made[0]), out)
    return 'ok', '', 'application/pdf; LibreOffice', src


def op_crawl(url, out):
    """Обход открытого каталога веб-сервера (страницы «Index of»). Адрес: <каталог>#<глубина>,<предел числа каталогов>.
    Пишет таблицу: путь <TAB> размер <TAB> дата."""
    import re, html, urllib.parse as _u
    url, _, lim = url.partition('#')
    depth, maxdirs = (lim.split(',') + ['400'])[:2] if lim else ('3', '400')
    depth, maxdirs = int(depth), int(maxdirs)
    if not url.endswith('/'):
        url += '/'
    url = _u.quote(url, safe=':/%')
    queue, seen, rows, errors = [(url, 0)], set(), [], 0
    while queue and len(seen) < maxdirs:
        u, d = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        r = subprocess.run(['curl', '-sS', '-L', '--connect-timeout', '20', '--max-time', '90', '-A', UA, u],
                           capture_output=True)
        page = r.stdout.decode('utf-8', 'replace')
        if 'Index of' not in page:
            errors += 1
            rows.append((_u.unquote(u), 'ОШИБКА', (r.stderr.decode('utf-8', 'replace') or page[:80]).strip().replace('\n', ' ')[:120]))
            continue
        for m in re.finditer(r'<a href="([^"?#]+)">.*?</a>\s*(?:</td>)?(.*?)(?:</tr>|\n)', page, re.S):
            href, rest = m.group(1), html.unescape(re.sub(r'<[^>]+>', ' ', m.group(2)))
            if href.startswith('/') or href.startswith('..') or '://' in href:
                continue
            full = _u.urljoin(u, href)
            dm = re.search(r'(\d{4}-\d\d-\d\d)', rest)
            sm = re.search(r'\s([\d.]+[KMG]?)\s*$', rest.strip() + ' ')
            if href.endswith('/'):
                rows.append((_u.unquote(full), 'каталог', dm.group(1) if dm else ''))
                if d + 1 < depth:
                    queue.append((full, d + 1))
            else:
                rows.append((_u.unquote(full), sm.group(1) if sm else '', dm.group(1) if dm else ''))
        time.sleep(0.3)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write('\t'.join(row) + '\n')
    ok = len(rows) > errors
    return ('ok' if ok else 'ошибка: каталог недоступен'), '200', 'каталогов: %d; строк: %d; ошибок: %d' % (len(seen), len(rows), errors), url


def op_crawllist(listfile, out):
    """Обход нескольких каталогов: в файле-списке по одному адресу в строке (можно с #глубина,предел). Результат — одна таблица."""
    rows, bad = [], 0
    for line in open(listfile, encoding='utf-8'):
        u = line.strip()
        if not u:
            continue
        tmp = out + '.tmp'
        res = op_crawl(u, tmp)
        if res[0] != 'ok':
            bad += 1
        if os.path.exists(tmp):
            rows.append(open(tmp, encoding='utf-8').read())
            os.remove(tmp)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(''.join(rows))
    return ('ok' if rows else 'ошибка: ничего не получено'), '200', 'каталогов в списке с ошибкой: %d' % bad, listfile


def _fitz():
    try:
        import fitz
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--user', '--break-system-packages', 'pymupdf'],
                       capture_output=True)
        import site, importlib
        importlib.reload(site)
        sys.path.append(site.getusersitepackages())
        import fitz
    return fitz


def op_peeklist(listfile, out):
    """Предварительный просмотр изданий без сохранения: для каждого адреса из списка — размер, число страниц,
    пометка об ограничении доступа, текст первых страниц и оглавление. Нужен, чтобы отобрать издания по содержанию."""
    import re, tempfile, zipfile, urllib.parse as _u
    fitz = _fitz()
    n = total = 0
    clean = lambda t: ' '.join(t.split())
    with open(out, 'w', encoding='utf-8') as f:
        for line in open(listfile, encoding='utf-8'):
            u = line.strip()
            if not u:
                continue
            total += 1
            tmp = tempfile.mktemp(suffix='.bin')
            res, code, ctype = op_get(_u.quote(u, safe=':/%'), tmp)
            if res != 'ok':
                f.write('\t'.join((u, '0', '0', 'ОШИБКА ' + res[:80], '', '')) + '\n')
                continue
            size = os.path.getsize(tmp)
            pages, flag, head, toc = 0, '', '', ''
            try:
                if u.lower().endswith('.zip'):
                    head = '; '.join(z.filename.encode('cp437', 'replace').decode('cp866', 'replace') + ' (%d)' % z.file_size
                                     for z in zipfile.ZipFile(tmp).infolist()[:40])
                else:
                    d = fitz.open(tmp)
                    pages = len(d)
                    first = [d[i].get_text() for i in range(min(pages, 8))]
                    last = [d[i].get_text() for i in range(max(pages - 6, 8), pages)]
                    head = clean(' '.join(first[:4]))[:1100]
                    if len(clean(' '.join(first))) < 200:
                        flag = 'нет текстового слоя'
                    if re.search(r'служебного\s+пользования|[Дд][Сс][Пп]\b|[Сс]екретно', ' '.join(first[:3])):
                        flag += ' ДСП?'
                    for t in first + last:
                        if re.search(r'ОГЛАВЛЕНИЕ|СОДЕРЖАНИЕ|Оглавление|Содержание', t):
                            toc = clean(t)[:2200]
                            break
                    n += 1
            except Exception as e:
                flag = 'не открыт: %s' % type(e).__name__
            os.remove(tmp)
            f.write('\t'.join((u, str(size), str(pages), flag.strip(), head, toc)) + '\n')
            f.flush()
            time.sleep(0.3)
    return ('ok' if n else 'ошибка'), '200', 'просмотрено: %d из %d' % (n, total), listfile


def op_cybersearch(listfile, out):
    """Поиск научных статей в открытой научной библиотеке cyberleninka.ru. В списке: метка <TAB> запрос.
    В таблицу попадают статьи с 2023 года: метка, год, перечень ВАК, журнал, авторы, название, адрес, аннотация."""
    import json, re, html
    n = total = 0
    listfile, _, lim = listfile.partition('#')  # после # — предел строк на один запрос (по умолчанию 40)
    lim = int(lim) if lim else 40
    strip = lambda t: ' '.join(html.unescape(re.sub(r'<[^>]+>', '', t or '')).split())
    with open(out, 'w', encoding='utf-8') as f:
        for line in open(listfile, encoding='utf-8'):
            if not line.strip():
                continue
            tag, _, q = line.rstrip('\n').partition('\t')
            total += 1
            body = json.dumps({'mode': 'articles', 'q': q, 'size': 100, 'from': 0, 'year_from': 2023, 'year_to': 2026},
                              ensure_ascii=False)
            r = subprocess.run(['curl', '-sS', '--connect-timeout', '15', '--max-time', '60', '-A', UA,
                                '-H', 'Content-Type: application/json', '--data', body.encode('utf-8'),
                                'https://cyberleninka.ru/api/search'], capture_output=True)
            time.sleep(1.2)
            try:
                arts = json.loads(r.stdout.decode('utf-8', 'replace')).get('articles', [])
            except Exception:
                f.write('\t'.join((tag, 'ОШИБКА', '', '', '', q, '', r.stdout[:80].decode('utf-8', 'replace'))) + '\n')
                continue
            n += 1
            k = 0
            for a in arts:
                try:
                    year = int(a.get('year') or 0)
                except ValueError:
                    year = 0
                if year < 2023:
                    continue
                vak = 'ВАК' if any((c or {}).get('alias_name') == 'vak' for c in (a.get('catalogs') or [])) else ''
                f.write('\t'.join((tag, str(year), vak, strip(a.get('journal')), '; '.join(a.get('authors') or []),
                                   strip(a.get('name')), a.get('link') or '', strip(a.get('annotation'))[:400])) + '\n')
                k += 1
                if k >= lim:
                    break
            f.flush()
    return ('ok' if n else 'ошибка'), '200', 'запросов выполнено: %d из %d' % (n, total), listfile


def op_ddglist(listfile, out):
    """Поиск адресов страниц через html.duckduckgo.com. В списке: метка <TAB> запрос.
    В таблицу пишутся метка, адрес, заголовок и фрагмент первых 12 результатов (сами страницы не скачиваются)."""
    import re, html, urllib.parse as _u
    n = total = 0
    strip = lambda t: ' '.join(html.unescape(re.sub(r'<[^>]+>', '', t or '')).split())
    with open(out, 'w', encoding='utf-8') as f:
        for line in open(listfile, encoding='utf-8'):
            if not line.strip():
                continue
            tag, _, q = line.rstrip('\n').partition('\t')
            total += 1
            r = subprocess.run(['curl', '-sS', '-L', '--connect-timeout', '15', '--max-time', '40', '-A', UA,
                                '--data-urlencode', 'q=' + q, '--data', 'kl=ru-ru', 'https://html.duckduckgo.com/html/'],
                               capture_output=True)
            time.sleep(4.0)
            page = r.stdout.decode('utf-8', 'replace')
            hits = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(?:.*?class="result__snippet"[^>]*>(.*?)</a>)?', page, re.S)
            if not hits:
                # запасные поисковые системы: Bing, затем Mojeek
                for engine, tpl, rx in (
                        ('bing', 'https://www.bing.com/search?setlang=ru&cc=ru&q=', r'<li class="b_algo".*?<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>(?:.*?<p[^>]*>(.*?)</p>)?'),
                        ('mojeek', 'https://www.mojeek.com/search?q=', r'<a[^>]*class="title"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>(?:.*?<p class="s">(.*?)</p>)?')):
                    r = subprocess.run(['curl', '-sS', '-L', '--compressed', '--connect-timeout', '15', '--max-time', '40', '-A', UA,
                                        '-H', 'Accept-Language: ru-RU,ru;q=0.9', tpl + _u.quote(q)], capture_output=True)
                    time.sleep(3.0)
                    page = r.stdout.decode('utf-8', 'replace')
                    hits = [(h, t, sn) for h, t, sn in re.findall(rx, page, re.S)]
                    if hits:
                        tag = tag + '/' + engine
                        break
            if not hits:
                f.write('\t'.join((tag, 'НЕТ', q, strip(page)[:150])) + '\n')
                continue
            n += 1
            for href, title, snip in hits[:12]:
                m = re.search(r'uddg=([^&]+)', href)
                url = _u.unquote(m.group(1)) if m else html.unescape(href)
                f.write('\t'.join((tag, url, strip(title), strip(snip)[:300])) + '\n')
            f.flush()
    return ('ok' if n else 'ошибка'), '200', 'запросов с результатами: %d из %d' % (n, total), listfile


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
    os.makedirs(os.path.dirname(LOG) or '.', exist_ok=True)
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
            try:
                if op == 'kremlin':
                    res, code, ctype, url = op_kremlin(url, out)
                elif op == 'kontur':
                    res, code, ctype, url = op_kontur(url, out)
                elif op == 'sudact':
                    res, code, ctype, url = op_sudact(url, out)
                elif op == 'web':
                    res, code, ctype, url = op_web(url, out)
                elif op == 'sh':
                    res, code, ctype, url = op_sh(url, out)
                elif op == 'wait':
                    res, code, ctype, url = op_wait(url, out)
                elif op == 'sudauto':
                    res, code, ctype, url = op_sudauto(url, out)
                elif op == 'cons':
                    res, code, ctype, url = op_cons(url, out)
                elif op == 'consauto':
                    res, code, ctype, url = op_consauto(url, out)
                elif op == 'consfind':
                    res, code, ctype, url = op_consfind(url, out)
                elif op == 'constitles':
                    res, code, ctype, url = op_constitles(url, out)
                elif op == 'consqlist':
                    res, code, ctype, url = op_consqlist(url, out)
                elif op == 'ipscards':
                    res, code, ctype, url = op_ipscards(url, out)
                elif op == 'sudtitles':
                    res, code, ctype, url = op_sudtitles(url, out)
                elif op == 'conshead':
                    res, code, ctype, url = op_conshead(url, out)
                elif op in ('sudactshort', 'consshort'):
                    globals()['MIN_CHARS'] = 700  # выписки и короткие акты
                    res, code, ctype, url = (op_sudact if op == 'sudactshort' else op_cons)(url, out)
                    globals()['MIN_CHARS'] = 3000
                elif op == 'docx2pdf':
                    res, code, ctype, url = op_docx2pdf(url, out)
                elif op == 'yadisk':
                    res, code, ctype, url = op_yadisk(url, out)
                elif op == 'peeklist':
                    res, code, ctype, url = op_peeklist(url, out)
                elif op == 'ddglist':
                    res, code, ctype, url = op_ddglist(url, out)
                elif op == 'cybersearch':
                    res, code, ctype, url = op_cybersearch(url, out)
                elif op == 'crawllist':
                    res, code, ctype, url = op_crawllist(url, out)
                elif op == 'crawl':
                    res, code, ctype, url = op_crawl(url, out)
                elif op == 'ipsact':
                    res, code, ctype, url = op_ipsact(url, out)
                elif op == 'ipscard':
                    res, code, ctype, url = op_ipscard(url, out)
                elif op in ('ips', 'ipswide'):
                    globals()['WIDE'] = op == 'ipswide'
                    res, code, ctype, url = kremlin_save(url, out)
                    globals()['WIDE'] = False
                elif op == 'pub':
                    res, code, ctype, url = op_pub(url, out)
                elif op == 'pdf':
                    res, code, ctype = op_pdf(url, out)
                elif op == 'post':
                    res, code, ctype = op_get(url, out, post=True)
                else:
                    res, code, ctype = op_get(url, out)
            except Exception as e:  # одно неудачное задание не должно обрывать весь прогон
                res, code, ctype = 'ошибка: %s: %s' % (type(e).__name__, str(e)[:200]), '', ''
            is_file = res == 'ok' and os.path.isfile(out)
            size = os.path.getsize(out) if is_file else 0
            digest = sha256(out) if is_file else ''
            now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            log.writerow([now, op, url, out, res, code, size, ctype, digest])
            lf.flush()
            print(res, code, size, url, '->', out)
            time.sleep(1.0)


if __name__ == '__main__':
    main(sys.argv[1])
