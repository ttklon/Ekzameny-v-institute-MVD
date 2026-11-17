#!/usr/bin/env python3
"""extract_src.py OUT — извлекает текст из PDF источников (нормативные акты, судебная практика) в OUT/*.txt (нужен pymupdf)."""
import sys, os, glob, re
import pymupdf
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..', 'Административная деятельность полиции', '2. Источники')
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
dirs = ['1. Нормативные правовые акты', '2. Судебная практика', '0. Загружено пользователем']
k = 0; empty = []
for d in dirs:
    for f in sorted(glob.glob(os.path.join(ROOT, d, '**', '*.pdf'), recursive=True)):
        rel = os.path.relpath(f, ROOT); import hashlib
        name = hashlib.md5(rel.encode()).hexdigest()[:6] + ' ' + os.path.basename(rel)[:-4][-70:] + '.txt'
        with open(os.path.join(out, '_index.tsv'), 'a', encoding='utf-8') as ix: ix.write(name + '\t' + rel + '\n')
        dst = os.path.join(out, name)
        if os.path.exists(dst): continue
        try:
            doc = pymupdf.open(f); t = '\n'.join(p.get_text() for p in doc)
        except Exception as e:
            t = ''; print('ОШИБКА', rel, e)
        if len(t.strip()) < 200: empty.append(rel)
        open(dst, 'w', encoding='utf-8').write(t); k += 1
print('извлечено', k, 'без текста:', len(empty))
for e in empty: print('  ', e)
# HTML- и txt-копии (исходные страницы официальных публикаций): текст без разметки
import html as _h
for d in dirs:
    for ext in ('html', 'txt'):
        for f in sorted(glob.glob(os.path.join(ROOT, d, '**', '*.' + ext), recursive=True)):
            rel = os.path.relpath(f, ROOT); name = hashlib.md5(rel.encode()).hexdigest()[:6] + ' ' + os.path.basename(rel)[-70:] + '.txt'
            dst = os.path.join(out, name)
            if os.path.exists(dst): continue
            raw = open(f, 'rb').read()
            for enc in ('utf-8', 'cp1251'):
                try: t = raw.decode(enc); break
                except UnicodeDecodeError: t = raw.decode('cp1251', 'replace')
            if ext == 'html':
                m = re.search(r'charset=["\']?([\w-]+)', t[:3000])
                if m and m.group(1).lower() in ('windows-1251', 'cp1251'): t = raw.decode('cp1251', 'replace')
                t = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', t); t = re.sub(r'(?s)<[^>]+>', ' ', t); t = _h.unescape(t)
            open(dst, 'w', encoding='utf-8').write(t)
            with open(os.path.join(out, '_index.tsv'), 'a', encoding='utf-8') as ix: ix.write(name + '\t' + rel + '\n')
print('файлов в', out, len(os.listdir(out)))
