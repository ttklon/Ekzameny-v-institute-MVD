#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
echo '=== ppt.ru: приказы Генпрокуратуры об утрате силы'
for i in 2 3 4 5; do g "https://pravo.ppt.ru/prikaz/genprokuratura?page=$i" -o /tmp/l$i.html; sleep 1; done
python3 - <<'PY' > /tmp/urls.txt
import re,html
want={('20.03.2023','192'),('23.09.2024','697'),('05.05.2023','305'),('22.02.2023','127'),('28.02.2023','132'),('16.09.2022','517'),('05.02.2025','79'),('09.08.2024','568')}
seen=set()
for i in (2,3,4,5):
    t=open('/tmp/l%d.html'%i,encoding='utf-8',errors='replace').read()
    for h,x in re.findall(r'<a[^>]*href="([^"]*/prikaz/genprokuratura/n-[^"]+)"[^>]*>(.*?)</a>',t,re.S):
        x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())
        m=re.search(r'от (\d\d\.\d\d\.\d{4}) N (\d+)',x)
        if m and (m.group(1),m.group(2)) in want and h not in seen:
            seen.add(h); print(h if h.startswith('http') else 'https://pravo.ppt.ru'+h)
PY
cat /tmp/urls.txt
while read -r u; do g "$u" -o /tmp/a.html; python3 - "$u" <<'PY'
import re,html,sys
t=open('/tmp/a.html',encoding='utf-8',errors='replace').read()
m=re.search(r'<title[^>]*>(.*?)</title>',t,re.S)
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('---',sys.argv[1]); print('   title:',' '.join(html.unescape(m.group(1)).split())[:300] if m else '','| text',len(x))
for k in (r'15\.02\.2011',r'N 33\b',r'оперативно-розыскн'):
    for mm in list(re.finditer(k,x))[:3]: print('   …[%s] %s'%(k,x[max(0,mm.start()-300):mm.end()+400]))
PY
sleep 1; done < /tmp/urls.txt
echo '=== wayback: что сохранено по документам garant'
for id in 72246274 77663768 411260623; do echo "--- $id"; for k in 1 2 3; do r=$(g "http://web.archive.org/cdx/search/cdx?url=base.garant.ru/$id*&fl=timestamp,original,statuscode,length&filter=statuscode:200&limit=40"); if echo "$r" | grep -q '<html'; then sleep 20; else echo "$r" | head -40; break; fi; done; done
