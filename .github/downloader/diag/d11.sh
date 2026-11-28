#!/bin/bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
g(){ curl -sS -L --connect-timeout 15 --max-time 120 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' "$@"; }
ch(){ timeout 150 google-chrome --headless=new --no-sandbox --disable-gpu --lang=ru-RU --virtual-time-budget=25000 --user-agent="$UA" --dump-dom "$1" 2>/dev/null; }
mkdir -p .work/diag/html
cat > /tmp/tx.py <<'PY'
import sys,re,html
t=open(sys.argv[1],'rb').read().decode('utf-8','replace')
m=re.search(r'<title[^>]*>(.*?)</title>',t,re.S); print('   title:',' '.join(html.unescape(m.group(1)).split())[:300] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x))
for k in sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:int(4)]: print('   …[%s] %s'%(k,x[max(0,mm.start()-250):mm.end()+350]))
PY
echo '--- prg.kz 660 (chrome)'; ch 'https://prg.kz/document/?doc_id=31576719' > .work/diag/html/prg660.html; python3 /tmp/tx.py .work/diag/html/prg660.html 'Положение об основах организации психологической работы в органах внутренних дел Российской Федерации I' 'Порядок ведения служебной документации' 'Министр'
python3 - <<'PY'
import re
t=open('.work/diag/html/prg660.html',errors='replace').read()
from collections import Counter
print('   классы:',Counter(re.findall(r'<(?:div|article|main|section)[^>]*class="([^"]*)"',t)).most_common(25))
PY
echo '--- consultant подборка ОРД'; g -o /tmp/a.html 'https://www.consultant.ru/law/podborki/prikaz_generalnogo_prokurora_operativno-rozysknoj/'; python3 /tmp/tx.py /tmp/a.html 'Приказ Генпрокуратуры России от \d\d\.\d\d\.202[3-6] N \d+'
echo '--- consultant № 33 справка'; ch 'https://www.consultant.ru/document/cons_doc_LAW_113652/' > /tmp/b.html; python3 /tmp/tx.py /tmp/b.html 'тратил\w* силу (с|в связи)' 'в связи с изданием'
for u in 'https://www.consultant.ru/document/cons_doc_LAW_113652/2ff7a8c72de3994f30496a0ccbb1ddafdaddf518/' 'https://sudact.ru/law/prikaz-genprokuratury-rf-ot-15022011-n-33/' 'https://rulaws.ru/acts/Prikaz-Genprokuratury-Rossii-ot-15.02.2011-N-33/'; do echo "--- $u"; g -o /tmp/a.html "$u"; python3 /tmp/tx.py /tmp/a.html 'тратил\w* силу (с|в связи)' 'в связи с изданием'; done
echo '--- 903 school536'; g -o /tmp/x.pdf 'https://school536.ru/data/files/bezopasnost/normativ_pdd/17-%C2%ABob-utverzhdenii-nastavleniya-po-organizaczii-deyatelnosti-gosavtoinspekczii.pdf'; pip install -q pypdf 2>/dev/null; python3 - <<'PY'
import pypdf,re
r=pypdf.PdfReader('/tmp/x.pdf'); t=' '.join(' '.join((p.extract_text() or '') for p in r.pages).split())
for m in list(re.finditer(r'с изменениями|Редакция|редакци|Внимание|Страница 8|Министр',t))[:10]: print('   …',t[max(0,m.start()-120):m.end()+200])
print('   КОНЕЦ:',t[-500:])
PY
