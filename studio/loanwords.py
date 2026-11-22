"""English words that Hindi speech writes in Devanagari.

People who speak Hindi say "game", "live" and "subscribe" all day, and the speech model writes them the way they
sound: गेम, लाइव, सब्सक्राइब. Spelled out letter by letter these come out as "gem", "laiv" and "sabsakraib",
which looks wrong on screen. So the common ones are listed here with their real spelling, and roman.py uses the
list. Anything that is not listed is still spelled out by the rules in roman.py: this list only makes the usual
words look right.

One line per word: the English spelling, a colon, then every way it is written in Devanagari. These differences
are ignored when a word is looked up, so they never need their own entry: the dot under a letter (फ़ोन or फोन; not
under ड and ढ, which are letters of their own), the chandrabindu (ँ or ं), and ाइ against ाई (लाइव or लाईव).
Long and short vowels are NOT ignored, because Hindi has real words that differ only by that (फूल is a flower,
फुल is "full").

Words that are Hindi first and English second (बस, पास, सर, लो, वन, बेल, गोल, पेड) are left out on purpose: a
wrong guess puts an English word in place of a Hindi one."""
import re
import unicodedata

_TABLE = """
# ---- streaming, videos and social media
clip: क्लिप
live: लाइव
stream: स्ट्रीम
streamer: स्ट्रीमर
streaming: स्ट्रीमिंग
channel: चैनल चैनेल
subscribe: सब्सक्राइब सबस्क्राइब
subscriber: सब्सक्राइबर सबस्क्राइबर
like: लाइक
share: शेयर
comment: कमेंट कमेन्ट
video: वीडियो विडियो
vlog: व्लॉग व्लोग
reel: रील
Shorts: शॉर्ट्स
short: शॉर्ट
post: पोस्ट
story: स्टोरी
follow: फॉलो
follower: फॉलोअर फॉलोवर
notification: नोटिफिकेशन
link: लिंक
title: टाइटल
thumbnail: थंबनेल थम्बनेल
trending: ट्रेंडिंग ट्रेन्डिंग
viral: वायरल
view: व्यू
edit: एडिट
editing: एडिटिंग
editor: एडिटर
upload: अपलोड
download: डाउनलोड
online: ऑनलाइन
offline: ऑफलाइन
internet: इंटरनेट
app: ऐप एप
mobile: मोबाइल
phone: फोन
laptop: लैपटॉप
computer: कंप्यूटर कम्प्यूटर
setup: सेटअप
setting: सेटिंग
graphics: ग्राफिक्स
sensitivity: सेंसिटिविटी सेन्सिटिविटी
content: कंटेंट
creator: क्रिएटर
camera: कैमरा
screen: स्क्रीन
record: रिकॉर्ड
recording: रिकॉर्डिंग
sound: साउंड
music: म्यूजिक
song: सॉन्ग
voice: वॉइस
face: फेस
photo: फोटो
selfie: सेल्फी
comedy: कॉमेडी
entertainment: एंटरटेनमेंट
dialogue: डायलॉग
reaction: रिएक्शन
review: रिव्यू
trailer: ट्रेलर
release: रिलीज
launch: लॉन्च
update: अपडेट
patch: पैच
server: सर्वर
highlight: हाइलाइट
moment: मोमेंट
challenge: चैलेंज
gift: गिफ्ट
giveaway: गिवअवे
donate: डोनेट
donation: डोनेशन
chat: चैट
message: मैसेज
icon: आइकॉन
love: लव
fan: फैन

# ---- gaming
game: गेम
gamer: गेमर
gaming: गेमिंग
gameplay: गेमप्ले
play: प्ले
player: प्लेयर
playing: प्लेइंग
team: टीम
squad: स्क्वाड
solo: सोलो
duo: ड्यूओ
match: मैच
round: राउंड
level: लेवल
mission: मिशन
map: मैप
zone: ज़ोन
kill: किल
killed: किल्ड
streak: स्ट्रीक
headshot: हेडशॉट
sniper: स्नाइपर
gun: गन
weapon: वेपन
rifle: राइफल
pistol: पिस्टल
shotgun: शॉटगन
grenade: ग्रेनेड
bomb: बम
boss: बॉस
lobby: लॉबी
rank: रैंक
push: पुश
conqueror: कॉन्करर
ace: ऐस
clutch: क्लच
noob: नूब नोब
pro: प्रो
hacker: हैकर
hack: हैक
cheat: चीट
bug: बग
glitch: ग्लिच
lag: लैग
ping: पिंग
skin: स्किन
loot: लूट
drop: ड्रॉप
airdrop: एयरड्रॉप
spawn: स्पॉन
respawn: रिस्पॉन
revive: रिवाइव
heal: हील
health: हेल्थ
armor: आर्मर
helmet: हेलमेट
car: कार
bike: बाइक
truck: ट्रक
helicopter: हेलीकॉप्टर हेलिकॉप्टर
plane: प्लेन
jet: जेट
boat: बोट
tank: टैंक
police: पुलिस
cop: कॉप
wanted: वांटेड
chase: चेज
escape: एस्केप
mode: मोड
mod: मॉड
world: वर्ल्ड
open: ओपन
city: सिटी
damage: डैमेज
speed: स्पीड
power: पावर
energy: एनर्जी
fast: फास्ट
slow: स्लो
high: हाई
stats: स्टैट्स
score: स्कोर
point: पॉइंट
win: विन
lose: लूज
winner: विनर
champion: चैंपियन
trophy: ट्रॉफी
final: फाइनल
first: फर्स्ट
best: बेस्ट
top: टॉप
funny: फनी
epic: एपिक
insane: इनसेन
crazy: क्रेज़ी
legend: लेजेंड
god: गॉड
OP: ओपी
ultimate: अल्टीमेट
light: लाइट
off: ऑफ ओफ
double: डबल
triple: ट्रिपल
mini: मिनी
mega: मेगा
full: फुल
new: न्यू
next: नेक्स्ट
season: सीजन
episode: एपिसोड
part: पार्ट
HD: एचडी

# ---- the names of games, apps and brands
GTA: जीटीए
grand: ग्रैंड ग्रैण्ड
theft: थेफ्ट
auto: ऑटो ओटो
vice: वाइस
Leonida: लियोनिडा
Florida: फ्लोरिडा
Miami: मियामी
Lucia: लूसिया लुसिया
Jason: जेसन
Michael: माइकल
Franklin: फ्रैंकलिन
Trevor: ट्रेवर
Rockstar: रॉकस्टार
BGMI: बीजीएमआई
PUBG: पबजी पब्जी
FF: एफएफ
COD: सीओडी
free: फ्री
fire: फायर
max: मैक्स
call: कॉल
duty: ड्यूटी
Warzone: वॉरज़ोन
Minecraft: माइनक्राफ्ट माइनक्रैफ्ट
Fortnite: फोर्टनाइट
Valorant: वैलोरेंट वेलोरेंट
Roblox: रोब्लॉक्स रोब्लोक्स
Cyberpunk: साइबरपंक
Apex: एपेक्स
clash: क्लैश
clans: क्लैंस क्लेन्स
royale: रोयाल
royal: रॉयल
brawl: ब्रॉल
star: स्टार
battlegrounds: बैटलग्राउंड्स बैटलग्राउंड
India: इंडिया
Indian: इंडियन
counter: काउंटर
strike: स्ट्राइक
PC: पीसी
PS: पीएस
Xbox: एक्सबॉक्स
PlayStation: प्लेस्टेशन
Nvidia: एनवीडिया
RTX: आरटीएक्स
FPS: एफपीएस
AI: एआई
ID: आईडी
IPL: आईपीएल
UPI: यूपीआई
OTP: ओटीपी
YouTube: यूट्यूब
Instagram: इंस्टाग्राम
Insta: इंस्टा
WhatsApp: व्हाट्सएप व्हाट्सऐप
Facebook: फेसबुक
Twitter: ट्विटर
Discord: डिस्कॉर्ड डिस्कोर्ड
Twitch: ट्विच
kick: किक
Google: गूगल
Jio: जियो
Airtel: एयरटेल
Paytm: पेटीएम
PhonePe: फोनपे
Amazon: अमेज़न
Flipkart: फ्लिपकार्ट
Telegram: टेलीग्राम
Snapchat: स्नैपचैट
ChatGPT: चैटजीपीटी
Samsung: सैमसंग
iPhone: आईफोन
Android: एंड्रॉइड एंड्रॉयड

# ---- everyday English inside Hindi
ok: ओके
sorry: सॉरी
please: प्लीज
thanks: थैंक्स
thank: थैंक
you: यू
hello: हेलो हैलो
bye: बाय
guys: गाइज गाइस
friend: फ्रेंड
brother: ब्रदर
bro: ब्रो
dude: ड्यूड
madam: मैडम
yes: यस
wow: वाओ वाउ
cool: कूल
nice: नाइस
super: सुपर
great: ग्रेट
good: गुड
bad: बैड
very: वेरी
really: रियली
actually: एक्चुअली एक्चुली
basically: बेसिकली
seriously: सीरियसली
literally: लिटरली
exactly: एग्जैक्टली एक्जैक्टली
sure: श्योर
perfect: परफेक्ट
amazing: अमेज़िंग अमेजिंग
awesome: ऑसम
scene: सीन
time: टाइम
second: सेकंड सेकेंड
minute: मिनट
hour: आवर
night: नाइट
morning: मॉर्निंग
price: प्राइस
offer: ऑफर
sale: सेल
order: ऑर्डर
delivery: डिलीवरी डिलिवरी
account: अकाउंट
password: पासवर्ड
number: नंबर नम्बर
code: कोड
check: चेक
test: टेस्ट
result: रिजल्ट
exam: एग्जाम एक्जाम
class: क्लास
college: कॉलेज
school: स्कूल
office: ऑफिस
job: जॉब
problem: प्रॉब्लम
solution: सॉल्यूशन
issue: इश्यू
tension: टेंशन
confidence: कॉन्फिडेंस
focus: फोकस
mood: मूड
plan: प्लान
idea: आइडिया
chance: चांस चान्स
risk: रिस्क
fix: फिक्स
support: सपोर्ट
money: मनी
dollar: डॉलर
million: मिलियन
billion: बिलियन
percent: परसेंट
cricket: क्रिकेट
football: फुटबॉल
captain: कैप्टन
coach: कोच
dance: डांस
party: पार्टी
style: स्टाइल
look: लुक
hot: हॉट
real: रियल
fake: फेक
original: ओरिजिनल
six: सिक्स
five: फाइव
four: फोर
three: थ्री
ten: टेन
hundred: हंड्रेड
thousand: थाउजेंड
"""

# Names that are said as several words, where one of the words (ऑफ) would be "off" on its own.
_PHRASES = [
    ("कॉल ऑफ ड्यूटी", "Call of Duty"),
    ("क्लैश ऑफ क्लैंस", "Clash of Clans"),
    ("क्लैश ऑफ क्लैन्स", "Clash of Clans"),
    ("लीग ऑफ लेजेंड्स", "League of Legends"),
    ("ग्रैंड थेफ्ट ऑटो", "Grand Theft Auto"),
]

# written as numbers so that no editor or tool can turn them into the invisible marks themselves
_NUKTA, _CHANDRABINDU, _ANUSVARA = chr(0x093C), chr(0x0901), chr(0x0902)
_VOWEL_ENDINGS = "".join(chr(c) for c in list(range(0x093E, 0x094D)) + list(range(0x0905, 0x0915)))


def key(word: str) -> str:
    """A spelling with the differences that do not matter taken out (the dot under a letter, the chandrabindu)."""
    s = unicodedata.normalize("NFC", word or "")
    s = re.sub("(?<![डढ])" + _NUKTA, "", s)       # ड़ and ढ़ are letters of their own, the other dots are only a dot
    return s.replace(_CHANDRABINDU, _ANUSVARA)


def _variants(spelling: str) -> list:
    """The spelling, and the same with ाइ and ाई swapped: लाइव and लाईव are the same word."""
    out = [spelling]
    if "ाइ" in spelling:
        out.append(spelling.replace("ाइ", "ाई"))
    if "ाई" in spelling:
        out.append(spelling.replace("ाई", "ाइ"))
    return out


def _build():
    table, spellings, conflicts = {}, [], []
    for line in _TABLE.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        english, _, rest = line.partition(":")
        english = english.strip()
        for spelling in rest.split():
            spellings.append((english, spelling))
            for v in _variants(spelling):
                k = key(v)
                if table.get(k, english) != english:
                    conflicts.append((k, table[k], english))
                else:
                    table[k] = english
    return table, spellings, conflicts


TABLE, SPELLINGS, CONFLICTS = _build()


def lookup(word: str):
    """The English word a Devanagari spelling stands for, or None. A plural ending (-्स or -ज) is understood when
    the word it is made from is known: क्लिप्स is clips, वीडियोज़ is videos."""
    k = key(word)
    if k in TABLE:
        return TABLE[k]
    for tail in ("्स", "ज"):
        if not k.endswith(tail) or len(k) <= len(tail) + 1:
            continue
        stem = k[: -len(tail)]
        if tail == "ज" and stem[-1] not in _VOWEL_ENDINGS:
            continue                      # -ज is a plural only after a vowel (वीडियोज); after a letter it may be a Hindi word
        known = TABLE.get(stem)
        if known and known[:1].islower() and known.isalpha():
            return known + "s"
    return None


def _phrase_pattern(phrase: str) -> str:
    """A pattern for a phrase that lets the dot under a letter be there or not, and any space be one or more."""
    out = []
    for ch in phrase:
        if ch == " ":
            out.append(r"\s+")
        else:
            out.append(re.escape(ch))
            if 0x0915 <= ord(ch) <= 0x0939:
                out.append(_NUKTA + "?")
    return "".join(out)


_PHRASE_RE = re.compile("|".join(f"(?P<p{i}>{_phrase_pattern(p)})" for i, (p, _e) in enumerate(_PHRASES)))


def phrases(text: str) -> str:
    """The names that are several words long, written the English way."""
    return _PHRASE_RE.sub(lambda m: _PHRASES[int(m.lastgroup[1:])][1], text)
