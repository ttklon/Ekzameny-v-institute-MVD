#!/bin/bash
# поиск: DuckDuckGo через headless Chrome; вход — файл с запросами (по одному в строке)
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
while IFS= read -r q; do
  [ -z "$q" ] && continue
  echo "######## $q"
  enc=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$q")
  timeout 90 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=15000 --user-agent="$UA" --dump-dom "https://duckduckgo.com/?q=$enc&kl=ru-ru&ia=web" 2>/dev/null > /tmp/ddg.html
  python3 - <<'PY'
import re,html
t=open('/tmp/ddg.html',errors='replace').read()
seen=set()
for m in re.finditer(r'<a[^>]*data-testid="result-title-a"[^>]*>',t):
    h=re.search(r'href="([^"]+)"',m.group(0))
    if not h or h.group(1) in seen: continue
    seen.add(h.group(1)); e=t.find('</a>',m.end())
    print(html.unescape(h.group(1))+'\t'+' '.join(html.unescape(re.sub(r'<[^>]+>',' ',t[m.end():e])).split())[:160])
print('bytes',len(t))
PY
  sleep 4
done < "$1"
