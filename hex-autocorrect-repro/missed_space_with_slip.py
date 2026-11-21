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
