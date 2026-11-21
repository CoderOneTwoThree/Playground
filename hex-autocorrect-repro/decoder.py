"""Faithful Python port of ios/HEXShared/FullKeyboard/TypingDecoder.swift `decide`
(model reader, whole-word beam search, splitReadings) to reproduce the missed-space bug.
Taps are placed at key centres of a QWERTY grid (pitch 1x1)."""
import struct, math, sys

class Model:
    def __init__(self, path):
        d = open(path, 'rb').read(); self.d = d
        u32 = lambda at: struct.unpack_from('<I', d, at)[0]
        assert u32(0) == 0x4D545848 and u32(4) == 3
        W, B, blob, L = u32(8), u32(12), u32(16), u32(20)
        self.W, self.B = W, B
        self.codes, self.chars, self.base = {}, [' '] * (L + 1), [0] * (L + 1)
        for i in range(L):
            at = 28 + 8 * i
            ch = chr(u32(at)); code = d[at + 4]; bc = d[at + 5]
            self.codes[ch] = code; self.chars[code] = ch; self.base[code] = bc
        self.apos = self.codes.get("'")
        self.offsetsAt = 28 + 8 * L
        self.unigramAt = self.offsetsAt + 4 * (W + 1)
        rows = self.unigramAt + W; rows += (4 - rows % 4) % 4
        self.rowsAt = rows; self.pwAt = rows + 4 * (W + 1); self.pcAt = self.pwAt + 4 * B
        self.blobAt = self.pcAt + B
        assert self.blobAt + blob == len(d)
        import array
        self.off = array.array('I'); self.off.frombytes(d[self.offsetsAt:self.offsetsAt + 4 * (W + 1)])
        self.rows = array.array('I'); self.rows.frombytes(d[rows:rows + 4 * (W + 1)])
        self.pw = array.array('I'); self.pw.frombytes(d[self.pwAt:self.pwAt + 4 * B])
    def length(self, i): return self.off[i + 1] - self.off[i]
    def byte(self, i, depth):
        s = self.off[i]
        return self.d[self.blobAt + s + depth] if depth < self.off[i + 1] - s else -1
    def word(self, i): return ''.join(self.chars[self.d[self.blobAt + k]] for k in range(self.off[i], self.off[i + 1]))
    def encode(self, w):
        try: return [self.codes[c] for c in w]
        except KeyError: return None
    def uni(self, i): return self.d[self.unigramAt + i] / 8
    def bigram(self, a, b):
        lo, end = self.rows[a], self.rows[a + 1]; hi = end
        while lo < hi:
            m = (lo + hi) // 2
            if self.pw[m] < b: lo = m + 1
            else: hi = m
        if lo < end and self.pw[lo] == b: return self.d[self.pcAt + lo] / 8
        return None
    def narrow(self, lo, hi, depth, t):
        a, b = lo, hi
        while a < b:
            m = (a + b) // 2
            if self.byte(m, depth) < t: a = m + 1
            else: b = m
        c, e = a, hi
        while c < e:
            m = (c + e) // 2
            if self.byte(m, depth) <= t: c = m + 1
            else: e = m
        return a, c
    def index_codes(self, codes):
        lo, hi = 0, self.W
        for depth, b in enumerate(codes):
            lo, hi = self.narrow(lo, hi, depth, b)
            if lo >= hi: return None
        return lo if self.length(lo) == len(codes) else None
    def index(self, w):
        c = self.encode(w); return None if c is None else self.index_codes(c)

P = dict(sigmaX=0.29, sigmaY=0.26, lmWeight=1.5, deletionCost=7.0, insertionCost=7.0, transpositionCost=5.0,
         spaceOmissionCost=6.0, maxEdits=1, beam=48, autoMargin=2.0, validMargin=7.0, unknownValidCost=15.0,
         unknownCost=22.0, maxTapCost=9.0, oneLetterWordCost=7.0)

ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
CENTRES = {}
for r, (row, x0) in enumerate(zip(ROWS, [0.0, 0.5, 1.5])):
    for i, ch in enumerate(row): CENTRES[ch] = (x0 + i, float(r))

class Decoder:
    def __init__(self, m, **over):
        self.m = m; self.p = dict(P, **over)
        self.cent = [None] * len(m.chars)
        for ch, pt in CENTRES.items():
            if ch in m.codes: self.cent[m.codes[ch]] = pt
    def lm(self, w, prev):
        back = 0.92 + self.m.uni(w)
        if prev is None: return back
        b = self.m.bigram(prev, w)
        return back if b is None else min(b, back)
    def tapcosts(self, pt):
        sx, sy = self.p['sigmaX'], self.p['sigmaY']
        out = []
        for c in self.cent:
            if c is None: out.append(math.inf); continue
            dx = (pt[0] - c[0]) / sx; dy = (pt[1] - c[1]) / sy
            out.append(0.5 * (dx * dx + dy * dy))
        raw = list(out)
        for code in range(1, len(out)):
            b = self.m.base[code]
            if b != code and math.isfinite(raw[b]): out[code] = min(raw[code], raw[b] + 1.0)
        best = min(x for x in out if math.isfinite(x))
        return [x - best for x in out]
    def search(self, costs, rng, limit, maxEdits):
        m, p = self.m, self.p
        n = len(rng); maxDepth = n + maxEdits + 2
        layers = [[] for _ in range(maxDepth + 2)]
        layers[0] = [(0, m.W, 0, 0, 0.0)]
        found = {}
        choices = [sorted([(c, v) for c, v in enumerate(costs[i]) if c > 0 and v <= p['maxTapCost']], key=lambda t: t[1]) for i in rng]
        extra = []
        if maxEdits:
            for t in range(len(choices)):
                if not choices[t]: extra.append(p['insertionCost']); continue
                key = m.base[choices[t][0][0]]; same = False
                for nb in (t - 1, t + 1):
                    if 0 <= nb < len(choices) and choices[nb] and m.base[choices[nb][0][0]] == key: same = True
                if same: extra.append(p['insertionCost']); continue
                gap = next((v for c, v in choices[t] if m.base[c] != key), p['maxTapCost'])
                extra.append(p['insertionCost'] + min(4, gap))
        allc = [c for c in range(1, len(m.chars)) if c != m.apos]
        for depth in range(maxDepth + 1):
            layer = layers[depth]
            if len(layer) > p['beam']:
                layer.sort(key=lambda s: s[4]); del layer[p['beam']:]
            k = 0
            while k < len(layer):
                lo, hi, tap, ed, cost = layer[k]; k += 1
                if tap == n and m.length(lo) == depth:
                    if cost < found.get(lo, math.inf): found[lo] = cost
                if depth >= maxDepth: continue
                def push(code, nt, e, c):
                    a, b = m.narrow(lo, hi, depth, code)
                    if a < b: layers[depth + 1].append((a, b, nt, e, c))
                if tap < n:
                    for code, c in choices[tap]: push(code, tap + 1, ed, cost + c)
                if depth > 0 and m.apos: push(m.apos, tap, ed, cost)
                if ed >= maxEdits: continue
                e = ed + 1
                for code in allc: push(code, tap, e, cost + p['deletionCost'])
                if tap < n: layer.append((lo, hi, tap + 1, e, cost + extra[tap]))
                if tap + 1 < n and depth + 2 <= maxDepth:
                    for a, ca in choices[tap + 1][:3]:
                        lo2, hi2 = m.narrow(lo, hi, depth, a)
                        if lo2 >= hi2: continue
                        for b, cb in choices[tap][:3]:
                            if b == a: continue
                            lo3, hi3 = m.narrow(lo2, hi2, depth + 1, b)
                            if lo3 < hi3: layers[depth + 2].append((lo3, hi3, tap + 2, e, cost + ca + cb + p['transpositionCost']))
        return sorted(found.items(), key=lambda t: t[1])[:limit]
    def stand(self, i): return self.m.length(i) >= 2 or self.m.uni(i) < self.p['oneLetterWordCost']
    def split_readings(self, costs, prev, split_edits=0):
        n = len(costs); out = []
        for k in range(1, n):
            L = [x for x in self.search(costs, range(0, k), 3, split_edits) if self.stand(x[0])]
            if not L: continue
            R = [x for x in self.search(costs, range(k, n), 3, split_edits) if self.stand(x[0])]
            for l, ls in L:
                lc = ls + self.p['lmWeight'] * self.lm(l, prev)
                for r, rs in R:
                    out.append((self.m.word(l) + ' ' + self.m.word(r), lc + rs + self.p['lmWeight'] * self.lm(r, l) + self.p['spaceOmissionCost']))
        return out
    def decide(self, typed, previous=None, literal_valid=False, split_edits=0):
        m, p = self.m, self.p
        letters = m.encode(typed)
        costs = [self.tapcosts(CENTRES[c]) for c in typed]  # tap dead-centre on each typed key
        prev = m.index(previous) if previous else None
        lit = sum(costs[i][c] for i, c in enumerate(letters))
        li = m.index_codes(letters)
        lit += p['lmWeight'] * (self.lm(li, prev) if li is not None else (p['unknownValidCost'] if literal_valid else p['unknownCost']))
        rd = [(m.word(w), s + p['lmWeight'] * self.lm(w, prev)) for w, s in self.search(costs, range(len(costs)), 5, p['maxEdits']) if w != li]
        if len(letters) >= 3: rd += self.split_readings(costs, prev, split_edits)
        rd.sort(key=lambda t: t[1]); seen = set(); keep = []
        for t, c in rd:
            if t.lower() != typed and c < lit and t.lower() not in seen: seen.add(t.lower()); keep.append((t, c))
        repl = None
        if keep:
            margin = p['validMargin'] if (li is not None or literal_valid) else p['autoMargin']
            if lit - keep[0][1] >= margin: repl = keep[0][0]
        return repl, keep[:3], lit

if __name__ == '__main__':
    m = Model(sys.argv[1]); dec = Decoder(m)
    for w in sys.argv[2:]:
        r, top, lit = dec.decide(w)
        print(f"{w!r:22} -> {r!r:24} literal={lit:6.2f} top={[(t, round(c, 2)) for t, c in top]}")
