#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
mkdir -p .work/diag/html
cat > /tmp/tx.py <<'PY'
import sys,re,html
s=open(sys.argv[1],'rb').read(); t=None
for e in ('utf-8','cp1251'):
    try: t=s.decode(e); break
    except Exception: pass
if t is None: t=s.decode('utf-8','replace')
m=re.search(r'<title[^>]*>(.*?)</title>',t,re.S); print('   title:',' '.join(html.unescape(m.group(1)).split())[:600] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x),'| ОБРЕЗАНО' if 'truncated-600 invisible' in t else '')
for k in sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:4]: print('   …[%s] %s'%(k,x[max(0,mm.start()-250):mm.end()+450]))
PY
n=0
p(){ n=$((n+1)); echo "--- [$n] $1"; g -o .work/diag/html/q$n.html -w '   HTTP %{http_code} %{size_download} %{content_type}\n' "$1"; shift; python3 /tmp/tx.py .work/diag/html/q$n.html "$@"; }
p 'https://www.consultant.ru/document/cons_doc_LAW_544784/' 'утратившим силу' 'от 15\.02\.2011' 'Документ утратил'
p 'https://pravo.ppt.ru/prikaz/genprokuratura/n-455-354891' 'утратившим силу' 'N 33'
p 'https://pravo.ppt.ru/prikaz/genprokuratura/n-454-354971' 'утратившим силу'
p 'https://base.garant.ru/414444041/' 'утратившим силу'
p 'https://pravo.ppt.ru/prikaz/genprokuratura' '2026 N \d+'
p 'https://logoslab.ru/library/ukaz-prezidenta-rf-o-natsionalnom-plane-protivodejstvija-korruptsii-na-2025-2028-gody.html' 'Указ\w* Президента[^.]{0,80}от \d[^.]{0,60}' '2025.2028'
p 'https://www.consultant.ru/law/podborki/nacionalnyj_plan_protivodejstviya_korrupcii_na_ocherednoj_period_utverzhden/' 'Указ Президента РФ от \d\d\.\d\d\.202[4-6] N \d+'
p 'https://pravo.ppt.ru/prikaz/mvd/n-422-350035'
echo '=== ips'
for q in 'Национальный план противодействия коррупции' 'Указ Президента Российской Федерации от 06.10.2025 № 709'; do echo "--- $q"; e=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote_plus(sys.argv[1]))' "$q"); g "http://ips.pravo.gov.ru/api/ips/legislation/search.json?query=$e&limit=10&page=1" -o /tmp/i.json; python3 - <<'PY'
import json
try:
    d=json.load(open('/tmp/i.json',encoding='utf-8'))
    it=d.get('items') if isinstance(d,dict) else d
    print('   ключи',list(d.keys())[:8] if isinstance(d,dict) else type(d))
    for i in (it or [])[:10]: print('  ',{k:str(v)[:150] for k,v in i.items() if k in ('adoption','name','title','state','nd','head')})
except Exception as e: print('   ошибка',e, open('/tmp/i.json',errors='replace').read()[:300])
PY
done
