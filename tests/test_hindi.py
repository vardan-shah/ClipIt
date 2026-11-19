"""Hindi, Hinglish and English speech: how ClipIt tells which language a video is in, how Hindi is handed to the
speech library (which has quirks the code works around), and how every word gets its time.

No speech model is run and nothing is downloaded: the speech library is replaced by a stand-in that "hears" whatever
the test tells it to. So these checks are about ClipIt's own choices. (The real models were tried by hand on real
Hindi speech; see FREE.md for what was found.)"""
import os, sys, tempfile, types
os.environ["CLIPIT_DATA"] = tempfile.mkdtemp(prefix="pc-hindi-"); os.environ["DATABASE_URL"] = ""
for k in ("CLIPIT_MODELS", "CLIPIT_LANGUAGE", "CLIPIT_WHISPER_MODEL"):
    os.environ.pop(k, None)
sys.path.insert(0, ".")
import numpy as np

fails = []
def check(n, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"   got {got!r}")); ok or fails.append(n)

SR = 16000
rng = np.random.default_rng(7)
def speech(seconds, level=0.2):
    return (rng.standard_normal(int(seconds * SR)) * level * 32767).clip(-32768, 32767).astype(np.int16)
def silence(seconds):
    return (rng.standard_normal(int(seconds * SR)) * 0.0004 * 32767).astype(np.int16)
def rms(x):
    x = np.asarray(x, dtype=np.float32)
    x = x / 32768.0 if x.dtype != np.float32 or np.abs(x).max() > 1.5 else x
    return float(np.sqrt((x ** 2).mean()))

# ---------------------------------------------------------------- the speech library, as a stand-in
calls = {"made": [], "decoded": [], "lid_made": [], "lid": []}
script = {"texts": [], "langs": []}                     # what the stand-in hears next, in order
class Broken:                                           # text that cannot be read: the library cut a letter in half
    @property
    def text(self):
        raise UnicodeDecodeError("utf-8", b"\xe0\xa4", 0, 2, "unexpected end of data")
class Stream:
    def __init__(self):
        self.samples, self.result = None, types.SimpleNamespace(text="", lang="")
    def accept_waveform(self, sr, x):
        assert sr == SR
        self.samples = np.asarray(x, dtype=np.float32)
class Recognizer:
    def __init__(self, kw):
        self.kw = kw
    def create_stream(self):
        return Stream()
    def decode_stream(self, st):
        nz = np.flatnonzero(st.samples)
        calls["decoded"].append((self.kw["language"], st.samples, int(nz[-1]) + 1 if len(nz) else 0))
        t = script["texts"].pop(0) if script["texts"] else "ठीक है दोस्तों"
        st.result = Broken() if t == "BROKEN" else types.SimpleNamespace(text=t, lang=self.kw["language"])
class OfflineRecognizer:
    @staticmethod
    def from_whisper(**kw):
        calls["made"].append(kw)
        return Recognizer(kw)
class Identifier:
    def __init__(self, cfg):
        calls["lid_made"].append(cfg)
    def create_stream(self):
        return Stream()
    def compute(self, st):
        calls["lid"].append(st.samples)
        return script["langs"].pop(0) if script["langs"] else "en"
fake = types.ModuleType("sherpa_onnx")
fake.OfflineRecognizer = OfflineRecognizer
fake.SpokenLanguageIdentification = Identifier
fake.SpokenLanguageIdentificationConfig = lambda **kw: types.SimpleNamespace(**kw)
fake.SpokenLanguageIdentificationWhisperConfig = lambda **kw: types.SimpleNamespace(**kw)
sys.modules["sherpa_onnx"] = fake

from studio import config, fetch_model, jobs, transcribe, whisper

def put_model(name, kinds=("int8",)):
    d = config.MODELS_DIR / f"sherpa-onnx-whisper-{name}"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}-tokens.txt").write_text("x")
    for kind in kinds:
        for part in ("encoder", "decoder"):
            (d / (f"{name}-{part}.{kind}.onnx" if kind else f"{name}-{part}.onnx")).write_bytes(b"m")
def fresh(texts=(), langs=()):
    whisper.forget()
    for v in calls.values():
        v.clear()
    script["texts"][:] = list(texts)
    script["langs"][:] = list(langs)

# ---------------------------------------------------------------- language codes and the setting
norm = whisper.normalize_lang
check("Urdu counts as Hindi (the two sound alike, and Urdu script is no use for captions)", [norm("ur"), norm("urdu"), norm("UR")], ["hi"] * 3)
check("a regional form of a code is the code", [norm(x) for x in ("hi-IN", "en-US", "en_GB", "hi-Latn")], ["hi", "en", "en", "hi"])
check("names work: Hindi, Hinglish and English", [norm("Hindi"), norm("Hinglish"), norm("English")], ["hi", "hi", "en"])
check("other Indian languages stay as they are", [norm(x) for x in ("pa", "gu", "mr", "ta", "te", "bn")], ["pa", "gu", "mr", "ta", "te", "bn"])
check("a language Whisper has no name for is not passed on (the library would stop the whole server)",
      [norm("xx"), norm("klingon"), norm(""), norm(None)], [""] * 4)
for value, want in (("auto", "auto"), ("", "auto"), ("Hindi", "hi"), ("hinglish", "hi"), ("en", "en"), ("klingon", "auto"), ("pa", "pa")):
    config.LANGUAGE = value
    check(f"the setting {value!r} means {want!r}", whisper.setting(), want)
config.LANGUAGE = "auto"

# ---------------------------------------------------------------- which model listens for the language
for name, want in (("turbo", "tiny"), ("large-v3", "tiny"), ("small", "small"), ("base", "base"), ("tiny", "tiny")):
    config.WHISPER_MODEL = name
    check(f"{name} picks the language with {want} (the big ones cannot do it)", whisper.lid_name(), want)
config.WHISPER_MODEL = "turbo"

# ---------------------------------------------------------------- telling the language of a video
put_model("tiny"); put_model("turbo")
long = speech(60)
fresh(langs=["hi", "hi", "en"])
check("two of three listening spots hear Hindi: Hindi", transcribe.choose_language(long), "hi")
check("it listens at 1 to 3 spots, each up to 10 seconds, only where someone is talking",
      (1 <= len(calls["lid"]) <= 3, all(len(w) <= 10 * SR and rms(w) > 0.003 for w in calls["lid"])), (True, True))
patchy = np.concatenate([silence(20), speech(12), silence(20)])
fresh(langs=["hi"] * 3)
transcribe.choose_language(patchy)
check("in a video that is quiet except for the middle, it listens to the middle", bool(calls["lid"]) and all(rms(w) > 0.003 for w in calls["lid"]))
for heard, want in ((["en", "en", "hi"], "en"), (["ur", "hi", "ur"], "hi"), (["hi", "en", "pa"], "en"), (["en", "en", "en"], "en")):
    fresh(langs=heard)
    check(f"hearing {heard} gives {want}", transcribe.choose_language(long), want)
fresh()
check("YouTube's own word on the language is trusted, with no listening",
      ([transcribe.choose_language(long, hint=h) for h in ("hi", "en-US", "ur", "hi-IN")], calls["lid"]), (["hi", "en", "hi", "hi"], []))
config.LANGUAGE = "hi"
check("a language set by hand is used as it is", (transcribe.choose_language(long), calls["lid"]), ("hi", []))
config.LANGUAGE = "en"
check("...even over what YouTube says", transcribe.choose_language(long, hint="hi"), "en")
config.LANGUAGE = "auto"
fresh()
check("a video with nobody talking is English, with no listening", (transcribe.choose_language(silence(30)), calls["lid"]), ("en", []))
short = speech(5)
fresh(langs=["hi"])
check("a short recording is listened to whole", (transcribe.choose_language(short), len(calls["lid"]), len(calls["lid"][0])), ("hi", 1, len(short)))
fresh()
check("a short recording with nobody talking is English, with no listening", (transcribe.choose_language(silence(5)), calls["lid"]), ("en", []))

# the language model cannot be fetched (no internet): the video is still done, as English
whisper.forget()
for p in (config.MODELS_DIR / "sherpa-onnx-whisper-tiny").iterdir():
    p.unlink()
(config.MODELS_DIR / "sherpa-onnx-whisper-tiny").rmdir()
def no_internet(name):
    raise RuntimeError("ClipIt couldn't download its speech model.")
real_ensure = fetch_model.ensure_whisper
fetch_model.ensure_whisper = no_internet
said = []
check("no way to get the language model: English, and it says so in plain words", (transcribe.choose_language(long, note=said.append), bool(said) and "English" in said[0]), ("en", True))
fetch_model.ensure_whisper = real_ensure
put_model("tiny")

# ---------------------------------------------------------------- Hindi through Whisper
HINDI = "अरे भाई, ये क्या हो गया?"
five = speech(5.0)
fresh(texts=[HINDI])
words = transcribe.transcribe(five, lang="hi")
check("Hindi words come back one by one, punctuation stays on its word", [w["w"] for w in words], ["अरे", "भाई,", "ये", "क्या", "हो", "गया?"])
lang_used, fed, n_real = calls["decoded"][0]
check("the piece goes in padded with silence to just under 30 s (without it the library cuts Hindi off)",
      (len(fed), n_real == len(five), bool(np.allclose(fed[:len(five)], five / 32768.0, atol=1e-6)), bool(not fed[len(five):].any())),
      (int(29.5 * SR), True, True, True))
check("the model was told it is Hindi, to write down what is said (not translate it into English), and uses the compact files",
      (calls["made"][0]["language"], calls["made"][0]["task"], calls["made"][0]["encoder"].endswith("turbo-encoder.int8.onnx")), ("hi", "transcribe", True))
check("every word is inside the piece, in order", all(0 <= w["s"] < w["e"] <= 5.61 for w in words) and all(words[i]["s"] <= words[i + 1]["s"] for i in range(len(words) - 1)))
transcribe.transcribe(five, lang="hi")
check("the model is loaded once for a language, not for every piece", len(calls["made"]), 1)
transcribe.transcribe(five, lang="ur")
check("Urdu is done as Hindi", len(calls["made"]), 1)
transcribe.transcribe(five, lang="pa")
check("another language gets its own copy, told that language", [m["language"] for m in calls["made"]], ["hi", "pa"])

fresh(texts=[HINDI])
whisper.transcribe(five, "ur")
whisper.transcribe(five, "klingon")
check("Whisper's own entry point also turns Urdu, or a code it has no name for, into Hindi before the library sees it", [m["language"] for m in calls["made"]], ["hi"])

config.WHISPER_MODEL = "small"
put_model("small", kinds=("",))
fresh(texts=[HINDI])
transcribe.transcribe(five, lang="hi")
check("when there are no compact files, the full ones are used", calls["made"][0]["encoder"].endswith("small-encoder.onnx"), True)
config.WHISPER_MODEL = "turbo"
put_model("base", kinds=("int8", ""))
check("when both the compact and the full files are there, the compact ones are used", fetch_model.whisper_files("base")[0].endswith("base-encoder.int8.onnx"), True)

# pieces are short (Hindi takes a lot of room), and nothing is lost between them
fresh()
audio = speech(30)
words = transcribe.transcribe(audio, lang="hi")
sizes = [n for _, _, n in calls["decoded"]]
check("a long stretch is cut into pieces of at most 8 seconds", (len(sizes) >= 4, all(s <= 8.0 * SR + 1 for s in sizes)), (True, True))
check("...and the pieces together are all of it", abs(sum(sizes) - len(audio)) <= 1, True)
check("words from later pieces come later (times are for the whole video)", all(words[i]["s"] <= words[i + 1]["s"] for i in range(len(words) - 1)) and words[-1]["e"] <= 30.7)
progress = []
fresh()
transcribe.transcribe(speech(20), lang="hi", on_progress=progress.append)
check("progress goes up to 100%", (progress == sorted(progress), progress[-1]), (True, 1.0))

# silence, loops and nonsense are not turned into words
fresh()
check("silence is skipped, with no work done (the model is not even loaded)", (transcribe.transcribe(silence(6), lang="hi"), calls["decoded"], calls["made"]), ([], [], []))
fresh(texts=["लाफ " * 30])
check("a loop the model got stuck in is thrown away", transcribe.transcribe(speech(5), lang="hi"), [])
natural = ("अरे भाई, ये क्या हो गया? मैंने तो सोचा भी नहीं था कि गेम में ऐसा होगा। दोस्तों, आज हम जीटीए सिक्स की लाइव स्ट्रीम कर रहे हैं, चैनल को सब्सक्राइब ज़रूर करना। "
           "ये सबसे ज़बरदस्त क्लिप है, पूरी दुनिया पागल हो गई है। पुलिस ने मुझे चारों तरफ से घेर लिया, लेकिन मैं बच निकला! आप सबको बहुत बहुत धन्यवाद, अगले वीडियो में फिर मिलेंगे। "
           "यार, ये गाड़ी तो बहुत तेज़ है, देखो कितनी स्पीड है इसकी।")
check("more speech than a person could say in the time is thrown away, the same words in enough time are kept",
      (whisper.usable(natural, 4.0), whisper.usable(natural, 30.0)), (False, True))
check("normal Hindi, English, and laughter are kept", [whisper.usable(t, 5.0) for t in (HINDI + " मैंने तो सोचा भी नहीं था कि गेम में ऐसा होगा", "yes", "हा हा हा हा हा")], [True] * 3)
check("repeated English is thrown away too", whisper.usable("thank you " * 30, 5.0), False)
check("empty is not a word", whisper.usable("  ", 5.0), False)

# a piece the library cut off at its limit is done again in two halves
cut_off = "क" * 160
fresh(texts=[cut_off, "पहला हिस्सा", "दूसरा हिस्सा"])
words = transcribe.transcribe(speech(7.5), lang="hi")
check("a piece that came out very long is split in two and each half done again", ([w["w"] for w in words], len(calls["decoded"])), (["पहला", "हिस्सा", "दूसरा", "हिस्सा"], 3))
check("the second half's words come after the cut", words[2]["s"] >= 7.5 * 0.35 - 0.01)
fresh(texts=[cut_off] * 20)
transcribe.transcribe(speech(7.5), lang="hi")
check("this stops after two rounds of splitting", len(calls["decoded"]) <= 7, True)
def with_gaps(total, gaps):
    x = speech(total)
    for a_, b_ in gaps:
        i, j = int(round(a_ * SR)), int(round(b_ * SR))
        x[i:j] = (rng.standard_normal(j - i) * 0.0004 * 32767).astype(np.int16)
    return x
fresh(texts=[cut_off] * 20)
transcribe.transcribe(with_gaps(8.0, [(5.05, 5.15), (1.85, 2.0)]), lang="hi")      # quiet spots made so that the pieces stay over 3 s for two rounds
check("splitting stops after two rounds even when the pieces are still long (5 listens, no more)", len(calls["decoded"]), 5)
fresh(texts=[cut_off] * 20)
transcribe.transcribe(speech(2.0), lang="hi")
check("a piece under 3 seconds is never split", len(calls["decoded"]), 1)
fresh(texts=[cut_off, "पहला हिस्सा", "दूसरा हिस्सा"])
words = transcribe.transcribe(np.concatenate([speech(3.0), silence(4.5)]), lang="hi")
check("when a piece is split and one half is only silence, that half is not listened to", ([w["w"] for w in words], len(calls["decoded"])), (["पहला", "हिस्सा"], 2))
fresh(texts=["हाँ"])
words = transcribe.transcribe(np.concatenate([silence(0.2), speech(0.3), silence(1.0)]), lang="hi")
check("a short word before a pause is given time to be read (0.6 s), as with the English words", 0.55 <= words[0]["e"] - words[0]["s"] <= 0.65, True)
fresh(texts=["BROKEN", "ठीक है", "चलो यार"])
words = transcribe.transcribe(speech(7.5), lang="hi")
check("text cut in the middle of a letter counts as too long: split and done again", [w["w"] for w in words], ["ठीक", "है", "चलो", "यार"])
fresh(texts=["BROKEN"] * 20)
check("...and if that never works, the piece is dropped without an error", transcribe.transcribe(speech(7.5), lang="hi"), [])

# ---------------------------------------------------------------- splitting text into words
split = whisper._split
check("words keep their punctuation", split("अरे भाई, ये क्या हो गया?"), ["अरे", "भाई,", "ये", "क्या", "हो", "गया?"])
check("a mark on its own goes back onto the word before", (split("है ।"), split("हैं . चैनल"), split("क्या ? ")), (["है।"], ["हैं.", "चैनल"], ["क्या?"]))
check("nothing in, nothing out", (split(""), split("   ")), ([], []))
check("English inside Hindi stays as it is", split("दोस्तों, आज हम GTA 6 की लाइव"), ["दोस्तों,", "आज", "हम", "GTA", "6", "की", "लाइव"])
w = whisper._weight
check("a longer word takes longer to say", w("स्ट्रीम") > w("की") and w("GTA") > w("to"), True)
check("a number takes as long as saying it", w("6") >= 2, True)
check("no word weighs nothing", min(w("?"), w("।"), w("ं"), w("a")) >= 1, True)

# ---------------------------------------------------------------- placing words where someone is talking
def f32(x):
    return x.astype(np.float32) / 32768.0
sig = f32(np.concatenate([silence(0.3), speech(1.0), silence(1.2), speech(1.0), silence(0.3)]))      # talking 0.3-1.3 and 2.5-3.5
voiced = lambda gap: whisper._voiced(f32(np.concatenate([silence(0.5), speech(1.0), silence(gap), speech(1.0), silence(0.5)])))
check("a dip of 0.1 s inside talking is not a pause, one of 0.3 s is", (bool(voiced(0.1)[77]), bool(voiced(0.3)[82])), (True, False))
spans = whisper._spans(sig, [1, 1, 1, 1])
inside = lambda t: 0.3 - 0.07 <= t <= 1.3 + 0.07 or 2.5 - 0.07 <= t <= 3.5 + 0.07
check("each word lies where there is speech, none in the pause", all(inside(s) and inside(e) for s, e in spans), True)
check("words are in order", all(spans[i][1] <= spans[i + 1][0] + 0.001 for i in range(3)))
check("the pause stays a pause: the second word ends where the talking stops, the third starts where it starts again",
      (abs(spans[1][1] - 1.3) < 0.08, abs(spans[2][0] - 2.5) < 0.08), (True, True))
one = f32(speech(4.0))
a, b = whisper._spans(one, [1, 3])
check("a word three times as long gets three times the time", (abs((a[1] - a[0]) - 1.0) < 0.15, abs((b[1] - b[0]) - 3.0) < 0.15), (True, True))
q = whisper._spans(f32(silence(3.0)), [1, 1, 1])
check("a piece the energy cannot read is shared out evenly over its length", (len(q), all(0 <= s < e <= 3.01 for s, e in q), all(q[i][1] <= q[i + 1][0] + 0.001 for i in range(2))), (3, True, True))
check("one word fills the talking", (lambda s: abs(s[0][0] - 0.3) < 0.08 and abs(s[0][1] - 1.3) < 0.08)(whisper._spans(f32(np.concatenate([silence(0.3), speech(1.0), silence(0.5)])), [2])), True)
video = np.concatenate([silence(10), silence(0.5), speech(2.0), silence(0.5)])         # 13 s; the piece is the last 3 s
timed = whisper._place("एक दो तीन", video, 10 * SR, 13 * SR)
check("placed words carry the piece's place in the whole video", (timed[0]["s"] >= 10.4, timed[-1]["e"] <= 13.01, [x["w"] for x in timed]), (True, True, ["एक", "दो", "तीन"]))

# ---------------------------------------------------------------- the English way is unchanged
seen = []
real_whisper_transcribe = whisper.transcribe
whisper.transcribe = lambda audio, lang, on_progress=None: seen.append(lang) or [{"w": "namaste", "s": 0.0, "e": 0.5}]
transcribe._take_now = lambda: object()
transcribe.decode_pieces = lambda pieces, rec=None: [(["▁hello", "▁world"], [0.1, 0.9]) for _ in pieces]
heard = {}
for label, lang in (("no language given", None), ("English", "en"), ("empty", ""), ("a regional English", "en-IN")):
    heard[label] = [w["w"] for w in transcribe.transcribe(speech(5.0), lang=lang)]
check("with no language, or English, Parakeet does it exactly as before", (list(heard.values()), seen), ([["hello", "world"]] * 4, []))
check("Hindi goes to Whisper", ([w["w"] for w in transcribe.transcribe(speech(5.0), lang="hi")], seen), (["namaste"], ["hi"]))
transcribe.transcribe(speech(5.0), lang="ur")
check("Urdu goes to Whisper as Hindi", seen[-1], "hi")
whisper.transcribe = real_whisper_transcribe

# ---------------------------------------------------------------- which models are fetched when ClipIt starts
def plan(language):
    config.LANGUAGE = language
    return fetch_model.startup_plan()
check("English only: just the English speech model", plan("en"), [("speech", config.ASR_MODEL_NAME)])
check("automatic: the English one, and the small one that tells the languages apart (the big Hindi one waits until Hindi is heard)",
      plan("auto"), [("speech", config.ASR_MODEL_NAME), ("whisper", "tiny")])
check("Hindi by setting: the English one and the big Hindi one", plan("hi"), [("speech", config.ASR_MODEL_NAME), ("whisper", "turbo")])
config.LANGUAGE = "auto"
config.WHISPER_MODEL = "small"
check("with the lighter model, one download does both jobs", plan("auto"), [("speech", config.ASR_MODEL_NAME), ("whisper", "small")])
config.WHISPER_MODEL = "turbo"
check("English done on another machine (the graphics-card server): its model is not fetched here, the Whisper ones still are",
      (fetch_model.startup_plan(remote_speech=True), fetch_model.startup_plan(remote_speech=False)),
      ([("whisper", "tiny")], [("speech", config.ASR_MODEL_NAME), ("whisper", "tiny")]))
asked = []
real_en, real_wh = fetch_model.ensure, fetch_model.ensure_whisper
fetch_model.ensure, fetch_model.ensure_whisper = (lambda: asked.append("english")), (lambda name: asked.append(name))
fetch_model.fetch_plan([("speech", "x"), ("whisper", "tiny"), ("whisper", "turbo")])
fetch_model.ensure, fetch_model.ensure_whisper = real_en, real_wh
check("each model in the plan is fetched, in order", asked, ["english", "tiny", "turbo"])
try:
    fetch_model.ensure_whisper("../../etc")
    refused = False
except ValueError:
    refused = True
check("a model name that is not on the list never becomes part of a download address", refused, True)
check("the download sizes are known for every model", all(fetch_model.WHISPER_MB.get(n, 0) > 50 for n in ("tiny", "base", "small", "medium", "turbo", "large-v3")), True)

# ---------------------------------------------------------------- what a job does with it
import shutil
shutil.rmtree(config.MODELS_DIR / "sherpa-onnx-whisper-turbo")                                  # the big model is not on this computer yet
stages, jobsaved = [], []
real_set, real_save = jobs._set, jobs.save
jobs._set = lambda job, **kw: (job.update(kw), stages.append(kw.get("stage")))
jobs.save = lambda job: jobsaved.append(1)
fetched = []
real_ensure_w = whisper.ensure
whisper.ensure = lambda name=None: fetched.append(name or config.WHISPER_MODEL)
real_choose = transcribe.choose_language
transcribe.choose_language = lambda audio, hint="", note=None: "hi"
transcribe.choose_language = lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not listen"))
check("YouTube's words for a Hindi video: Hindi, no listening, and the big model is not fetched (YouTube's words are used)",
      (jobs._speech_language({"id": "j0", "lang": "hi"}, long, ([], "hi"), []), fetched), ("hi", []))
transcribe.choose_language = lambda audio, hint="", note=None: "hi"
job = {"id": "job-1", "lang": ""}
check("a job with no YouTube words listens, and remembers the language", (jobs._speech_language(job, long, None, []), job.get("speech_lang")), ("hi", "hi"))
check("it says it is getting the Hindi model, once, because it was not there", (any("Hindi" in (s or "") for s in stages), fetched), (True, ["turbo"]))
put_model("turbo")
stages.clear(); fetched.clear()
job2 = {"id": "job-2", "lang": ""}
jobs._speech_language(job2, long, None, [])
check("with the model already there, nothing is fetched and nothing is announced", (fetched, [s for s in stages if s and "Hindi" in s]), ([], []))
transcribe.choose_language = lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not listen"))
check("a job that was resumed keeps the language it had", jobs._speech_language({"id": "j3", "lang": "", "speech_lang": "hi"}, long, None, []), "hi")
check("YouTube's words for a Hindi video: Hindi, no listening", jobs._speech_language({"id": "j4", "lang": "hi"}, long, ([], "hi"), []), "hi")
check("YouTube's words for an English video: English", jobs._speech_language({"id": "j5", "lang": "en-US"}, long, ([], "en-US"), []), "en")
transcribe.choose_language = lambda audio, hint="", note=None: "en"
stages.clear(); fetched.clear()
check("an English video is English, and nothing extra is fetched", (jobs._speech_language({"id": "j6", "lang": ""}, long, None, []), fetched), ("en", []))
jobs._set, jobs.save = real_set, real_save
whisper.ensure = real_ensure_w
transcribe.choose_language = real_choose

# ---------------------------------------------------------------- a whole video, start to finish
import shutil, subprocess
from pathlib import Path
from studio import auth, brain, ctx, db
db.init()
owner, _ = auth._create("owner@example.com", "Owner", password_hash="x")
video_file = Path(os.environ["CLIPIT_DATA"]) / "hindi-test.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=12", "-f", "lavfi",
                "-i", "color=c=black:s=320x240:d=12", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video_file)], check=True)
SAID = "दोस्तों आज हम गेम खेलेंगे और बहुत मज़ा आएगा यार चलो शुरू करते हैं"
saw = {"lang": [], "ai_words": []}
def listen_stub(audio, on_progress=None, lang=None):
    saw["lang"].append(lang)
    return [{"w": w, "s": round(i * 0.5, 2), "e": round(i * 0.5 + 0.4, 2)} for i, w in enumerate(SAID.split())]
def find_stub(words, *a, **k):
    saw["ai_words"].append([w["w"] for w in words])
    return [], {"model": None, "tokens": 0}
transcribe.transcribe, transcribe.model_ready = listen_stub, lambda: True
brain.find_clips = find_stub
def run_video(language):
    transcribe.choose_language = lambda audio, hint="", note=None: language
    saw["lang"].clear(); saw["ai_words"].clear()
    with ctx.as_user(owner.id):
        job = jobs.create({"type": "file", "path": str(video_file), "name": "hindi-test.mp4"}, {}, enqueue=False)
        jobs._run_job(job)
    return job
job = run_video("hi")
check("a Hindi video finishes, and is transcribed as Hindi, not left to the English model", (job["status"], saw["lang"]), ("done", ["hi"]))
check("...its words reach the AI that picks the clips", saw["ai_words"], [SAID.split()])
check("...the job remembers the language, and the captions are written as Hindi", (job.get("speech_lang"), job.get("lang")), ("hi", "hi"))
job = run_video("en")
check("an English video is transcribed as English, and nothing is marked as Hindi", (job["status"], saw["lang"], job.get("speech_lang"), job.get("lang") or ""), ("done", ["en"], "en", ""))

# ---------------------------------------------------------------- live recordings
from studio import live, media
transcribe.choose_language = real_choose
config.LANGUAGE = "auto"
listened = []
transcribe.transcribe = lambda audio, on_progress=None, lang=None: (listened.append(lang), [{"w": "namaste", "s": 0.1, "e": 0.5}])[1]
def new_session(**extra):
    d = Path(tempfile.mkdtemp(prefix="pc-live-", dir=os.environ["CLIPIT_DATA"]))
    job = {"id": "live-1", "dir": str(d), "user": owner.id, "clips": [], "ai": {}, "creator": "c1", "title": "Stream", "uploader": "u",
           "stage": "Recording", **extra}
    return live.Session(job, {})
def passes(sess, n, make=lambda: speech(8.0)):
    for _ in range(n):
        sess.pending = bytearray(make().tobytes())      # about eight seconds arrive, and are worked on
        sess._transcribe_step()

fresh(langs=["en"] * 3); listened.clear()
sess = new_session()
passes(sess, 3)
check("an English stream: three stretches are listened to, English every time, and nothing is marked as Hindi",
      (len(calls["lid"]), listened, sess.job.get("speech_lang"), "lang" in sess.job), (3, ["en"] * 3, "en", False))
fresh(langs=["hi"] * 3); listened.clear()
sess = new_session()
passes(sess, 1)
early = "speech_lang" in sess.job
passes(sess, 3)
check("a Hindi stream: Hindi from the first stretch on, only settled after three, the fourth is not listened to",
      (listened, len(calls["lid"]), early, sess.job.get("speech_lang"), sess.job.get("lang")), (["hi"] * 4, 3, False, "hi", "hi"))
fresh(langs=["hi"] * 3); listened.clear()
sess = new_session()
passes(sess, 1, lambda: silence(8.0))
passes(sess, 3)
check("silence at the start of a stream does not use up a listening", (listened, len(calls["lid"])), (["en", "hi", "hi", "hi"], 3))
for heard, used, final in ((["hi", "en", "hi"], ["hi", "hi", "hi"], "hi"), (["en", "hi", "hi"], ["en", "en", "hi"], "hi"),
                           (["en", "hi", "pa"], ["en", "en", "en"], "en"), (["hi", "en", "pa"], ["hi", "hi", "en"], "en")):
    fresh(langs=heard); listened.clear()
    sess = new_session()
    passes(sess, 3)
    check(f"a stream heard as {heard} is done as {used}, and ends up {final} (and is only marked as Hindi when it is)",
          (listened, sess.job.get("speech_lang"), sess.job.get("lang")), (used, final, "hi" if final == "hi" else None))
config.LANGUAGE = "hi"
fresh(); listened.clear()
sess = new_session()
passes(sess, 2)
check("a language set by hand is used straight away, with no listening", (listened, calls["lid"], sess.job.get("speech_lang")), (["hi", "hi"], [], "hi"))
config.LANGUAGE = "auto"
fresh(); listened.clear()
sess = new_session(speech_lang="hi")
passes(sess, 1)
check("a recording picked up after a restart keeps its language, with no listening", (listened, calls["lid"]), (["hi"], []))
real_ready, real_ensure_now = whisper.ready, whisper.ensure
at_fetch = []
sess = new_session(speech_lang="hi")
whisper.ready = lambda name=None: False
whisper.ensure = lambda name=None: at_fetch.append(sess.job["stage"])
passes(sess, 1)
check("while the big Hindi model is fetched the recording says so, and goes back to 'Recording' afterwards",
      (at_fetch, sess.job["stage"]), (["Getting the Hindi speech model (one time)"], "Recording"))
whisper.ready, whisper.ensure = real_ready, real_ensure_now

# lining the video pieces up with the live words, for Hindi as well
said_in = {"hi": ["अरे", "भाई", "ये", "क्या", "हो", "गया", "चलो", "देखते", "हैं", "सब", "कुछ"],
           "en": ["so", "this", "clip", "looks", "amazing", "right", "now", "watch", "closely", "everyone", "here"]}
asked = []
def heard_again(audio, on_progress=None, lang=None):
    asked.append((len(audio), lang))
    return [{"w": w, "s": float(i), "e": i + 0.5} for i, w in enumerate(said_in[lang])]
transcribe.transcribe = heard_again
real_extract, real_load = media.extract_audio, media.load_audio
media.extract_audio, media.load_audio = (lambda src, wav: None), (lambda wav: speech(100.0))
for code in ("hi", "en"):
    asked.clear()
    sess = new_session(speech_lang=code)
    sess.words = [{"w": w, "s": 100.0 + i, "e": 100.5 + i} for i, w in enumerate(said_in[code])]
    where = sess._align(Path("clip.mp4"), 95.0, 12.0)
    check(f"{code}: the clip's own words are matched with the live ones, and the clock correction found", where, 100.0)
    check(f"{code}: the clip is listened to in {code}, " + ("the first 45 seconds only" if code == "hi" else "all of it"), asked, [(45 * SR if code == "hi" else 100 * SR, code)])
media.extract_audio, media.load_audio = real_extract, real_load

print("ALL PASSED" if not fails else f"{len(fails)} failed")
import shutil; shutil.rmtree(os.environ["CLIPIT_DATA"], ignore_errors=True)
sys.exit(1 if fails else 0)
