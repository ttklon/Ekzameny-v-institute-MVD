#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
ch(){ timeout 120 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=20000 --user-agent="$UA" --dump-dom "$1" 2>/dev/null; }
mkdir -p .work/diag/html
cat > /tmp/tx.py <<'PY'
import sys,re,html
s=open(sys.argv[1],'rb').read(); t=None
for e in ('utf-8','cp1251'):
    try: t=s.decode(e); break
    except Exception: pass
if t is None: t=s.decode('utf-8','replace')
m=re.search(r'<title[^>]*>(.*?)</title>',t,re.S); print('   title:',' '.join(html.unescape(m.group(1)).split())[:260] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x),'| ОБРЕЗАНО' if 'truncated-600 invisible' in t else '')
for k in sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:3]: print('   …[%s] %s'%(k,x[max(0,mm.start()-200):mm.end()+300]))
print('   КОНЕЦ:',x[-300:])
PY
n=0
p(){ n=$((n+1)); echo "--- [$n] $1"; g -o .work/diag/html/p$n.html -w '   HTTP %{http_code} %{size_download} %{content_type}\n' "$1"; shift; python3 /tmp/tx.py .work/diag/html/p$n.html "$@"; }
echo '=== mvd.consultant.ru: поиск по названию'
ms(){ echo "--- mvd.consultant.ru $1"; g -G --data-urlencode "$1" ${2:+--data-urlencode "$2"} -o /tmp/a.html 'https://mvd.consultant.ru/documents/search'; python3 - <<'PY'
import re,html
t=open('/tmp/a.html',errors='replace').read()
r=re.findall(r'<a[^>]*href="(/documents/\d+[^"]*)"[^>]*>(.*?)</a>',t,re.S)
print('   найдено ссылок',len(r))
for h,x in r[:12]: print('  ',h,' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())[:230])
PY
}
ms 'title=делопроизводству в органах внутренних дел'
ms 'title=собственной безопасности'
ms 'title=психологической работы'
ms 'title=пропаганде безопасности дорожного движения'
ms 'title=Типовых положений'
ms 'title=административного законодательства'
ms 'title=полиграф'
ms 'title=оперативно-розыскной деятельности'
ms 'title=выезд'
ms 'title=личном поручительстве'
ms 'title=наставничеств'
ms 'number=1' 'acceptdatefrom=02.01.2013'
echo '--- страница документа банка (как получить текст)'; g -o /tmp/d.html 'https://mvd.consultant.ru/documents/1059276'; python3 - <<'PY'
import re,html
t=open('/tmp/d.html',errors='replace').read()
print('   size',len(t)); print('   ссылки:',sorted(set(re.findall(r'href="([^"]*(?:pdf|print|download|file|page)[^"]*)"',t)))[:15]); print('   img:',re.findall(r'<img[^>]*src="([^"]+)"',t)[:6])
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split()); print('  ',x[1500:2600])
PY
echo '=== garant prime'
for id in 411260623 72246274 70675376 72148844 77663768; do p "https://www.garant.ru/products/ipo/prime/doc/$id/" 'Инструкци\w+ по делопроизводству' 'Механизм реализации'; done
echo '=== garant: части документов'
for id in 411260623 72246274 72148844; do echo "--- части $id"; g -o /tmp/a.html "https://base.garant.ru/$id/"; python3 - "$id" <<'PY'
import re,html,sys
t=open('/tmp/a.html','rb').read().decode('cp1251','replace')
seen=[]
for h,x in re.findall(r'<a[^>]*href="(/%s/[0-9a-f]{32}/)[^"]*"[^>]*>(.*?)</a>'%sys.argv[1],t,re.S):
    if h not in seen: seen.append(h); print('  ',h,' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())[:120])
print('   всего',len(seen))
PY
done
echo '=== прочие сайты'
p 'https://pravo.ppt.ru/prikaz/mvd' 'N 424' '30\.06\.2026'
p 'https://normacs.net/Doclist/doc/29AEL.html' 'Типов'
p 'https://normacs.net/Doclist/doc/26IH4.html' 'Настоящая Инструкция'
p 'https://sibcnti.ru/Doclist/doc/26IH4.html' 'Настоящая Инструкция'
p 'https://www.normacs.com/doc/d2312740/' 'Настоящая Инструкция'
p 'https://www.informio.ru/update/wuz/70432' 'Скачать' 'Приложение'
python3 - <<'PY'
import re
t=open('.work/diag/html/p%d.html'%11,errors='replace').read() if False else ''
PY
grep -ao 'href="[^"]*\.\(pdf\|docx\?\|rtf\|zip\)[^"]*"' .work/diag/html/p$n.html | head -8
p 'https://legalacts.ru/doc/prikaz-mvd-rossii-ot-02092024-n-515-ob-utverzhdenii-instruktsii/' 
p 'https://legalacts.ru/doc/prikaz-mvd-rossii-ot-02012013-n-1-ob-utverzhdenii-kontseptsii/'
p 'https://legalacts.ru/doc/prikaz-mvd-rossii-ot-29122018-n-903-ob-utverzhdenii-nastavlenija/' 'ред\. от'
p 'https://legalacts.ru/search/?term=%D0%BF%D1%80%D0%B8%D0%BA%D0%B0%D0%B7+%D0%9C%D0%92%D0%94+%D0%B4%D0%B5%D0%BB%D0%BE%D0%BF%D1%80%D0%BE%D0%B8%D0%B7%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D1%83+515' '515'
p 'https://epp.genproc.gov.ru/ru/gprf/documents/?types%5B0%5D=2568&q=%D0%BE%D0%BF%D0%B5%D1%80%D0%B0%D1%82%D0%B8%D0%B2%D0%BD%D0%BE-%D1%80%D0%BE%D0%B7%D1%8B%D1%81%D0%BA%D0%BD%D0%BE%D0%B9' 'оперативно-розыскн'
echo '--- sudact поиск (chrome)'; ch 'https://sudact.ru/law/doc/?law-txt=%D0%BF%D1%80%D0%BE%D0%BA%D1%83%D1%80%D0%BE%D1%80%D1%81%D0%BA%D0%BE%D0%B3%D0%BE+%D0%BD%D0%B0%D0%B4%D0%B7%D0%BE%D1%80%D0%B0+%D0%BE%D0%BF%D0%B5%D1%80%D0%B0%D1%82%D0%B8%D0%B2%D0%BD%D0%BE-%D1%80%D0%BE%D0%B7%D1%8B%D1%81%D0%BA%D0%BD%D0%BE%D0%B9+%D0%B4%D0%B5%D1%8F%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%BE%D1%81%D1%82%D0%B8&law-date_from=01.01.2023&law-date_to=28.11.2026' > /tmp/s.html; python3 - <<'PY'
import re,html
t=open('/tmp/s.html',errors='replace').read(); print('   size',len(t))
for h,x in re.findall(r'<a[^>]*href="(/law/[^"]+)"[^>]*>(.*?)</a>',t,re.S)[:25]:
    x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())
    if 'рокур' in x or 'розыск' in x: print('  ',h,x[:200])
PY
echo '=== ips: указ 709, нацплан'
for q in 'Указ Президента Российской Федерации от 06.10.2025 № 709' 'Национальный план противодействия коррупции'; do echo "--- $q"; g -G --data-urlencode "query=$q" 'http://ips.pravo.gov.ru/api/ips/legislation/search.json?limit=10&page=1' | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for i in (d.get("items") or d.get("documents") or [])[:10]: print("  ",i.get("adoption"),"|",(i.get("name") or i.get("title") or "")[:150],"|",i.get("state"))
    print("   ключи",list(d.keys())[:8])
except Exception as e: print("   ошибка",e)'; done
