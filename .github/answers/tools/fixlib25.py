"""fixlib25.py — помощники ручной правки при полной проверке: ins (вернуть строку из 30db505 после указанной),
rep (заменить фрагмент), dele (удалить строку), old (текст 30db505). Импортируется, сам не запускается."""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(os.path.join(HERE, '..'))
import normfixB25 as B
def old(q): return subprocess.run(['git', 'show', '30db505:.github/answers/adp2/q%03d.txt' % q], capture_output=True, text=True).stdout.split('\n')
def _one(L, pref, what='строка'):
    k = [i for i, l in enumerate(L) if l.startswith(pref)]
    assert len(k) == 1, '%s «%s»: найдено %d' % (what, pref[:40], len(k)); return k[0]
def ins(q, oldpref, after, blank=True, text=None):
    """после строки, начинающейся с after, вставить строку 30db505, начинающуюся с oldpref (или text)"""
    L = B.rd(q); new = text if text is not None else old(q)[_one(old(q), oldpref, 'старая')]
    assert new not in L, 'уже есть'
    i = _one(L, after); L[i + 1:i + 1] = (['', new] if blank else [new]); B.wr(q, L); print('q%03d + %s' % (q, new[:70]))
def rep(q, a, b, cnt=1):
    p = 'adp2/q%03d.txt' % q; t = open(p, encoding='utf-8').read(); assert t.count(a) == cnt, 'q%03d «%s»: %d' % (q, a[:40], t.count(a))
    open(p, 'w', encoding='utf-8').write(t.replace(a, b)); print('q%03d ~ %s' % (q, a[:50]))
def dele(q, pref):
    L = B.rd(q); i = _one(L, pref); del L[i]
    if 0 < i < len(L) and L[i] == '' and L[i - 1] == '': del L[i]
    B.wr(q, L); print('q%03d − %s' % (q, pref[:60]))
