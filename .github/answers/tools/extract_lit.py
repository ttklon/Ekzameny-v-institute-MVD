import sys, os, glob, hashlib, pymupdf
ROOT = '/home/user/Ekzameny-v-institute-MVD/Административная деятельность полиции/2. Источники'
out = '/tmp/lit'; part = int(sys.argv[1]); nparts = int(sys.argv[2])
fs = []
for d in ('3. Учебная литература', '4. Научные материалы (с 2023 года)', '5. Эмпирические материалы (с 2023 года)'):
    fs += sorted(glob.glob(os.path.join(ROOT, d, '**', '*.pdf'), recursive=True))
k = 0; empty = 0
for i, f in enumerate(fs):
    if i % nparts != part: continue
    rel = os.path.relpath(f, ROOT); name = hashlib.md5(rel.encode()).hexdigest()[:6] + ' ' + os.path.basename(rel)[:-4][-70:] + '.txt'
    dst = os.path.join(out, name)
    if os.path.exists(dst): continue
    try:
        doc = pymupdf.open(f); t = '\n'.join(p.get_text() for p in doc)
    except Exception as e:
        t = ''
    if len(t.strip()) < 500: empty += 1
    open(dst + '.tmp', 'w', encoding='utf-8').write(t); os.rename(dst + '.tmp', dst)
    with open(os.path.join(out, '_index%d.tsv' % part), 'a', encoding='utf-8') as ix: ix.write(name + '\t' + rel + '\n')
    k += 1
print('part', part, 'извлечено', k, 'без текста', empty)
