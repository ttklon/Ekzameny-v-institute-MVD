#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 120 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
ch(){ timeout 120 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=20000 --user-agent="$UA" --dump-dom "$1" 2>/dev/null; }
mkdir -p .work/diag/html
cat > /tmp/tx.py <<'PY'
import sys,re,html
s=open(sys.argv[1],'rb').read()
t=None
for e in ('utf-8','cp1251'):
    try: t=s.decode(e); break
    except Exception: pass
if t is None: t=s.decode('utf-8','replace')
m=re.search(r'<title[^>]*>(.*?)</title>',t,re.S); print('   title:',' '.join(html.unescape(m.group(1)).split())[:300] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x))
for k in sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:3]: print('   …[%s] %s'%(k,x[max(0,mm.start()-200):mm.end()+300]))
PY
echo '--- consultant № 33'; g -o /tmp/a.html 'https://www.consultant.ru/document/cons_doc_LAW_113652/'; python3 /tmp/tx.py /tmp/a.html 'тратил\w* силу' 'Документ утратил'
echo '--- sudact № 754'; g -o /tmp/a.html 'https://sudact.ru/law/prikaz-genprokuratury-rossii-ot-01112025-n-754/'; python3 /tmp/tx.py /tmp/a.html 'N 33' 'оперативно-розыскн'
echo '--- pravo.ru 705'; g -o /tmp/a.html 'https://pravo.ru/news/210317/'; python3 /tmp/tx.py /tmp/a.html '705' 'дсп|ДСП|служебного пользования'
echo '--- wayback ГУСБ'
for q in 'http://web.archive.org/cdx/search/cdx?url=xn--b1aew.xn--p1ai/mvd/structure1/Glavnie_upravlenija/%D0%B3%D1%83%D1%81%D0%B1/Polozhenie*&fl=timestamp,original,statuscode,length&filter=statuscode:200&limit=-12' 'http://web.archive.org/cdx/search/cdx?url=mvd.ru/mvd/structure1/Glavnie_upravlenija/*&filter=urlkey:.*(gusb|%D0%B3%D1%83%D1%81%D0%B1).*&fl=timestamp,original,statuscode,length&limit=-12' 'http://web.archive.org/cdx/search/cdx?url=xn--b1aew.xn--p1ai/mvd/structure1/Glavnie_upravlenija/%D0%B3%D1%83%D1%81%D0%B1*&fl=timestamp,original,statuscode,length&filter=statuscode:200&collapse=urlkey&limit=40'; do echo "   $q"; g "$q" | head -c 5000; echo; done
g -o .work/diag/html/gusb.html 'http://web.archive.org/web/20250811110551id_/https://xn--b1aew.xn--p1ai/mvd/structure1/Glavnie_upravlenija/%D0%B3%D1%83%D1%81%D0%B1/Polozhenie?ysclid=lt4v5q5m97345087267'; python3 /tmp/tx.py .work/diag/html/gusb.html 'N 679' 'ред\.|редакци' 'изменени'
echo '--- 903 pdf'
pip install -q pypdf 2>/dev/null
for u in 'https://sch191spb.ru/wp-content/uploads/2025/05/prikaz-mvd-rf-o-deyatelnosti-gibdd-po-propagande-bdd.pdf' 'https://school536.ru/data/files/bezopasnost/normativ_pdd/17-%C2%ABob-utverzhdenii-nastavleniya-po-organizaczii-deyatelnosti-gosavtoinspekczii.pdf'; do g -o /tmp/x.pdf -w "   %{http_code} %{size_download} $u\n" "$u"; python3 - <<'PY'
import pypdf,re
try:
    r=pypdf.PdfReader('/tmp/x.pdf'); print('   страниц',len(r.pages))
    t=' '.join(' '.join((p.extract_text() or '') for p in r.pages).split()); print('   text',len(t)); print('   ',t[:700])
    for m in list(re.finditer(r'ред\. от|в ред\.|Дата сохранения|Список изменяющих',t))[:6]: print('   …',t[max(0,m.start()-80):m.end()+220])
except Exception as e: print('   ошибка',e)
PY
done
echo '--- e-ecolog 903'; ch 'https://e-ecolog.ru/docs/RypHIomzdnkBXjc-PIkxo' > .work/diag/html/eecolog903.html; python3 /tmp/tx.py .work/diag/html/eecolog903.html 'ред\. от' 'Список изменяющих' 'Дата сохранения'
python3 - <<'PY'
import re
t=open('.work/diag/html/eecolog903.html',errors='replace').read()
print('   divs:',sorted(set(re.findall(r'<(?:div|article|main|section)[^>]*class="([^"]*)"',t)))[:60])
print('   ссылки:',len(set(re.findall(r'href="(/docs/RypHIomzdnkBXjc-PIkxo/\d+)"',t))))
PY
echo '--- zakonbase 903'; g -o /tmp/a.html 'https://zakonbase.ru/content/part/385014'; python3 /tmp/tx.py /tmp/a.html 'ред\. от' 'N 903'
echo '--- prg.kz 660'; g -o /tmp/a.html 'https://prg.kz/document/?doc_id=31576719'; python3 /tmp/tx.py /tmp/a.html 'психологической работы' 'изменени'
echo '--- yurpsy 660'; g -o /tmp/a.html 'https://yurpsy.com/files/xrest/9/03.htm'; python3 /tmp/tx.py /tmp/a.html 'N 660'
echo '--- informio 515'; g -o /tmp/a.html 'https://www.informio.ru/update/wuz/70432'; python3 /tmp/tx.py /tmp/a.html 'Инструкци'
for n in 903 515 660 679 424 336; do echo "--- mvd.consultant.ru number=$n"; g -o /tmp/a.html "https://mvd.consultant.ru/documents/search?number=$n&numberexactcheck=true"; python3 - <<'PY'
import re,html
t=open('/tmp/a.html',errors='replace').read()
for h,x in re.findall(r'<a[^>]*href="(/documents/\d+[^"]*)"[^>]*>(.*?)</a>',t,re.S)[:8]:
    print('  ',h,' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())[:170])
PY
done
