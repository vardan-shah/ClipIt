"""Made for India: Hindi and Hinglish read the way a person from India would read them.

- English words that Hindi speech writes in Devanagari (गेम, लाइव, क्लिप) come out spelled as people type them
- the picker that works without an AI can read Hindi titles and Hindi speech
- games are found from Hindi titles, and the games played in India are known
- the "clip it" voice command works when it is said in Hindi
- the AI is told how to read Hindi and Hinglish, and only when the speech is that

Runs against the code directly, with its own empty data folder. No AI, no network."""
import contextlib
import io
import os
import sys
import tempfile
from unittest import mock

os.environ["CLIPIT_DATA"] = tempfile.mkdtemp(prefix="pc-india-")
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")
import numpy as np  # noqa: E402
from studio import ai, ai_check, brain, games, live, loanwords, roman  # noqa: E402

fails = []


def check(n, got, want=True):
    """What came out, and what should have come out."""
    good = want(got) if callable(want) else got == want
    print(("PASS " if good else "FAIL ") + n + ("" if good else f"   got {got!r}"))
    good or fails.append(n)


def ok(n, cond, info=""):
    """A yes-or-no check. `info` is only shown when it fails, to see what went wrong."""
    print(("PASS " if cond else "FAIL ") + n + ("" if cond else f"   got {info!r}"))
    cond or fails.append(n)


def ws(text, start=0.0, step=0.45):
    """Words one after the other from `start`, the way a transcript hands them over."""
    out, t = [], start
    for w in text.split():
        out.append({"w": w, "s": round(t, 2), "e": round(t + 0.4, 2)})
        t += step
    return out


# ---- English words said in Hindi are spelled the English way
for hi, want in [("गेम", "game"), ("क्लिप", "clip"), ("लाइव", "live"), ("लाईव", "live"), ("चैनल", "channel"),
                 ("सब्सक्राइब", "subscribe"), ("वीडियो", "video"), ("गेमप्ले", "gameplay"), ("स्ट्रीमर", "streamer"),
                 ("हेडशॉट", "headshot"), ("ओके", "ok"), ("गाइज़", "guys"), ("फ्रेंड्स", "friends")]:
    check(f"{hi} is written {want}", roman.to_roman(hi), want)
check("a plural is made from the word", [roman.to_roman(x) for x in ("क्लिप्स", "वीडियोज़", "गेमर्स", "सेटिंग्स")],
      ["clips", "videos", "gamers", "settings"])
check("a full stop stuck to the word does not hide it", roman.to_roman("गेम।"), "game.")
check("nor does a number written in Devanagari", roman.to_roman("जीटीए६"), "GTA6")
ok("the way of writing a dot under a letter does not matter", roman.to_roman("फ़ोन") == roman.to_roman("फोन") == "phone", roman.to_roman("फ़ोन"))
check("names and short names keep their capitals", [roman.to_roman(x) for x in ("बीजीएमआई", "पबजी", "यूट्यूब", "माइनक्राफ्ट", "आईफोन")],
      ["BGMI", "PUBG", "YouTube", "Minecraft", "iPhone"])
check("a whole sentence reads as it is typed", roman.to_roman("भाई ये क्लिप देखो"), "bhai ye clip dekho")
ok("Hindi games with several words in their name", roman.to_roman("कॉल ऑफ ड्यूटी मोबाइल") == "Call of Duty mobile"
      and roman.to_roman("क्लैश ऑफ क्लैंस") == "Clash of Clans", roman.to_roman("कॉल ऑफ ड्यूटी मोबाइल"))
check("'ऑफ' alone is 'off'", roman.to_roman("लाइट ऑफ कर"), "light off kar")
# words that are Hindi, and only sound like English ones, are not turned into English
for hi, wrong in [("फूल", "full"), ("बोल", "ball"), ("बस", "bus"), ("कुल", "cool"), ("पास", "pass"), ("सर", "sir")]:
    ok(f"{hi} is still the Hindi word", roman.to_roman(hi) != wrong, roman.to_roman(hi))
check("words people type a certain way", [roman.to_roman(x) for x in ("अरे", "आ गया", "चाहिए", "रुपये", "हिंदी")],
      ["arre", "aa gaya", "chahiye", "rupaye", "hindi"])
check("English around Hindi is left alone", roman.to_roman("GTA गेम में 1000 clips"), "GTA game mein 1000 clips")

# ---- the list of words itself holds together
ok("the list has plenty of words", len(loanwords.SPELLINGS) > 400, len(loanwords.SPELLINGS))
check("no spelling means two different words", loanwords.CONFLICTS, [])
bad = [(e, s) for e, s in loanwords.SPELLINGS if loanwords.lookup(s) != e]
check("every spelling in the list finds its word", bad, [])

# ---- Hinglish is told from English
check("Hindi in Devanagari", roman.looks_hindi("भाई ये क्या हुआ"))
check("Hindi in Roman letters", roman.looks_hindi("bhai ye kya kar diya yaar mujhe nahi pata kya hua tha"))
check("Hindi and English mixed", roman.looks_hindi("bro that was insane yaar, kya clutch tha, mujhe nahi pata kaise hua"))
check("English", roman.looks_hindi("so we are just driving around the city today and the radio is playing some music"), False)
check("English with one Hindi word", roman.looks_hindi("that was a crazy play bhai honestly one of the best i have seen this week"), False)
check("English that holds words which are also Hindi ones", roman.looks_hindi("i said to him to do a tab on the log and he did it again and again"), False)
check("too little to say", roman.looks_hindi("kya hua"), False)
check("nothing", roman.looks_hindi(""), False)

# ---- games are found from Hindi titles, and the games played in India are known
for title, want in [("जीटीए 6 गेमप्ले हिंदी में", "Grand Theft Auto VI"),
                    ("ग्रैंड थेफ्ट ऑटो 6 लाइव", "Grand Theft Auto VI"),
                    ("GTA six first look in Hindi", "Grand Theft Auto VI"),
                    ("GTA 6 Vice City trailer reaction", "Grand Theft Auto VI"),
                    ("GTA Vice City Hindi gameplay", "Grand Theft Auto: Vice City"),
                    ("BGMI Hindi live rank push", "BGMI"),
                    ("बीजीएमआई लाइव कॉन्करर पुश", "BGMI"),
                    ("Free Fire MAX pro player", "Free Fire"),
                    ("फ्री फायर लाइव", "Free Fire"),
                    ("माइनक्राफ्ट हिंदी सर्वाइवल", "Minecraft"),
                    ("COD Mobile ranked", "Call of Duty: Mobile"),
                    ("कॉल ऑफ ड्यूटी मोबाइल लाइव", "Call of Duty: Mobile"),
                    ("Call of Duty Warzone squad", "Call of Duty"),
                    ("Roblox Hindi obby", "Roblox"),
                    ("क्लैश ऑफ क्लैंस base", "Clash of Clans"),
                    ("Brawl Stars Hindi", "Brawl Stars"),
                    ("eFootball 2026 live", "eFootball"),
                    ("Genshin Impact Hindi", "Genshin Impact"),
                    ("Valorant ranked Hindi", "Valorant"),
                    ("पबजी लाइव", "PUBG")]:
    check(f"the game in '{title}'", games.detect(title)[0], want)
check("a chat stream in Hindi has no game", games.detect("आज बातें करते हैं दोस्तों के साथ")[0], None)
check("'Free Fire' written in English is read as the game", games.detect("Free Fire")[0], "Free Fire")
check("the tags of an Indian game", "BGMI" in games.tags_of("bgmi") and "FreeFire" in games.tags_of("free fire"), True)
ok("a game written in Hindi gets its name and tags", games.name_of("फ्री फायर") == "Free Fire" and "FreeFire" in games.tags_of("फ्री फायर"),
      (games.name_of("फ्री फायर"), games.tags_of("फ्री फायर")))
check("GTA VI still has its own tags", "GTA6" in games.tags_of("जीटीए 6"), True)
check("a Vice City trailer for GTA VI does not become the old game", games.detect("GTA VI Vice City map leaks")[0], "Grand Theft Auto VI")
tidy_tags = brain._tidy({"hashtags": ["जीटीए6", "गेम", "Hindi"], "hook": "x"}, 0.0, 10.0)["hashtags"]
check("hashtags the AI wrote in Hindi letters come out in Roman letters, not mangled", tidy_tags, ["GTA6", "game", "Hindi"])

# ---- without an AI: Hindi titles and Hindi speech still make a hook, a title and tags
check("tags from a Hindi title", brain._title_tags("जीटीए 6 गेमप्ले हिंदी में"), ["gta6", "gameplay", "hindi", "shorts"])
check("tags from a Hinglish title leave out the little words", brain._title_tags("Bhai ne GTA 6 me kya kar diya | Hindi Gameplay"),
      ["gta6", "hindi", "gameplay", "shorts"])
check("tags from an English title are as before", brain._title_tags("GTA 6 Launch Day Gameplay LIVE"), ["gta6", "launch", "day", "gameplay", "shorts"])

spoken = ws("पागल है क्या?", 10.0) + ws("अरे यार ये क्या हुआ!", 14.0) + ws("चलो आगे चलते हैं", 19.0)
loud = np.full(60, -40.0)
loud[14:18] = -5.0
picks = brain.fallback_by_loudness(loud, spoken, 1, 20, 60.0, "जीटीए 6 गेमप्ले हिंदी में")
p = picks[0] if picks else {}
check("no AI, Hindi speech: the hook is what was said, in Roman letters", p.get("hook"), "ARRE YAAR YE KYA HUA")
check("no AI, Hindi speech: so is the title", p.get("title"), "Arre yaar ye kya hua!")
check("no AI, a Hindi title: its tags", p.get("hashtags"), ["gta6", "gameplay", "hindi", "shorts"])
check("no AI, Hindi speech: no word of a hook or title is left in Devanagari", not roman.needs_roman(p.get("hook", "") + p.get("title", "")), True)

hinglish = ws("bhai aaj kuch bhi ho jaye", 10.0) + ws("oye oye ek number jump maara bhai!", 14.0) + ws("chalo ab agla mission", 20.0)
picks = brain.fallback_by_loudness(loud, hinglish, 1, 20, 60.0, "")
ok("no AI, Hinglish in Roman letters: the reaction is found", picks and picks[0]["hook"] == "OYE OYE EK NUMBER JUMP", str(picks[:1]))

# the whole path, with no AI to ask
with mock.patch.object(brain, "ask_ai", side_effect=RuntimeError("The AI is not set up on this server.")):
    clips, info = brain.find_clips(spoken, loud, 60.0, title="जीटीए 6 गेमप्ले हिंदी में", uploader="", max_clips=1, min_len=10, max_len=20)
c = clips[0] if clips else {}
ok("no AI, a whole video in Hindi: a clip with a Roman hook and title", c.get("hook") == "ARRE YAAR YE KYA HUA" and c.get("title") == "Arre yaar ye kya hua!", str(c))
ok("...and its tags come from the Hindi title", c.get("hashtags") == ["gta6", "gameplay", "hindi", "shorts"], str(c.get("hashtags")))

# ---- the AI is told how to read Hindi and Hinglish, and only when the speech is that
seen = []


def fake_ai(prompt, schema=None, purpose="", timeout=None):
    seen.append(prompt)
    return [], "fake-model", 1


def lines_of(text, n=5):
    """The same sentence said n times, far enough apart that each one stays a line of its own."""
    out = []
    for i in range(n):
        out += ws(text, i * 7.0)
    return out


NOTE = brain.INDIA_NOTE.strip().splitlines()[0]
with mock.patch.object(brain, "ask_ai", fake_ai):
    for label, text, told in [("Hindi in Devanagari", "अरे यार ये क्या हुआ पागल है क्या", True),
                              ("Hinglish in Roman letters", "bhai ye kya kar diya yaar mujhe nahi pata tha", True),
                              ("English", "no way that just happened did you see that car fly over me", False)]:
        words = lines_of(text)
        seen.clear()
        brain.find_clips(words, np.zeros(40), 40.0, title="T", uploader="U")
        ok(f"a whole video, {label}: the reading guide is {'added' if told else 'left out'}", bool(seen) and (NOTE in seen[0]) == told, len(seen))
        seen.clear()
        brain.judge_transcript(words, 0.0, 40.0, title="T", uploader="U")
        check(f"a live check on the words, {label}: the reading guide is {'added' if told else 'left out'}", bool(seen) and (NOTE in seen[0]) == told)
        seen.clear()
        brain.find_live_clips(words, np.zeros(40), 40.0, title="T", uploader="U")
        check(f"a live check with loudness, {label}: the reading guide is {'added' if told else 'left out'}", bool(seen) and (NOTE in seen[0]) == told)
    seen.clear()
    brain.describe("अरे यार ये क्या हुआ पागल है क्या", title="T", uploader="U")
    check("a clip cut by hand, in Hindi: the reading guide is added", bool(seen) and NOTE in seen[0])
guide = brain.INDIA_NOTE
check("the guide tells the AI what the usual reactions mean", all(w in guide for w in ("yaar", "arre", "pagal", "ek number")), True)
check("the guide says to write the hook the way the streamer speaks, in Roman letters", "Hinglish" in guide and "Devanagari" in guide, True)
check("the guide keeps abuse out of the posts", "swear" in guide.lower() or "abuse" in guide.lower(), True)
check("the guide holds nothing that comes from the video", "{" not in guide and "<" not in guide, True)

# ---- "clip it" said in Hindi
def session(trigger_words=""):
    d = tempfile.mkdtemp(prefix="pc-india-live-")
    return live.Session({"title": "t", "uploader": "u", "dir": d, "creator": "", "ai": {}, "source": {"url": "", "name": "t"}},
                        {"trigger_words": trigger_words})


s = session()
s._triggers([{"w": "क्लिप", "s": 10.0, "e": 10.4}])
ok("'clip' said in Hindi starts a check of that moment", bool(s.said) and s.said["t"] == 10.0, s.said)
s = session()
s._triggers([{"w": "clip", "s": 10.0, "e": 10.4}])
check("'clip' said in English still does", bool(s.said))
s = session()
s._triggers([{"w": "क्लिपर", "s": 10.0, "e": 10.4}])
check("a different Hindi word is not mistaken for it", s.said, None)
s = session("clip kar")
s._triggers(ws("अरे क्लिप कर भाई", 40.0))
ok("a creator's phrase typed in Roman letters matches Hindi speech", len(s.manual) == 1, s.manual)
s = session("क्लिप कर")
s._triggers(ws("arre clip kar bhai", 40.0))
ok("a creator's phrase typed in Hindi matches Roman speech", len(s.manual) == 1, s.manual)
s = session("clip kar")
s._triggers(ws("nothing to see here", 40.0))
check("other words do not", s.manual, [])

# ---- the check of the AI setup also tries Hindi and Hinglish
good = [{"start": 6.0, "end": 20.0, "score": 80, "hook": "arre arre yaar", "title": "Police se bhaag gaya", "description": "d",
         "hashtags": ["gta6"], "reason": "r"}]
calls = []


def run_check(answer, argv=None, tiny="ok"):
    calls.clear()

    def fake_call(model, prompt, schema, spec=None, timeout=None):
        calls.append(prompt)
        if prompt == ai.TEST_PROMPT:
            if isinstance(tiny, Exception):
                raise tiny
            return [tiny], 10, 2
        if isinstance(answer, Exception):
            raise answer
        return answer, 300, 40

    spec = {"provider": "ollama", "how": "ollama", "base": "http://127.0.0.1:11434", "key": ""}
    buf = io.StringIO()
    with mock.patch.object(ai, "candidates", return_value=[(spec, "gemma3:12b")]), mock.patch.object(ai, "call", fake_call), \
            contextlib.redirect_stdout(buf):
        code = ai_check.main(argv)
    return code, buf.getvalue()


code, text = run_check(good)
ok("ai_check: a model that finds the moment in Hindi and Hinglish is told so", code == 0 and "Hindi and Hinglish: OK" in text and "ARRE ARRE YAAR" in text, text)
ok("ai_check: the Hindi question is the real one the pipeline asks", len(calls) == 2 and NOTE in calls[1] and "<transcript>" in calls[1], len(calls))
check("ai_check: the sample holds Devanagari and Roman Hinglish", roman.has_hindi(calls[1]) and "bhai" in calls[1])
code, text = run_check([])
ok("ai_check: a model that answers but finds nothing is called weak, with what to try", code == 0 and "Hindi and Hinglish: WEAK" in text and "gemma3" in text, text)
code, text = run_check([{"start": 90.0, "end": 100.0, "score": 80, "hook": "x", "title": "t", "description": "d", "hashtags": [], "reason": "r"}])
ok("ai_check: a moment far from the real one is weak too", "Hindi and Hinglish: WEAK" in text, text)
code, text = run_check(RuntimeError("HTTP 500 boom"))
ok("ai_check: a model that fails on the Hindi question says so, the rest still counts", code == 0 and "Hindi and Hinglish: FAIL" in text and "1 of 1 worked" in text, text)
code, text = run_check(good, argv=["--quick"])
ok("ai_check --quick leaves the Hindi question out", code == 0 and "Hindi" not in text and len(calls) == 1, text)
code, text = run_check(good, tiny=RuntimeError("HTTP 401 no"))
ok("ai_check: a service that fails the tiny question is not asked the Hindi one", len(calls) == 1 and "Hindi" not in text and code == 1, text)

print("ALL PASSED" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
