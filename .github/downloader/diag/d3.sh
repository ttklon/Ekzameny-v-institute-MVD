#!/bin/bash
# Поиск адресов недостающих актов: DuckDuckGo через Chrome. Аргумент — файл с запросами (по одному в строке).
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
ch(){ timeout 90 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=15000 --user-agent="$UA" --dump-dom "$1" 2>/dev/null; }
cat > /tmp/res.py <<'PY'
import sys,re,html,urllib.parse
s=sys.stdin.read(); out=[]
for m in re.finditer(r'<a[^>]*data-testid="result-title-a"[^>]*>(.*?)</a>',s,re.S):
    h=re.search(r'href="([^"]+)"',m.group(0)); t=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',m.group(1))).split())
    if h: out.append(html.unescape(h.group(1))+'\t'+t[:150])
if not out:
    for h in re.findall(r'href="([^"]+)"',s):
        h=html.unescape(h); m=re.search(r'uddg=([^&]+)',h)
        if m: h=urllib.parse.unquote(m.group(1))
        if h.startswith('http') and 'duckduckgo' not in h and h not in out: out.append(h)
print('bytes',len(s)); print('\n'.join(out[:14]))
PY
while IFS= read -r Q; do
  [ -z "$Q" ] && continue
  E=$(python3 -c "import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))" "$Q")
  echo "######## $Q"
  ch "https://duckduckgo.com/?q=$E&kl=ru-ru&ia=web" > /tmp/r.html
  python3 /tmp/res.py < /tmp/r.html
  if ! grep -q 'result-title-a' /tmp/r.html; then sleep 20; ch "https://duckduckgo.com/?q=$E&kl=ru-ru&ia=web" | python3 /tmp/res.py; fi
  sleep 6
done < "$1"
