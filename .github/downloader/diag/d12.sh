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
m=re.search(r'<title[^>]*>(.*?)</title>',t,re.S); print('   title:',' '.join(html.unescape(m.group(1)).split())[:260] if m else '')
x=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',t,flags=re.S))).split())
print('   text',len(x),'| paywall' if 'Откройте актуальную версию' in x or 'демонстрационном режиме' in x else '')
for k in sys.argv[2:]:
    for mm in list(re.finditer(k,x))[:3]: print('   …[%s] %s'%(k,x[max(0,mm.start()-200):mm.end()+300]))
print('   КОНЕЦ:',x[-380:])
PY
n=0
p(){ n=$((n+1)); echo "--- [$n] $1"; g -o .work/diag/html/p$n.html -w '   HTTP %{http_code} %{size_download}\n' "$1"; shift; python3 /tmp/tx.py .work/diag/html/p$n.html "$@"; }
p 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-02.09.2013-N-660/' 'ред\. от'
p 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-02.01.2013-N-1/' 'ред\. от'
p 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-02.09.2024-N-515/' 'ред\. от|с изм'
p 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-30.06.2026-N-424/'
p 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-29.12.2018-N-903/' 'ред\. от'
p 'https://rulaws.ru/acts/Prikaz-MVD-Rossii-ot-16.06.2011-N-679/' 'ред\. от'
p 'https://lawnotes.ru/npa/prikaz-mvd-rossii-ot-02.09.2013-n-660' 'ред\. от'
p 'https://lawnotes.ru/npa/prikaz-mvd-rossii-ot-02.01.2013-n-1' 'ред\. от'
p 'https://lawnotes.ru/npa/prikaz-mvd-rossii-ot-02.09.2024-n-515' 'ред\. от|с изм'
p 'https://lawnotes.ru/npa/prikaz-mvd-rossii-ot-29.12.2018-n-903' 'ред\. от'
p 'https://lawnotes.ru/npa/prikaz-mvd-rossii-ot-30.06.2026-n-424'
p 'https://yurpsy.com/files/xrest/9/03.htm' 'в ред\.' 'N 660'
p 'https://legalacts.ru/doc/venskaja-konventsija-o-konsulskikh-snoshenijakh-zakliuchena-v/' 'Статья 79'
p 'https://helpiks.org/9-14116.html' 'Концепци'
echo '=== wayback garant'
for u in 'base.garant.ru/72246274/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'base.garant.ru/72246274/' 'base.garant.ru/70675376/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'base.garant.ru/70675376/' 'base.garant.ru/72148844/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'base.garant.ru/411260623/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'base.garant.ru/77663768/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'docs.cntd.ru/document/552052053'; do
  echo "--- cdx $u"; g "http://web.archive.org/cdx/search/cdx?url=$u&fl=timestamp,statuscode,length&filter=statuscode:200&limit=-6" | tr '\n' ';'; echo
done
for u in 'http://web.archive.org/web/2019id_/https://base.garant.ru/72246274/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'http://web.archive.org/web/2018id_/https://base.garant.ru/70675376/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'http://web.archive.org/web/2023id_/https://base.garant.ru/70675376/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'http://web.archive.org/web/2026id_/https://base.garant.ru/72148844/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'http://web.archive.org/web/2026id_/https://base.garant.ru/77663768/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'https://base.garant.ru/77663768/53f89421bbdaf741eb2d1ecc4ddb4c33/' 'https://base.garant.ru/77663768/'; do p "$u" 'С изменениями и дополнениями от:? ?[^А-Я]{0,120}' 'Информация об изменениях'; done
echo '=== sudact поиск № 33'
p 'https://sudact.ru/law/doc/?law-txt=&law-law_number=&law-date_from=01.01.2024&law-date_to=28.11.2026&law-name=%D0%BE%D0%BF%D0%B5%D1%80%D0%B0%D1%82%D0%B8%D0%B2%D0%BD%D0%BE-%D1%80%D0%BE%D0%B7%D1%8B%D1%81%D0%BA%D0%BD%D0%BE%D0%B9' 'Генпрокуратуры России от \d\d\.\d\d\.202\d N \d+'
p 'https://www.consultant.ru/law/podborki/prikaz_generalnogo_prokurora_operativno-rozysknoj/' 'Приказ Генпрокуратуры России от \d\d\.\d\d\.\d{4} N \d+'
