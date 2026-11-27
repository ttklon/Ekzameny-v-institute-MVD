#!/bin/bash
# Что отдают найденные страницы: размер, заголовок, объём текста, признаки неполного текста
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
cat > /tmp/pg.py <<'PY'
import sys,re,html
s=open(sys.argv[1],'rb').read()
if s[:4]==b'%PDF': print('   PDF',len(s)); sys.exit()
t=None
for enc in ('utf-8','cp1251'):
    try: t=s.decode(enc); break
    except Exception: pass
if t is None: t=s.decode('utf-8','replace')
m=re.search(r'<title>(.*?)</title>',t,re.S); print('   title:',html.unescape(m.group(1)).strip()[:200] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x))
for k in sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:3]: print('   …',x[max(0,mm.start()-120):mm.end()+200])
for h in sorted(set(re.findall(r'href="([^"]*(?:%s)[^"]*)"'%(sys.argv[2] if len(sys.argv)>2 else 'zzzz'),t)))[:0]: print('   ->',h)
PY
p(){ u="$1"; shift; echo "--- $u"; curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' -o /tmp/p.bin -w '   %{http_code} %{size_download} %{content_type} %{url_effective}\n' "$u"; python3 /tmp/pg.py /tmp/p.bin "$@"; }
p 'https://base.garant.ru/72148844/' 'редакци' 'изменениями' 'Информация об изменениях' 'полный текст'
python3 - <<'PY'
import re
t=open('/tmp/p.bin','rb').read().decode('cp1251','replace')
print('   ссылки на части:',sorted(set(re.findall(r'href="(/72148844/[^"#]+)',t)))[:40])
PY
p 'https://base.garant.ru/12167124/' 'ГОСТ Р 52766'
p 'https://e-ecolog.ru/docs/RypHIomzdnkBXjc-PIkxo' 'редакци' 'Наставлени'
p 'https://files.stroyinf.ru/Data2/1/4293835/4293835927.pdf'
p 'https://files.stroyinf.ru/Data1/52/52321/' 'ГОСТ Р 52766' 'Изменени'
p 'https://meganorm.ru/mega_doc/norm_update_01022025/gost-r_gosudarstvennyj-standart/0/gost_r_52766-2007_natsionalnyy_standart_rossiyskoy.html' 'Изменени' 'редакци'
p 'https://ddtks.ru/files/documents/bdd/materialy/norm/2022_2023/14-prikaz-mvd-rf-n930-red.pdf'
p 'https://www.un.org/ru/documents/decl_conv/conventions/dip_rel.shtml' 'дипломатическ'
p 'https://www.un.org/ru/documents/decl_conv/conventions/consular.shtml' 'консульск'
p 'https://www.un.org/ru/documents/decl_conv/conventions/consular_relations.shtml' 'консульск'
echo '--- un.org перечень'; curl -sS -L --max-time 60 -A "$UA" 'https://www.un.org/ru/documents/decl_conv/conventions.shtml' | python3 -c "
import sys,re,html
t=sys.stdin.read()
for h,x in re.findall(r'<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>',t,re.S):
    x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())
    if re.search(r'дипломатическ|консульск|знак|дорожн',x): print('  ',h,x[:120])"
echo '--- garant поиск'; curl -sS -L --max-time 60 -A "$UA" --data-urlencode 'text=приказ МВД России от 2 сентября 2024 г. N 515' 'https://base.garant.ru/search/' -o /tmp/s.bin -w '   %{http_code} %{size_download} %{url_effective}\n'; python3 - <<'PY'
import re,html
t=open('/tmp/s.bin','rb').read()
for enc in ('utf-8','cp1251'):
    try: t=t.decode(enc); break
    except Exception: pass
if isinstance(t,bytes): t=t.decode('utf-8','replace')
n=0
for h,x in re.findall(r'<a[^>]*href="(/\d+/)"[^>]*>(.*?)</a>',t,re.S):
    x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',x)).split())
    if x: print('  ',h,x[:160]); n+=1
    if n>14: break
PY
echo '--- cis.minsk.by'; curl -sS -L --max-time 60 -A "$UA" 'https://cis.minsk.by/reestrv2/' | python3 -c "
import sys,re
t=sys.stdin.read(); print(re.findall(r'<form[^>]*>',t)[:5]); print(re.findall(r'<input[^>]*>',t)[:10]); print(sorted(set(re.findall(r'href=\"([^\"]+)\"',t)))[:40]); print(re.findall(r'src=\"([^\"]+\.js[^\"]*)\"',t)[:10])"
