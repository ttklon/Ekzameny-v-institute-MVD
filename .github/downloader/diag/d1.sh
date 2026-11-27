#!/bin/bash
# Проверка доступности источников для актов, которых нет на sudact.ru и в открытой части consultant.ru
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 60 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
vis(){ python3 -c "
import sys,re,html
s=sys.stdin.read()
t=html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',s,flags=re.S)))
t=' '.join(t.split()); print(len(s),len(t)); print(t[:int(sys.argv[1])])" "$1"; }
links(){ python3 -c "
import sys,re,html,urllib.parse
s=sys.stdin.read(); print('bytes',len(s))
seen=[]
for h in re.findall(r'href=\"([^\"]+)\"',s):
    h=html.unescape(h)
    m=re.search(r'uddg=([^&]+)',h)
    if m: h=urllib.parse.unquote(m.group(1))
    if h.startswith('http') and not re.search(r'duckduckgo|mojeek|brave|bing|microsoft|yandex|google|yastatic',h) and h not in seen: seen.append(h)
print('\n'.join(seen[:15]))"; }
Q='приказ МВД России от 29.12.2018 № 903 Наставление по организации деятельности Госавтоинспекции по пропаганде'
echo '=== 1 consultant EXP link'; g -o /tmp/c1.html -w '%{http_code} %{url_effective}\n' 'https://login.consultant.ru/link/?req=doc&base=EXP&n=907535&demo=1'; vis 700 < /tmp/c1.html
grep -o 'online.cgi[^"'"'"' ]*' /tmp/c1.html | sort -u | head -20
echo '=== 2 chrome dump-dom'; timeout 120 google-chrome --headless=new --no-sandbox --disable-gpu --virtual-time-budget=25000 --user-agent="$UA" --dump-dom 'https://login.consultant.ru/link/?req=doc&base=EXP&n=907535&demo=1' > /tmp/c2.html 2>/tmp/c2.err; vis 2500 < /tmp/c2.html; grep -o '<iframe[^>]*>' /tmp/c2.html | head -5
echo '=== 3 rulaws и другие зеркала'
for u in 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-29.12.2018-N-903/' 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-02.09.2024-N-515/' 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-02.09.2013-N-660/' 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-02.01.2013-N-1/' 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-30.06.2026-N-424/' 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-10.09.2019-N-612/' 'https://legalacts.ru/doc/prikaz-mvd-rossii-ot-29122018-n-903-ob-utverzhdenii-nastavlenija-po/' 'https://docs.cntd.ru/search?q=%D0%93%D0%9E%D0%A1%D0%A2%20%D0%A0%2052766-2007' 'https://base.garant.ru/72143900/' 'https://normativ.kontur.ru/search?query=%D0%BF%D1%80%D0%B8%D0%BA%D0%B0%D0%B7%20%D0%9C%D0%92%D0%94%20903%20%D0%BF%D1%80%D0%BE%D0%BF%D0%B0%D0%B3%D0%B0%D0%BD%D0%B4%D0%B0'; do echo "--- $u"; g -o /tmp/p.html -w '%{http_code} %{size_download}\n' "$u"; vis 300 < /tmp/p.html; grep -o '/document/[0-9]\{6,\}' /tmp/p.html | sort -u | head -5; grep -o 'documentId=[0-9]*' /tmp/p.html | sort -u | head -5; done
echo '=== 4 поисковые системы'
echo '--- ddg html'; g --data-urlencode "q=$Q" --data 'kl=ru-ru' 'https://html.duckduckgo.com/html/' | links
echo '--- ddg lite'; g --data-urlencode "q=$Q" 'https://lite.duckduckgo.com/lite/' | links
echo '--- mojeek'; g -G --data-urlencode "q=$Q" 'https://www.mojeek.com/search' | links
echo '--- brave'; g -G --data-urlencode "q=$Q" 'https://search.brave.com/search' | links
echo '--- bing'; g -G --data-urlencode "q=$Q" --data 'setlang=ru&cc=RU&mkt=ru-RU' 'https://www.bing.com/search' | links
echo '--- yandex'; g -G --data-urlencode "text=$Q" 'https://yandex.ru/search/' | links
echo '--- searx'; for h in searx.be search.sapti.me priv.au searx.tiekoetter.com; do echo "- $h"; g -G --data-urlencode "q=$Q" --data 'format=json&language=ru' "https://$h/search" | head -c 600; echo; done
echo '=== 5 wayback / ООН'
g 'https://archive.org/wayback/available?url=unece.org/DAM/trans/conventn/Conv_road_signs_2006v_RU.pdf'; echo
g 'https://web.archive.org/cdx/search/cdx?url=unece.org/DAM/trans/conventn/&matchType=prefix&collapse=urlkey&limit=400&fl=original,statuscode,length' | grep -i 'ru\|_r\.' | head -60
g 'https://web.archive.org/cdx/search/cdx?url=unece.org/fileadmin/DAM/trans/conventn/&matchType=prefix&collapse=urlkey&limit=400&fl=original,statuscode,length' | grep -i 'ru\|_r\.' | head -60
echo '--- un.org conventions list'; g 'https://www.un.org/ru/documents/decl_conv/conventions.shtml' | grep -i -o 'href="[^"]*"[^<]*<\?[^<]*дорожн[^<]*' | head; g 'https://www.un.org/ru/documents/decl_conv/conventions.shtml' | grep -i -c 'href'
