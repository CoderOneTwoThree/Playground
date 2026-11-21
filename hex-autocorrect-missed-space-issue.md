# Autocorrect of misspelled words with a missed space

The autocorrect generally is extremely strong. One area that could use improvement is the handling of missed spaces between words, where one of the words is misspelled. A related gap is three or more words typed with no spaces at all.

I have reproduced this in-keyboard with a large range of words.

## Example

1. User types "specialcharacter"

   The keyboard recognises this as two words and inserts a space, producing "special character".

2. User types "specialchsracter"

   The user has mistyped "character", hitting s instead of a.

   The keyboard recognises neither the misspelling nor the missed space between the words. It leaves this as "specialchsracter".

3. Correct handling

   The keyboard should be able to recognise both the missed space and the misspelled word. When one of the words is spelled correctly, that should help it spot the missing space, and the other word then becomes easy to fix.

## Three words with no spaces

The keyboard also can't handle three correctly spelled words with the spaces missed. All of these stay as typed:

- "seeyoutomorrow"
- "thankyouverymuch"
- "haveaniceday"

It should produce "see you tomorrow", "thank you very much" and "have a nice day".

---

## Technical details

These findings come from a Python port of `TypingDecoder.decide`, which ports the model reader, the whole-word beam search and `splitReadings` line for line. The port was run against the bundled `ios/HEXKeyboard/TypingModel/en.hextm` with the English parameters (`lmWeight` 1.5). Taps land at key centres on a QWERTY grid. The port has not been run on a device or in Xcode.

### Results

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

### Cause 1: there's no room in the cost for a slip inside a missed-space reading

`TypingDecoder.decide` (`ios/HEXShared/FullKeyboard/TypingDecoder.swift:532`) replaces the literal only when the best reading beats it by `autoMargin` (2.0):

- **The literal** is an unknown word, so it costs a flat `lmWeight × unknownCost` = 1.5 × 22 = **33**, whatever its length.
- **The clean split** "special character" costs **29.69**: the language-model cost of both words plus `spaceOmissionCost` 6.0.
- **The bar** is 33 − 2 = 31, which leaves **1.31 nats** for any slip.
- **The slip** of reading a dead-centre tap on S as A costs 0.5 × (1 / 0.29)² ≈ **5.95**. Total 35.64, so the reading is rejected. It is not even kept as a suggestion, because readings costlier than the literal are filtered out.

The literal's cost is fixed, while a split's cost grows with how rare the words are, plus the space penalty and any slips. In practice a slip inside a missed-space reading only survives within about 14% of a key width of the intended key, and only for frequent word pairs.

With Spatial autocorrect off, the `UITextChecker` path never does this. `usableGuess` (`AutocorrectEngine.swift:1177`) accepts a split guess only when its letters are exactly the typed ones (`parts.joined().lowercased() == token.lowercased()`). `testASplitNeedsTwoWordsYourLettersAndTheSpacedForm` locks that in (`"emial"` must not become `"e mail"`).

### Cause 2: splits are two words only

`splitReadings` (`TypingDecoder.swift:732`) tries a single split point, and each half must be one model word. A three-word run therefore has no candidate reading. In the port, none of the following changed: seeyoutomorrow, thankyouverymuch, iloveyou, whatareyou, inthemorning, haveaniceday, specialcharacterset.

### A possible fix for cause 1: anchor on an exact word

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

### A possible fix for cause 2

Extend `splitReadings` to search over several split points, for example with dynamic programming over tap positions, using model words with substitution-only matching per segment. Each added space costs `spaceOmissionCost`, so the acceptance rule from cause 1 matters even more here.

### Failing tests (sketch)

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
