#!/bin/bash
# подбор адресов текстов: ГОСТ Р 57145-2016 на meganorm.ru; приказы МВД России № 1045, № 77 на docs.cntd.ru
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
for p in 1 2 3; do
  echo "== meganorm pravila_$p"
  curl -sL -m 40 -A "$UA" "https://meganorm.ru/mega_doc/norm/pravila/pravila_$p.html" | iconv -f cp1251 -t utf-8 -c 2>/dev/null | tr '\n' ' ' | grep -o '<a[^>]*href="[^"]*"[^>]*>[^<]*\(57145\|52605\|52282\|58653\)[^<]*' | head -5
done
echo "== cntd 1045"
curl -sL -m 40 -A "$UA" -o /tmp/c1.html -w '%{http_code} %{size_download}\n' "https://docs.cntd.ru/document/499078196"
python3 - <<'PY'
import re,html
s=open('/tmp/c1.html',encoding='utf-8',errors='replace').read()
t=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style).*?</\1>',' ',s,flags=re.S))).split())
print(len(t)); i=t.find('Общие положения'); print(t[:300]); print('...'); print(t[i:i+500]); print('...'); print(t[-600:])
for w in ('подписк','демонстрац','Полный текст','доступ ограничен','редакци'):
    print(w, t.count(w))
PY
