#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
ch(){ timeout 120 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=25000 --user-agent="$UA" --dump-dom "$1" 2>/dev/null; }
mkdir -p .work/diag/html
echo '=== ppt.ru: приказы Генпрокуратуры, страницы 1-8'
for i in 1 2 3 4 5 6 7 8; do g "https://pravo.ppt.ru/prikaz/genprokuratura?page=$i" -o /tmp/a.html; python3 - "$i" <<'PY'
import re,html,sys
t=open('/tmp/a.html',encoding='utf-8',errors='replace').read()
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
r=re.findall(r'Приказ Генпрокуратуры России от (\d\d\.\d\d\.\d{4}) N (\d+) "([^"]{0,260})',x)
print('--- стр',sys.argv[1],'актов',len(r),'с',r[-1][0] if r else '','по',r[0][0] if r else '')
for d,n,ti in r:
    if re.search(r'розыск|отдельные организационно-распорядительные|утративш|N 33\b|N 195\b|N 78\b|N 581\b',ti): print('  ',d,n,ti[:240])
PY
sleep 1; done
echo '=== wayback: что сохранено по документам garant'
for id in 72246274 77663768 411260623 72148844; do echo "--- $id"; g "http://web.archive.org/cdx/search/cdx?url=base.garant.ru/$id*&fl=timestamp,original,statuscode,length&filter=statuscode:200&limit=40" | head -40; done
echo '=== ivo.garant.ru (chrome)'
for id in 72246274 411260623; do ch "https://ivo.garant.ru/#/document/$id/paragraph/1:0" > .work/diag/html/ivo$id.html; python3 - "$id" <<'PY'
import re,html,sys
t=open('.work/diag/html/ivo%s.html'%sys.argv[1],errors='replace').read()
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('---',sys.argv[1],'size',len(t),'text',len(x)); print('  ',x[:500]); print('   …',x[-400:])
PY
done
echo '=== archive.ph'
for u in 'https://base.garant.ru/72246274/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'https://base.garant.ru/72246274/'; do g -o /tmp/a.html -w "   HTTP %{http_code} %{size_download} %{url_effective}\n" "https://archive.ph/newest/$u"; head -c 300 /tmp/a.html | tr '\n' ' '; echo; done
echo '=== ips поиск (POST)'
for q in 'Национальный план противодействия коррупции'; do e=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote_plus(sys.argv[1]))' "$q"); for m in "-X POST" "-X POST -H Content-Type:application/json -d {}"; do g $m "http://ips.pravo.gov.ru/api/ips/legislation/search.json?query=$e&limit=10&page=1" -o /tmp/i.json; python3 - <<'PY'
import json
try:
    d=json.load(open('/tmp/i.json',encoding='utf-8')); it=d.get('items') or d.get('documents') or d.get('list') or []
    print('   ключи',list(d.keys())[:10],'записей',len(it))
    for i in it[:10]: print('  ',str(i)[:400])
except Exception as e: print('   ошибка',e, open('/tmp/i.json',errors='replace').read()[:200])
PY
done; done
