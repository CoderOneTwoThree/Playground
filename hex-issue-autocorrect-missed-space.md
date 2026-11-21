**Title:** iOS keyboard: autocorrect misses a missed space when one of the words is misspelled, and can't split three or more run-together words

### Hex version

iOS keyboard. Analysis done against the source at `edeccfc` (dev, 21 Nov 2026). FILL IN: the app version you saw this on.

### Platform

Other (iOS keyboard)

### System details

FILL IN: iPhone model and iOS version. The keyboard language is English, with Spatial autocorrect on (the default).

### What happened?

The autocorrect generally is extremely strong. One area that could use improvement is the handling of missed spaces between words, where one of the words is misspelled. A related gap is three or more words typed with no spaces at all.

I have reproduced this in-keyboard with a large range of words.

**Expected:** the keyboard recognises both the missed space and the misspelled word. When one of the words is spelled correctly, that should help it spot the missing space, and the other word then becomes easy to fix. Three run-together words should be split too.

### Steps to reproduce

1. Type "specialcharacter" and press Space. The keyboard recognises this as two words and inserts a space, producing "special character". ✅
2. Type "specialchsracter" (s hit instead of a in "character") and press Space. The keyboard recognises neither the misspelling nor the missed space between the words, and leaves it as "specialchsracter". ❌
3. Type "seeyoutomorrow", "thankyouverymuch" or "haveaniceday" and press Space. Each stays as typed; expected "see you tomorrow", "thank you very much", "have a nice day". ❌

### Additional context

These findings come from a Python port of `TypingDecoder.decide`, which ports the model reader, the whole-word beam search and `splitReadings` line for line. The port was run against the bundled `ios/HEXKeyboard/TypingModel/en.hextm` with the English parameters (`lmWeight` 1.5). Taps land at key centres on a QWERTY grid. The port has not been run on a device or in Xcode.

#### Results

| Typed | Result | Same word, no slip |
|---|---|---|
| specialchsracter | unchanged | specialcharacter → special character |
| goodmotning | unchanged | goodmorning → good morning |
| nextwerk | unchanged | nextweek → next week |
| lookingforwsrd | unchanged | lookingforward → looking forward |
| emailaddtess | unchanged | emailaddress → email address |
| thsnkyou | thank you ✅ | |
| seeyiu | see you ✅ | |
| lastnifht | last night ✅ | |
| csnyou / ofrhe / inyhe / doyoy | fixed ✅ | |

The slip alone is fixed: "chsracter" typed after "special " becomes "character". Very common pairs work. Less common words fail.

#### Cause 1: there's no room in the cost for a slip inside a missed-space reading

`TypingDecoder.decide` (`ios/HEXShared/FullKeyboard/TypingDecoder.swift:532`) replaces the literal only when the best reading beats it by `autoMargin` (2.0):

- **The literal** is an unknown word, so it costs a flat `lmWeight × unknownCost` = 1.5 × 22 = **33**, whatever its length.
- **The clean split** "special character" costs **29.69**: the language-model cost of both words plus `spaceOmissionCost` 6.0.
- **The bar** is 33 − 2 = 31, which leaves **1.31 nats** for any slip.
- **The slip** of reading a dead-centre tap on S as A costs 0.5 × (1 / 0.29)² ≈ **5.95**. Total 35.64, so the reading is rejected. It is not even kept as a suggestion, because readings costlier than the literal are filtered out.

The literal's cost is fixed, while a split's cost grows with how rare the words are, plus the space penalty and any slips. In practice a slip inside a missed-space reading only survives within about 14% of a key width of the intended key, and only for frequent word pairs.

With Spatial autocorrect off, the `UITextChecker` path never does this. `usableGuess` (`AutocorrectEngine.swift:1177`) accepts a split guess only when its letters are exactly the typed ones (`parts.joined().lowercased() == token.lowercased()`). `testASplitNeedsTwoWordsYourLettersAndTheSpacedForm` locks that in (`"emial"` must not become `"e mail"`).

#### Cause 2: splits are two words only

`splitReadings` (`TypingDecoder.swift:732`) tries a single split point, and each half must be one model word. A three-word run therefore has no candidate reading. In the port, none of the following changed: seeyoutomorrow, thankyouverymuch, iloveyou, whatareyou, inthemorning, haveaniceday, specialcharacterset.

#### A possible fix for cause 1: anchor on an exact word

Prototype rule: when `decide` finds no replacement, try each prefix that is an exact model word (two or more letters, with a remainder of three or more), and run the remainder through `decide` as its own word with the prefix as `previous`. If the remainder gets a one-word replacement, use the most probable "prefix + fix".

| Typed | With the rule |
|---|---|
| specialchsracter | special character ✅ |
| goodmotning | good morning ✅ |
| nextwerk | next week ✅ |
| lookingforwsrd | looking forward ✅ |
| emailaddtess | email address ✅ |

Ordinary one-word typos are unaffected, because the normal decoder runs first: understsnd, togetjer, beautifull, somethinf, carpwt, informstion, therapidt, afternoom, butterflt and passwird all stay single words.

The risk is words outside the model. In the port these were wrongly split:

- netflix → "net flux"
- bitcoin → "bi coin"
- overthinking → "overthink in"
- toolbarx → "tool bar"

The port has no `UITextChecker`, so it treats every word missing from the model as unknown. On device, `literalIsValid` and `validMargin` (7.0) would likely protect dictionary words, but brands, slang and jargon outside both dictionaries would still be at risk. A real version needs that guard, and needs to be run through the typing benchmark (`android/benchmark/typing`) to check false corrections of correctly typed words.

An alternative is to rework the scoring: make the unknown literal's cost scale with length, or give multi-word readings their own margin. That is more general but has to be tuned on the benchmark.

#### A possible fix for cause 2

Extend `splitReadings` to search over several split points, for example with dynamic programming over tap positions, using model words with substitution-only matching per segment. Each added space costs `spaceOmissionCost`, so the acceptance rule from cause 1 matters even more here.

#### Failing tests (sketch)

These are for `ios/HEXMobileTests/AutocorrectEngineTests.swift` and use the existing `useDecoder()` and `typeTaps(_:)` helpers. They have not been compiled.

```swift
func testAMissedSpaceWithASlipInARarerWordSplitsAndFixes() throws {
    try useDecoder()
    typeTaps("specialchsracter")
    XCTAssertEqual(target.text, "special character ", "a missed space and an s for an a")
}

func testThreeWordsWithMissedSpacesSplit() throws {
    try useDecoder()
    typeTaps("seeyoutomorrow")
    XCTAssertEqual(target.text, "see you tomorrow ", "two missed spaces")
}
```

---

#### What I tested and tried

##### Setup

- I cloned `anomalyco/hex` at `edeccfc` (dev, 21 Nov 2026) and read the iOS keyboard's autocorrect code:
  - `ios/HEXShared/FullKeyboard/AutocorrectEngine.swift` decides what Space puts in. It sends a word either to Spatial autocorrect or to `UITextChecker`.
  - `ios/HEXShared/FullKeyboard/TypingDecoder.swift` is Spatial autocorrect, which is on by default (`FullKeyboardSettings.spatialAutocorrect`).
  - `ios/HEXMobileTests/AutocorrectEngineTests.swift` has the existing split tests: "seehow", "ofbthe", and the split-guess rules.
- I couldn't run Swift, Xcode or a simulator, because the machine was Linux. Instead, I ported the decoder to Python line for line:
  - the HXTM v3 model reader;
  - the per-tap Gaussian cost, with `sigmaX` 0.29 and `sigmaY` 0.26;
  - the beam search with one edit (substitution, insertion, deletion, transposition, free apostrophe);
  - `splitReadings`;
  - the margin rule.
- The port used the English parameters from `Parameters.tuned(for: "en")`.
- It read the real bundled model, `ios/HEXKeyboard/TypingModel/en.hextm`.
- Taps land at key centres on a QWERTY grid with one-key pitch and standard row offsets.

The port leaves out four things:
- your own words and `UILexicon`;
- the never-suggest list;
- adaptive touch offsets;
- `UITextChecker` validity, so every word missing from the model counts as unknown.

##### Checking the port against the repo's behaviour

| Typed | Port result | Matches the repo? |
|---|---|---|
| seehow | see how | Yes, the case tested in `testSpatialAutocorrectReadsTapsWithTheWordBefore` |
| ofthe | of the | Yes |
| specialcharacter | special character | Yes, matches what you see in the keyboard |
| specialchsracter | unchanged | Yes, matches what you see in the keyboard |

##### Test 1: a missed space plus one slip

Each slip is a neighbouring key, tapped dead centre.

| No slip | Result | With slip | Result | Best two-word cost (bar is 31) |
|---|---|---|---|---|
| specialcharacter | special character | specialchsracter | unchanged | over 33, dropped |
| goodmorning | good morning | goodmotning | unchanged | 32.08 |
| nextweek | next week | nextwerk | unchanged | 31.70 |
| lookingforward | looking forward | lookingforwsrd | unchanged | 31.89 |
| emailaddress | email address | emailaddtess | unchanged | over 33, dropped |
| thankyou | thank you | thsnkyou | thank you | 28.14 |
| seeyou | see you | seeyiu | see you | 29.64 |
| lastnight | last night | lastnifht | last night | 29.83 |
| canyou | can you | csnyou | can you | 29.08 |
| thatis | that is | thatos | that is | 25.33 |
| ofthe | of the | ofrhe | of the | 20.26 |
| inthe | in the | inyhe | in the | 21.20 |
| doyou | do you | doyoy | do you | 26.83 |

I also ran phonenumvet and highschoik, which both stayed unchanged. These have two slips each, so they aren't a fair comparison.

Two more checks:
- "chsracter" typed as its own word after "special " is corrected to "character".
- Measured numbers: the clean split costs 29.69, the literal costs 33.0, and the bar is 31.0, so the slack is 1.31 nats. Reading an S tap as A costs 5.95.

##### Test 2: three or more words with no spaces

All of these stayed unchanged, with no candidate reading at all:

- seeyoutomorrow
- thankyouverymuch
- iloveyou
- whatareyou
- inthemorning
- haveaniceday
- specialcharacterset

##### Tried: the "anchor on an exact word" rule

The rule runs only when the normal decoder makes no change:
1. Take each prefix that is an exact model word, two or more letters long, leaving three or more letters after it.
2. Decode the rest as its own word, with the prefix as the previous word.
3. If the rest gets a one-word fix, keep the most probable "prefix + fix".

| Group | Words | Outcome |
|---|---|---|
| Fixed | specialchsracter, goodmotning, nextwerk, lookingforwsrd, emailaddtess | All correct |
| One-word typos, unaffected | understsnd, togetjer, beautifull, somethinf, carpwt, informstion, therapidt, afternoom, butterflt, passwird, infornstipn, defintely | The normal decoder still fixes each as one word |
| Left alone | carlsberg, kubernetes, manchesyer, hotdogging, wifi | No change |
| Wrongly split | netflix → net flux, bitcoin → bi coin, overthinking → overthink in, toolbarx → tool bar | Errors. On device, `UITextChecker` may protect the first three. |

##### Not done

- The fixes haven't been run through the repo's typing benchmark (`android/benchmark/typing`).
- The two XCTest sketches haven't been compiled or run.
- I didn't trace the Android keyboard, so I don't know whether it has the same behaviour.
- I didn't test other languages.

#### Reproducing

All three scripts are below. Save them in one folder; each takes the model path as its first argument:

```sh
python3 decoder.py ios/HEXKeyboard/TypingModel/en.hextm specialcharacter specialchsracter
python3 missed_space_with_slip.py ios/HEXKeyboard/TypingModel/en.hextm
python3 three_words_and_anchor_rule.py ios/HEXKeyboard/TypingModel/en.hextm
```

<details><summary><code>decoder.py</code></summary>

```python
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
```

</details>

<details><summary><code>missed_space_with_slip.py</code></summary>

```python
import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decoder import *
m = Model(sys.argv[1]); dec = Decoder(m)
cases = [("specialcharacter","specialchsracter"),("thankyou","thsnkyou"),("goodmorning","goodmotning"),
 ("seeyou","seeyiu"),("nextweek","nextwerk"),("lastnight","lastnifht"),("phonenumber","phonenumvet"),
 ("emailaddress","emailaddtess"),("highschool","highschoik"),("canyou","csnyou"),("thatis","thatos"),
 ("lookingforward","lookingforwsrd"),("ofthe","ofrhe"),("inthe","inyhe"),("doyou","doyoy")]
for good, bad in cases:
    a = dec.decide(good)[0]; b, top, lit = dec.decide(bad)
    print(f"{good:16} -> {str(a):20} | {bad:16} -> {str(b):10} best={top[:1]} literal={lit:.1f}")
# Slack: the clean split vs the literal budget
r, top, lit = dec.decide("specialcharacter")
print("\nclean split cost", round(top[0][1],2), "literal", lit, "needs <=", lit-2, "-> slack", round(lit-2-top[0][1],2), "nats")
c = dec.tapcosts(CENTRES['s']); print("cost of reading a dead-centre 's' tap as 'a':", round(c[m.codes['a']],2))
# misspelled half alone, after 'special'
print("'chsracter' typed as its own word after 'special':", dec.decide("chsracter", previous="special")[0])
```

</details>

<details><summary><code>three_words_and_anchor_rule.py</code></summary>

```python
import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decoder import *
m = Model(sys.argv[1]); dec = Decoder(m)
print("== Three correctly spelled words, no spaces ==")
for w in ["seeyoutomorrow","thankyouverymuch","iloveyou","whatareyou","specialcharacterset","inthemorning","haveaniceday"]:
    r, top, lit = dec.decide(w); print(f"{w:22} -> {r!r:20} top={[(t,round(c,1)) for t,c in top[:2]]}")

print("\n== Anchored rule: prefix is an exact word, remainder fixed as its own word ==")
def anchored(typed):
    whole, _, _ = dec.decide(typed)
    if whole: return whole, "normal decoder"
    best = None
    for k in range(2, len(typed) - 1):
        left, right = typed[:k], typed[k:]
        if m.index(left) is None or len(right) < 3: continue
        fix, _, _ = dec.decide(right, previous=left)
        if fix and " " not in fix:
            c = dec.lm(m.index(left), None) + dec.lm(m.index(fix), m.index(left))
            if best is None or c < best[1]: best = (left + " " + fix, c)
    return (best[0], "anchored") if best else (None, "-")
for w in ["specialchsracter","goodmotning","nextwerk","lookingforwsrd","emailaddtess",
          # risk: one misspelled long word that starts with a real word
          "understsnd","togetjer","beautifull","somethinf","carpwt","informstion","therapidt","afternoom","butterflt","passwird"]:
    print(f"{w:18} -> {str(anchored(w)[0]):22} ({anchored(w)[1]})")
print("\n== Risk: words the normal decoder leaves alone ==")
for w in ["infornstipn","defintely","carlsberg","kubernetes","manchesyer","hotdogging","toolbarx","bitcoin","pinterest","overthinking","netflix","wifi"]:
    print(f"{w:18} -> {str(anchored(w)[0]):22} ({anchored(w)[1]})")
```

</details>

---
_Generated by [Claude Code](https://claude.ai/code)_
