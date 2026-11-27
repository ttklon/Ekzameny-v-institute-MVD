#!/bin/bash
# Что отдают найденные страницы: заголовок, объём текста, сведения о редакции, признаки неполного текста
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
cat > /tmp/pg.py <<'PY'
import sys,re,html
s=open(sys.argv[1],'rb').read()
if s[:4]==b'%PDF': print('   PDF',len(s)); sys.exit()
t=None
for enc in ('utf-8','cp1251'):
    try: t=s.decode(enc); break
    except Exception: pass
if t is None: t=s.decode('utf-8','replace')
m=re.search(r'<title>(.*?)</title>',t,re.S); print('   title:',' '.join(html.unescape(m.group(1)).split())[:330] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x))
seen=0
for k in ['[Рр]ед\. от \d','с изм\. ','Список изменяющих','С изменениями и дополнениями от','емонстрац','[Пп]олный текст','олная версия','утратил','дсп','ДСП','не действует','Редакция от','редакция от \d','Зарегистрировано в Минюсте','Информация об изменениях']+sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:2]: print('   …[%s] %s'%(k,x[max(0,mm.start()-110):mm.end()+190]))
subs=[]
for h in re.findall(r'href="([^"]+)"',t):
    if re.search(r'garant\.ru/\d+/[0-9a-f]{32}/|^/\d+/[0-9a-f]{32}/',h) and h not in subs: subs.append(h)
if subs: print('   части:',len(subs),' '.join(x.rstrip('/').split('/')[-1][:8] for x in subs[:30]))
PY
p(){ u="$1"; shift; echo "--- $u"; curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' -o /tmp/p.bin -w '   %{http_code} %{size_download} %{content_type} %{url_effective}\n' "$u"; python3 /tmp/pg.py /tmp/p.bin "$@"; sleep 1; }
while IFS=$'\t' read -r u k; do [ -z "$u" ] && continue; if [ -n "$k" ]; then p "$u" "$k"; else p "$u"; fi; done < "$1"
