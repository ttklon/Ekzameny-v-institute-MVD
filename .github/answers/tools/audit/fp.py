import sys,glob,re; sys.path.insert(0,'/home/user/Ekzameny-v-institute-MVD/.github/answers/tools/audit'); import lawtext as L
def g(h): return glob.glob('/tmp/s_adp/%s*'%h)[0]
def fp(h,label,kw,n=260,pre=0):
    """label — как напечатано в начале пункта ('8.4.', '7)', 'д)'); kw — основа слова, которое должно быть рядом"""
    t=re.sub(r'\s+',' ',L.text(g(h))); out=0
    for m in re.finditer(r'(?<![\d.])'+re.escape(label)+r' ?',t):
        seg=t[m.start():m.start()+700]
        if kw.lower() in seg.lower():
            print('[%s %s]'%(h,label), t[max(0,m.start()-pre):m.start()+n]); out+=1
            if out>=2: break
    if not out: print('[%s %s] — нет рядом «%s»; всего меток: %d'%(h,label,kw,len(re.findall(r'(?<![\d.])'+re.escape(label),t))))
