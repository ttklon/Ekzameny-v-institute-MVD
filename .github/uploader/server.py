#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Приём файлов пользователя в папку «0. Загружено пользователем».

Как устроена передача:
  1. Браузер режет файл на части и для каждой части считает SHA-256.
  2. Сервер принимает часть, сам считает её SHA-256 и длину; при расхождении часть отклоняется
     и браузер передаёт её заново.
  3. После последней части браузер присылает список хэшей всех частей; сервер заново читает
     части с диска, сверяет каждую, собирает файл, сверяет итоговый размер и считает SHA-256 файла.
  4. Файл, который побайтно совпадает с уже принятым или с уже лежащим в базе, второй раз
     не сохраняется — это записывается в журнал.
  5. Принятые файлы и журнал сохраняются в ветку на GitHub (отдельным коммитом, только эта папка).

Передача возобновляемая: части лежат на диске, повторный выбор того же файла продолжает с места обрыва.
Запуск: python3 .github/uploader/server.py [порт]
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.environ.get('UPLOAD_REPO') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(REPO, 'Административная деятельность полиции', '2. Источники')
INBOX = os.environ.get('UPLOAD_INBOX') or os.path.join(SRC, '0. Загружено пользователем')
BIGBOX = os.environ.get('UPLOAD_BIG') or os.path.join(REPO, '.work', 'upload_big')
PARTS = os.environ.get('UPLOAD_PARTS') or '/tmp/adp_upload_parts'
USE_GIT = os.environ.get('UPLOAD_NO_GIT') != '1'
JOURNAL = os.path.join(INBOX, '_Журнал приёмки.tsv')
SUMS = os.path.join(SRC, 'Контрольные суммы SHA-256.txt')
CHUNK = 512 * 1024              # размер части
MAX_FILE = 4 * 1024 ** 3        # предел размера одного файла
GH_LIMIT = 95 * 1024 ** 2       # файлы крупнее в GitHub не отправляются (предел GitHub — 100 МБ)
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

lock = threading.RLock()          # журнал и таблицы
flocks = {}                       # замок на каждую передачу
records = []                      # всё, что записано в журнал
by_id = {}                        # id передачи -> запись
by_sha = {}                       # sha256 -> запись о сохранённом файле
base = {}                         # sha256 -> путь файла, который уже есть в базе
pending = []                      # записи, ещё не отправленные в GitHub
git_state = {'msg': 'ожидание файлов', 'err': '', 'last': 0.0, 'pushed': 0}
last_finish = [0.0]


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())


def clean_rel(rel):
    """Относительный путь файла: без выхода из папки, без служебных символов, имя не длиннее 230 байт."""
    out = []
    for part in re.split(r'[\\/]+', rel or ''):
        part = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', '_', part).strip().strip('.').strip()
        if not part or part in ('.', '..'):
            continue
        stem, ext = os.path.splitext(part)
        ext = ext[:12]
        while len((stem + ext).encode('utf-8')) > 230 and stem:
            stem = stem[:-1]
        out.append((stem + ext) or 'файл')
    return '/'.join(out[-6:]) or 'файл'


def free_path(folder, rel):
    """Свободное имя в папке: при совпадении имён добавляется « (2)», « (3)»…"""
    p = os.path.join(folder, *rel.split('/'))
    if not os.path.exists(p):
        return p
    stem, ext = os.path.splitext(p)
    k = 2
    while os.path.exists('%s (%d)%s' % (stem, k, ext)):
        k += 1
    return '%s (%d)%s' % (stem, k, ext)


def load():
    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)
    if os.path.isfile(SUMS):
        for line in open(SUMS, encoding='utf-8'):
            m = re.match(r'^([0-9a-f]{64})  (.+)$', line.rstrip('\n'))
            if m and not m.group(2).startswith('0. Загружено пользователем/'):
                base.setdefault(m.group(1), m.group(2))
    if os.path.isfile(JOURNAL):
        for line in open(JOURNAL, encoding='utf-8'):
            c = line.rstrip('\n').split('\t')
            if len(c) < 8 or c[0].startswith('время'):
                continue
            r = dict(time=c[0], id=c[1], rel=c[2], size=int(c[3]), sha=c[4], status=c[5], saved=c[6], note=c[7], pushed=True)
            # запись действительна, только если файл на месте (или он и не должен был сохраняться)
            if r['status'] in ('new', 'big') and not os.path.isfile(os.path.join(REPO, r['saved'])):
                continue
            records.append(r)
            by_id[r['id']] = r
            if r['status'] in ('new', 'big'):
                by_sha[r['sha']] = r
            if r['status'] == 'new':      # после перезапуска сохранение в GitHub перепроверяется
                r['pushed'] = False
                pending.append(r)
    # крупные файлы лежат вне Git: папка исключается локально
    ex = os.path.join(REPO, '.git', 'info', 'exclude')
    if USE_GIT and os.path.isdir(os.path.dirname(ex)):
        cur = open(ex, encoding='utf-8').read() if os.path.isfile(ex) else ''
        if '.work/upload_big/' not in cur:
            with open(ex, 'a', encoding='utf-8') as f:
                f.write('\n.work/upload_big/\n')


def journal(r):
    new = not os.path.isfile(JOURNAL)
    with open(JOURNAL, 'a', encoding='utf-8') as f:
        if new:
            f.write('время UTC\tid передачи\tисходное имя\tразмер, байт\tSHA-256\tрезультат\tсохранён как\tпримечание\n')
        f.write('\t'.join([r['time'], r['id'], r['rel'], str(r['size']), r['sha'], r['status'], r['saved'], r['note']]) + '\n')
        f.flush()
        os.fsync(f.fileno())


def sess_dir(sid):
    return os.path.join(PARTS, sid)


def part_len(meta, i):
    return min(CHUNK, meta['size'] - i * CHUNK)


def have_parts(sid, meta):
    d = sess_dir(sid)
    out = []
    for i in range(meta['n']):
        p = os.path.join(d, '%06d.part' % i)
        if os.path.isfile(p) and os.path.getsize(p) == part_len(meta, i):
            out.append(i)
    return out


def get_meta(sid):
    p = os.path.join(sess_dir(sid), 'meta.json')
    if not re.fullmatch(r'[0-9a-f]{24}', sid or '') or not os.path.isfile(p):
        return None
    return json.load(open(p, encoding='utf-8'))


def flock(sid):
    with lock:
        return flocks.setdefault(sid, threading.Lock())


def api_init(d):
    rel = clean_rel(str(d.get('rel') or ''))
    size = int(d.get('size'))
    mtime = int(d.get('mtime') or 0)
    if size < 0 or size > MAX_FILE:
        return 400, {'error': 'размер файла вне допустимого (до 4 ГБ)'}
    sid = hashlib.sha256(('%s|%d|%d' % (rel, size, mtime)).encode('utf-8')).hexdigest()[:24]
    with lock:
        r = by_id.get(sid)
        if r:
            return 200, {'id': sid, 'done': True, 'rec': pub(r)}
    with flock(sid):
        meta = get_meta(sid)
        if not meta:
            meta = {'rel': rel, 'size': size, 'mtime': mtime, 'n': (size + CHUNK - 1) // CHUNK, 'chunk': CHUNK}
            os.makedirs(sess_dir(sid), exist_ok=True)
            with open(os.path.join(sess_dir(sid), 'meta.json'), 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False)
        return 200, {'id': sid, 'done': False, 'n': meta['n'], 'chunk': CHUNK, 'have': have_parts(sid, meta)}


def api_chunk(q, body):
    sid = q.get('id', [''])[0]
    meta = get_meta(sid)
    if not meta:
        return 404, {'error': 'передача не найдена — начните файл заново'}
    try:
        i = int(q.get('i', [''])[0])
    except ValueError:
        return 400, {'error': 'нет номера части'}
    want = q.get('sha', [''])[0].lower()
    if not 0 <= i < meta['n']:
        return 400, {'error': 'номер части вне диапазона'}
    if len(body) != part_len(meta, i):
        return 409, {'error': 'length', 'got': len(body), 'want': part_len(meta, i)}
    got = hashlib.sha256(body).hexdigest()
    if got != want:
        return 409, {'error': 'hash', 'got': got}
    p = os.path.join(sess_dir(sid), '%06d.part' % i)
    tmp = '%s.%d.tmp' % (p, threading.get_ident())
    with open(tmp, 'wb') as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    return 200, {'ok': True, 'i': i, 'sha': got}


def api_finish(d):
    sid = str(d.get('id') or '')
    with lock:
        r = by_id.get(sid)
        if r:
            return 200, {'ok': True, 'rec': pub(r)}
    meta = get_meta(sid)
    if not meta:
        return 404, {'error': 'передача не найдена — начните файл заново'}
    hashes = [str(h).lower() for h in (d.get('hashes') or [])]
    if len(hashes) != meta['n']:
        return 400, {'error': 'число хэшей не равно числу частей'}
    with flock(sid):
        with lock:
            r = by_id.get(sid)
            if r:
                return 200, {'ok': True, 'rec': pub(r)}
        sd = sess_dir(sid)
        # 1) повторная сверка каждой части, прочитанной с диска
        bad = []
        for i in range(meta['n']):
            p = os.path.join(sd, '%06d.part' % i)
            ok = os.path.isfile(p) and os.path.getsize(p) == part_len(meta, i)
            if ok:
                with open(p, 'rb') as f:
                    ok = hashlib.sha256(f.read()).hexdigest() == hashes[i]
            if not ok:
                bad.append(i)
                if os.path.exists(p):
                    os.remove(p)
        if bad:
            return 200, {'ok': False, 'bad': bad}
        # 2) сборка, сверка размера, SHA-256 всего файла
        tmp = os.path.join(sd, 'assembled.bin')
        h = hashlib.sha256()
        total = 0
        with open(tmp, 'wb') as out:
            for i in range(meta['n']):
                with open(os.path.join(sd, '%06d.part' % i), 'rb') as f:
                    b = f.read()
                h.update(b)
                out.write(b)
                total += len(b)
            out.flush()
            os.fsync(out.fileno())
        if total != meta['size'] or os.path.getsize(tmp) != meta['size']:
            os.remove(tmp)
            return 200, {'ok': False, 'bad': list(range(meta['n'])), 'error': 'размер собранного файла не совпал'}
        sha = h.hexdigest()
        # 3) проверка собранного файла чтением с диска
        h2 = hashlib.sha256()
        with open(tmp, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''):
                h2.update(b)
        if h2.hexdigest() != sha:
            os.remove(tmp)
            return 200, {'ok': False, 'bad': list(range(meta['n'])), 'error': 'собранный файл не прошёл проверку'}
        with lock:
            r = dict(time=now(), id=sid, rel=meta['rel'], size=meta['size'], sha=sha, status='new', saved='', note='', pushed=False)
            if meta['size'] == 0:
                r['note'] = 'пустой файл (0 байт)'
            if sha in by_sha:
                r['status'] = 'dup'
                r['note'] = 'повтор уже принятого файла: ' + by_sha[sha]['rel']
            elif sha in base:
                r['status'] = 'have'
                r['note'] = 'побайтно совпадает с файлом базы: ' + base[sha]
            else:
                big = meta['size'] > GH_LIMIT
                dst = free_path(BIGBOX if big else INBOX, meta['rel'])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(tmp, dst)
                r['saved'] = os.path.relpath(dst, REPO)
                if big:
                    r['status'] = 'big'
                    r['note'] = (r['note'] + '; ' if r['note'] else '') + 'больше 95 МБ: хранится только на сервере, в GitHub не отправляется'
                if os.path.basename(dst) != os.path.basename(meta['rel']):
                    r['note'] = (r['note'] + '; ' if r['note'] else '') + 'имя уже было занято другим файлом — сохранён под новым именем'
                by_sha[sha] = r
            journal(r)
            records.append(r)
            by_id[sid] = r
            pending.append(r)
            last_finish[0] = time.time()
        shutil.rmtree(sd, ignore_errors=True)
        return 200, {'ok': True, 'rec': pub(r)}


def pub(r):
    return {'rel': r['rel'], 'size': r['size'], 'sha': r['sha'], 'status': r['status'], 'saved': r['saved'],
            'note': r['note'], 'pushed': bool(r.get('pushed')), 'time': r['time']}


def api_state(full):
    with lock:
        c = {'new': 0, 'dup': 0, 'have': 0, 'big': 0}
        size = 0
        for r in records:
            c[r['status']] = c.get(r['status'], 0) + 1
            if r['status'] in ('new', 'big'):
                size += r['size']
        to_push = sum(1 for r in records if r['status'] == 'new')
        st = {'counts': c, 'bytes': size, 'git': dict(git_state, enabled=USE_GIT, pending=len([r for r in pending if r['status'] == 'new']), total=to_push,
                                                        pushed=sum(1 for r in records if r['status'] == 'new' and r.get('pushed')))}
        if full:
            st['files'] = [pub(r) for r in records]
        return 200, st


def api_verify(d):
    ids = [str(x) for x in (d.get('ids') or [])][:5000]
    with lock:
        return 200, {'recs': {i: pub(by_id[i]) for i in ids if i in by_id}}


def git(*a, timeout=600):
    r = subprocess.run(['git', '-C', REPO] + list(a), capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def git_worker():
    """Сохраняет принятые файлы в ветку на GitHub: только папку приёма, пачками."""
    while True:
        time.sleep(4)
        if not USE_GIT:
            continue
        with lock:
            if not pending:
                continue
            quiet = time.time() - last_finish[0]
            batch_bytes = sum(r['size'] for r in pending if r['status'] == 'new')
            if quiet < 10 and len(pending) < 25 and batch_bytes < 120 * 1024 ** 2:
                continue
            if git_state['err'] and time.time() - git_state['last'] < 45:
                continue
            batch = list(pending)
        git_state['last'] = time.time()
        try:
            paths = [JOURNAL] + [os.path.join(REPO, r['saved']) for r in batch if r['status'] == 'new']
            git_state['msg'] = 'сохраняю в GitHub: %d' % (len(paths) - 1)
            code, out = git('add', '--', *paths)
            if code:
                raise RuntimeError('git add: ' + out[-300:])
            n = len(paths) - 1
            msg = 'Приём файлов пользователя: %d (автоматически)' % n if n else 'Приём файлов пользователя: журнал (автоматически)'
            code, out = git('commit', '-q', '-m', msg, '--', *paths)
            if code and 'nothing to commit' not in out and 'nothing added' not in out and 'no changes added' not in out:
                raise RuntimeError('git commit: ' + out[-300:])
            code, branch = git('rev-parse', '--abbrev-ref', 'HEAD')
            code, out = git('push', '-q', 'origin', 'HEAD:' + branch)
            if code:
                git('pull', '-q', '--rebase', '--autostash', 'origin', branch)
                code, out = git('push', '-q', 'origin', 'HEAD:' + branch)
            if code:
                raise RuntimeError('git push: ' + out[-300:])
            with lock:
                for r in batch:
                    r['pushed'] = True
                    if r in pending:
                        pending.remove(r)
                git_state.update(err='', msg='сохранено в GitHub', pushed=git_state['pushed'] + n)
        except Exception as e:  # повтор через 45 секунд
            git_state.update(err=str(e)[:400], msg='ошибка сохранения в GitHub, повтор через минуту')
            print(now(), 'GIT', str(e)[:400], flush=True)


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'upload'

    def log_message(self, fmt, *a):
        pass

    def send(self, code, obj=None, raw=None, ctype='application/json; charset=utf-8'):
        body = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def body(self, limit):
        n = int(self.headers.get('Content-Length') or 0)
        if n > limit:
            self.close_connection = True
            return None
        data = b''
        while len(data) < n:
            b = self.rfile.read(min(1 << 16, n - len(data)))
            if not b:
                break
            data += b
        return data

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path in ('/', '/index.html'):
            return self.send(200, raw=open(HTML, 'rb').read(), ctype='text/html; charset=utf-8')
        if u.path == '/api/state':
            return self.send(*api_state('full=1' in u.query))
        if u.path == '/api/config':
            return self.send(200, {'chunk': CHUNK, 'max': MAX_FILE, 'gh_limit': GH_LIMIT})
        self.send(404, {'error': 'нет такой страницы'})

    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        try:
            if u.path == '/api/chunk':
                data = self.body(CHUNK + 1024)
                if data is None:
                    return self.send(413, {'error': 'часть больше допустимого'})
                return self.send(*api_chunk(urllib.parse.parse_qs(u.query), data))
            data = self.body(8 << 20)
            if data is None:
                return self.send(413, {'error': 'запрос слишком большой'})
            d = json.loads(data.decode('utf-8') or '{}')
            if u.path == '/api/init':
                return self.send(*api_init(d))
            if u.path == '/api/finish':
                return self.send(*api_finish(d))
            if u.path == '/api/verify':
                return self.send(*api_verify(d))
            self.send(404, {'error': 'нет такой страницы'})
        except Exception as e:
            print(now(), 'ERR', self.path[:80], repr(e)[:300], flush=True)
            try:
                self.send(500, {'error': 'ошибка сервера: %s' % str(e)[:200]})
            except Exception:
                pass

    do_PUT = do_POST


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    load()
    threading.Thread(target=git_worker, daemon=True).start()
    print(now(), 'приём файлов: порт %d, папка %s, в базе %d контрольных сумм, в журнале %d записей' % (port, INBOX, len(base), len(records)), flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()


if __name__ == '__main__':
    main()
