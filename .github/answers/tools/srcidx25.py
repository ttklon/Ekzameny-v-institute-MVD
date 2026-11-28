#!/usr/bin/env python3
"""srcidx25.py OUT DIR… — строит указатель текстов источников для srcsent25.py (нужен numpy).
DIR — папки с текстами (*.txt, создаются extract_src.py; для литературы — таким же извлечением из PDF).
Текст режется на отрезки по 80 основ; для каждой основы запоминается, в каких отрезках она есть.
Для актов запоминается, к какой статье относится отрезок (заголовки «Статья N.»)."""
import sys, os, re, glob, pickle
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import srctok25 as K
W = 80
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
vocab = {}; T = []; names = []; foff = [0]; cfile = []; cart = []; cstart = []; arts = ['']; artid = {'': 0}
for d in sys.argv[2:]:
    for f in sorted(glob.glob(os.path.join(d, '*.txt'))):
        segs = K.segments(f)
        ids = []; cs = []; ca = []
        for a, txt in segs:
            tk = K.tokens(txt)
            if not tk: continue
            if a not in artid: artid[a] = len(arts); arts.append(a)
            for c0 in range(0, len(tk), W): cs.append(len(ids) + c0); ca.append(artid[a])   # отрезок не переходит границу статьи
            for w in tk:
                i = vocab.get(w)
                if i is None: i = vocab[w] = len(vocab)
                ids.append(i)
        if not ids: continue
        fi = len(names); names.append(os.path.basename(f)); base = foff[-1]; T.append(np.array(ids, dtype=np.int32)); foff.append(base + len(ids))
        cstart += [base + c for c in cs]; cfile += [fi] * len(cs); cart += ca
T = np.concatenate(T); N = len(T)
cstart = np.array(cstart, dtype=np.int64); C = len(cstart)
chunk_of = np.searchsorted(cstart, np.arange(N, dtype=np.int64), side='right') - 1
key = T.astype(np.int64) * C + chunk_of; del chunk_of
key = np.unique(key); pid = (key // C).astype(np.int32); pch = (key % C).astype(np.int32); del key
V = len(vocab); poff = np.searchsorted(pid, np.arange(V + 1, dtype=np.int32)).astype(np.int64)
np.save(os.path.join(out, 'T.npy'), T); np.save(os.path.join(out, 'pch.npy'), pch); np.save(os.path.join(out, 'poff.npy'), poff)
np.save(os.path.join(out, 'cstart.npy'), cstart); np.save(os.path.join(out, 'cfile.npy'), np.array(cfile, dtype=np.int32)); np.save(os.path.join(out, 'cart.npy'), np.array(cart, dtype=np.int32))
pickle.dump({'vocab': vocab, 'names': names, 'foff': foff, 'arts': arts, 'W': W}, open(os.path.join(out, 'meta.pkl'), 'wb'))
print('файлов', len(names), 'основ в тексте', N, 'разных', V, 'отрезков', C, 'статей', len(arts))
