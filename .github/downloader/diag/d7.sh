#!/bin/bash
# Образцы страниц (для настройки печати) — сохраняются как есть
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
mkdir -p .work/diag/html
n=0
while IFS= read -r u; do [ -z "$u" ] && continue; n=$((n+1))
  curl -sS -L --connect-timeout 15 --max-time 90 -A "$UA" -H 'Accept-Language: ru-RU,ru;q=0.9' -o ".work/diag/html/$n.html" -w "$n %{http_code} %{size_download} %{content_type} %{url_effective}\n" "$u"; sleep 1
done <<'URLS'
https://base.garant.ru/72246274/
https://base.garant.ru/72246274/53f89421bbdaf741eb2d1ecc4ddb4c33/
https://meganorm.ru/mega_doc/norm/akt_forma/1/instruktsiya_o_poryadke_zakaza_raspredeleniya_khraneniya.html
https://meganorm.ru/mega_doc/dop_norm/0/instruktsiya_o_poryadke_zakaza_raspredeleniya_khraneniya/0/prikaz_mvd_rossii_ot_01_06_2017_N_336_s_izm_ot_27_08_2024_o.html
https://eccis.org/document/700
https://meganorm.ru/mega_doc/norm/gost-r_gosudarstvennyj-standart/1/gost_r_51256-2018_natsionalnyy_standart_rossiyskoy.html
https://legalacts.ru/doc/prikaz-genprokuratury-rf-ot-15022011-n-33/
https://base.garant.ru/70675376/
https://base.garant.ru/72264624/
https://base.garant.ru/72148844/
https://mvd.consultant.ru/documents/search?q=%D0%BF%D1%80%D0%BE%D0%BF%D0%B0%D0%B3%D0%B0%D0%BD%D0%B4%D0%B5
https://meganorm.ru/mega_doc/dop1/64/prikaz_mvd_rossii_ot_20_06_2012_N_615_s_izm_ot_20_09_2022_ob_megainfo/0/prikaz_mvd_rossii_ot_02_09_2024_N_515_ob_utverzhdenii.html
URLS
curl -sS -L --max-time 120 -A "$UA" -o /tmp/903.pdf 'https://ddtks.ru/files/documents/bdd/materialy/norm/2022_2023/14-prikaz-mvd-rf-n930-red.pdf'; pip install -q pypdf 2>/dev/null; python3 - <<'PY'
import pypdf
r=pypdf.PdfReader('/tmp/903.pdf'); print('ddtks 903: страниц',len(r.pages))
t=' '.join((r.pages[0].extract_text() or '').split()); print(t[:900])
t=' '.join((r.pages[-1].extract_text() or '').split()); print('…',t[-500:])
PY
for q in 'http://archive.org/wayback/available?url=xn--b1aew.xn--p1ai/mvd/structure1/Glavnie_upravlenija/%D0%B3%D1%83%D1%81%D0%B1/Polozhenie' 'http://archive.org/wayback/available?url=mvd.ru/mvd/structure1/Glavnie_upravlenija/gusb/Polozhenie' 'http://web.archive.org/cdx/search/cdx?url=xn--b1aew.xn--p1ai/mvd/structure1/Glavnie_upravlenija/*&filter=urlkey:.*olozhen.*&collapse=urlkey&limit=60&fl=timestamp,original,statuscode,length' 'http://web.archive.org/cdx/search/cdx?url=mvd.ru/mvd/structure1/Glavnie_upravlenija/*&filter=urlkey:.*olozhen.*&collapse=urlkey&limit=60&fl=timestamp,original,statuscode,length' 'http://web.archive.org/cdx/search/cdx?url=xn--b1aew.xn--p1ai/upload/site1/document_file/*&filter=urlkey:.*(903|515|propagand).*&collapse=urlkey&limit=40&fl=timestamp,original,statuscode,length'; do echo "--- $q"; curl -sS -L --max-time 120 "$q" | head -c 6000; echo; done
