import re
ABBR = {'ст','гл','см','др','пп','им','ул','абз','руб','тыс','млн','подп','разд','прим','кв','стр','т','е','д','п','ч','г','н','рис','табл','напр','утв','ред','коп','час','мин','сут','мес','лит','ср'}
def split_sents(s):
    """Делит строку на предложения вне «», //…// и **…**. Возвращает список кусков (с пробелами в конце)."""
    cuts = []; depth = 0; i = 0; n = len(s); inref = False; inb = False
    while i < n:
        c = s[i]
        if s.startswith('//', i): inref = not inref; i += 2; continue
        if s.startswith('**', i): inb = not inb; i += 2; continue
        if c == '«': depth += 1
        elif c == '»': depth = max(0, depth - 1)
        elif c in '.!?' and depth == 0 and not inref and not inb and i + 2 < n and s[i + 1] == ' ' and (s[i + 2].isupper() or s[i + 2] in '«') :
            m = re.search(r'([A-Za-zА-Яа-яЁё]+)$', s[:i])
            w = m.group(1) if m else ''
            if not (c == '.' and (w.lower() in ABBR or (len(w) == 1 and w.isupper()))):
                cuts.append(i + 2)
        i += 1
    out = []; p = 0
    for c in cuts:
        out.append(s[p:c]); p = c
    out.append(s[p:])
    return out
