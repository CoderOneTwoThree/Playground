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
