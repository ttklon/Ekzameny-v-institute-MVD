import re
def norm(s):
    s=s.lower().replace('ё','е')
    s=re.sub(r'@@ \d+ \|',' ',s)
    s=re.sub(r'(?<=[а-яa-z])[-­]\s+(?=[а-яa-z])','',s)
    s=re.sub(r'[^0-9a-zа-я]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()
