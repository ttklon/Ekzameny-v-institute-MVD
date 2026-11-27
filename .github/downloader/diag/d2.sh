#!/bin/bash
# Проверка поисковых систем и поиска на сайтах-источниках
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 60 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
ch(){ timeout 90 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=15000 --user-agent="$UA" --dump-dom "$1" 2>/dev/null; }
cat > /tmp/links.py <<'PY'
import sys,re,html,urllib.parse,base64
s=sys.stdin.read(); print('bytes',len(s))
seen=[]
for h in re.findall(r'(?:href="|<link>)([^"<]+)',s):
    h=html.unescape(h)
    m=re.search(r'uddg=([^&]+)',h)
    if m: h=urllib.parse.unquote(m.group(1))
    m=re.search(r'[?&]u=a1([A-Za-z0-9_-]+)',h)
    if m:
        try: h=base64.urlsafe_b64decode(m.group(1)+'=='*1).decode('utf-8','replace')
        except Exception as e: pass
    if h.startswith('http') and not re.search(r'duckduckgo|mojeek|brave\.com|bing\.com|microsoft|yandex|google|yastatic|rambler|mail\.ru|startpage|w3\.org|gstatic|live\.com|msn\.com',h) and h not in seen: seen.append(h)
print('\n'.join(seen[:12]))
PY
L(){ python3 /tmp/links.py; }
enc(){ python3 -c "import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))" "$1"; }
for Q in 'приказ МВД России 29.12.2018 903 Наставление по организации деятельности Госавтоинспекции по пропаганде безопасности дорожного движения' 'ГОСТ Р 52766-2007 Дороги автомобильные общего пользования Элементы обустройства текст'; do
E=$(enc "$Q"); echo "######## $Q"
echo '--- bing rss'; g "https://www.bing.com/search?q=$E&format=rss&setlang=ru&cc=RU" | L
echo '--- bing html'; g "https://www.bing.com/search?q=$E&setlang=ru&cc=RU&mkt=ru-RU" | L
echo '--- rambler'; g "https://nova.rambler.ru/search?query=$E" | L
echo '--- mail'; g "https://go.mail.ru/search?q=$E" | L
echo '--- startpage'; g "https://www.startpage.com/do/search?q=$E&language=russian" | L
echo '--- ddg html GET'; g "https://html.duckduckgo.com/html/?q=$E&kl=ru-ru" > /tmp/d.html; L < /tmp/d.html; python3 -c "
import re,html;s=open('/tmp/d.html',errors='replace').read();print(' '.join(html.unescape(re.sub(r'<[^>]+>',' ',s)).split())[:300])"
echo '--- chrome ddg'; ch "https://duckduckgo.com/?q=$E&kl=ru-ru&ia=web" | L
echo '--- chrome brave'; ch "https://search.brave.com/search?q=$E" | L
echo '--- chrome google'; ch "https://www.google.com/search?q=$E&hl=ru" | L
echo '--- chrome yandex'; ch "https://yandex.ru/search/?text=$E&lr=213" | L
echo '--- chrome bing'; ch "https://www.bing.com/search?q=$E&setlang=ru&cc=RU" | L
done
echo '######## формы поиска на сайтах'
for u in 'https://sudact.ru/law/' 'https://base.garant.ru/' 'https://files.stroyinf.ru/' 'https://internet-law.ru/gosts/' 'https://meganorm.ru/' 'https://cis.minsk.by/reestrv2/' 'https://normativ.kontur.ru/' 'https://legalacts.ru/' 'https://www.garant.ru/products/ipo/prime/doc/72070432/' 'https://protect.gost.ru/' 'https://e-ecolog.ru/' 'https://gostassistent.ru/' 'https://dokipedia.ru/' 'https://rosgosts.ru/' 'https://docs.cntd.ru/document/1200062214' 'https://www.mvd.ru/' 'https://xn--b1aew.xn--p1ai/' 'https://xn--90adear.xn--p1ai/'; do echo "--- $u"; g -o /tmp/p.html -w '%{http_code} %{size_download} %{url_effective}\n' "$u"; python3 - <<'PY'
import re,html
s=open('/tmp/p.html','rb').read()
for enc in ('utf-8','cp1251'):
    try: t=s.decode(enc); break
    except Exception: t=s.decode('utf-8','replace')
m=re.search(r'<title>(.*?)</title>',t,re.S); print('title:',html.unescape(m.group(1)).strip()[:120] if m else '')
for f in re.findall(r'<form[^>]*>',t)[:6]: print('  ',f[:200])
for i in re.findall(r'<input[^>]*type="?(?:text|search)[^>]*>',t)[:6]: print('     ',i[:160])
PY
done
