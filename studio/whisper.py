"""Hindi, Hinglish and other languages: speech to text with Whisper, through sherpa-onnx.

The English model (studio/transcribe.py) is quick and very good, but it only knows English. Whisper knows about a
hundred languages, Hindi among them, and it copes with Hindi that has English words in it ("Hinglish"). It writes
the Hindi in Devanagari letters and leaves the English words as they are; the captions turn the Hindi into Roman
letters later (studio/roman.py).

Four things about the speech library were found by trying it on Hindi speech made by a speech synthesiser (no recording
of a person was at hand), and are worked around here:

  * It stops a piece of speech after about six "tokens" a second, and Hindi needs about fifteen, so Hindi came out
    cut off, usually half a sentence. Padding the piece with silence up to just under 30 seconds raises that limit
    (the model pads to 30 seconds itself, so it hears the same thing). Pieces are kept short too (at most 8
    seconds), and a piece that still comes out cut off is split in two and done again.
  * It gives no word times for Whisper. Words are placed along the stretches of the piece where someone is actually
    talking, in proportion to how long each word is (see _spans).
  * Its language detector hears a lot of spoken Hindi as Urdu (the two sound alike), and Urdu script is no use for
    captions, so Urdu counts as Hindi. Only the small models can tell languages apart, so that job has its own
    (small) model.
  * Whisper sometimes gets stuck in a loop and writes the same few words over and over on music or noise. Those
    pieces are thrown away."""
import os
import re
import threading
import unicodedata
import zlib
from collections import Counter

import numpy as np

from . import config, fetch_model, transcribe as _speech

SR = 16000
PAD_SECONDS = 29.5                 # just under the 30 seconds the library accepts
PIECE_LO, PIECE_HI = 4.0, 8.0      # seconds. Hindi takes about 15 tokens a second and about 175 fit in a padded piece
TOKEN_ROOM = 150                   # text this long may have hit the limit: split the piece and do each half again
FRAME = 320                        # 20 milliseconds, the step the "is someone talking" check works in
THREADS = int(os.environ.get("CLIPIT_WHISPER_THREADS") or max(2, min(8, (os.cpu_count() or 4) - 2)))

# The languages Whisper has a name for. A name outside this list must never reach the library: it would stop the
# whole program instead of raising an error.
LANGUAGES = frozenset(
    "en zh de es ru ko fr ja pt tr pl ca nl ar sv it id hi fi vi he uk el ms cs ro da hu ta no th ur hr bg lt la mi ml "
    "cy sk te fa lv bn sr az sl kn et mk br eu is hy ne mn bs kk sq sw gl mr pa si km sn yo so af oc ka be tg sd gu am "
    "yi lo uz fo ht ps tk nn mt sa lb my bo tl mg as tt haw ln ha ba jw su yue".split())
_NAMES = {"english": "en", "hindi": "hi", "hinglish": "hi", "urdu": "hi", "ur": "hi", "sa": "hi"}

_lock = threading.RLock()
_decode_lock = threading.Lock()
_lid_lock = threading.Lock()
_recs: dict = {}
_lid = None


def normalize_lang(code) -> str:
    """A language code Whisper understands ("hi", "en", "pa"...), or "" if this is not one. "hi-IN" is "hi", the
    names Hindi, Hinglish and English work, and Urdu counts as Hindi."""
    c = str(code or "").strip().lower().replace("_", "-")
    if not c:
        return ""
    c = _NAMES.get(c, c)
    c = _NAMES.get(c.split("-")[0], c.split("-")[0])
    return c if c in LANGUAGES else ""


def setting() -> str:
    """The language setting: "auto", or one language code."""
    v = str(config.LANGUAGE or "").strip().lower()
    if v in ("", "auto"):
        return "auto"
    return normalize_lang(v) or "auto"


def lid_name() -> str:
    """The model that tells languages apart. Only the ones built on 80 mel bands can do it (tiny to medium), so the
    big ones (turbo, large-v3) leave it to the small one."""
    m = config.WHISPER_MODEL
    return m if m in ("tiny", "base", "small", "medium") else "tiny"


def ready(name=None) -> bool:
    return fetch_model.whisper_ready(name or config.WHISPER_MODEL)


def ensure(name=None) -> None:
    name = name or config.WHISPER_MODEL
    if not fetch_model.whisper_ready(name):
        fetch_model.ensure_whisper(name)


def forget() -> None:
    """Let go of the loaded models (they are loaded again when next needed)."""
    global _lid
    with _lock:
        _recs.clear()
        _lid = None


def _recognizer(lang: str):
    sherpa_onnx = _speech._sherpa()          # the speech library, loaded once (and loadable from a deep Windows folder)
    with _lock:
        name = config.WHISPER_MODEL
        rec = _recs.get((name, lang))
        if rec is None:
            ensure(name)
            enc, dec, tok = fetch_model.whisper_files(name)
            rec = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=enc, decoder=dec, tokens=tok, language=lang, task="transcribe",
                num_threads=THREADS, decoding_method="greedy_search")
            _recs[(name, lang)] = rec
        return rec


def _identifier():
    sherpa_onnx = _speech._sherpa()          # the speech library, loaded once (and loadable from a deep Windows folder)
    global _lid
    with _lock:
        if _lid is None:
            name = lid_name()
            ensure(name)
            enc, dec, _tok = fetch_model.whisper_files(name)
            cfg = sherpa_onnx.SpokenLanguageIdentificationConfig(
                whisper=sherpa_onnx.SpokenLanguageIdentificationWhisperConfig(encoder=enc, decoder=dec),
                num_threads=2, debug=False, provider="cpu")
            _lid = sherpa_onnx.SpokenLanguageIdentification(cfg)
        return _lid


# ---------------------------------------------------------------- which language is spoken
def _rms(x) -> float:
    x = np.asarray(x, dtype=np.float32) / 32768.0
    return float(np.sqrt((x ** 2).mean())) if len(x) else 0.0


def _talking(x) -> bool:
    """Is someone (or something) making sound for at least half of this stretch of audio?"""
    k = len(x) // SR
    if k < 1:
        return _rms(x) >= 0.003
    x = np.asarray(x, dtype=np.float32) / 32768.0
    loud = np.sqrt((x[:k * SR].reshape(k, SR) ** 2).mean(axis=1)) >= 0.003
    return bool(loud.mean() >= 0.5)


def has_speech(audio) -> bool:
    """Is there sound to listen to in this audio (int16, 16 kHz)? Silence is not worth asking about."""
    return bool(_windows(audio))


def _windows(audio, seconds=8.0) -> list:
    """Up to three stretches of about 8 seconds, spread through the video, where there is sound."""
    n, size = len(audio), int(seconds * SR)
    if n <= size + SR:                                  # a short recording: all of it, if there is sound in it
        return [(0, n)] if n and _talking(audio) else []
    kept = [(int(s), int(s) + size) for s in np.linspace(0, n - size, num=9) if _talking(audio[int(s):int(s) + size])]
    return kept if len(kept) <= 3 else [kept[0], kept[len(kept) // 2], kept[-1]]


def detect(audio) -> str:
    """The language spoken in this audio (int16, 16 kHz), as a code: listens at a few spots and goes with the
    majority. Silence, or no majority, gives "en" (the quick, safe choice). Raises if the small model cannot be
    had (no internet the first time)."""
    wins = _windows(audio)
    if not wins:
        return "en"
    ident = _identifier()
    votes = []
    for a, b in wins:
        st = ident.create_stream()
        st.accept_waveform(SR, audio[a:b].astype(np.float32) / 32768.0)
        with _lid_lock:
            votes.append(normalize_lang(ident.compute(st)))
    votes = [v for v in votes if v]
    if not votes:
        return "en"
    top, n = Counter(votes).most_common(1)[0]
    return top if n >= 2 or len(wins) == 1 else "en"


# ---------------------------------------------------------------- words, and where each one goes
def usable(text: str, seconds: float) -> bool:
    """Is this real speech, and not the model making things up? Nobody says more than nine words a second, and
    text that is the same few words over and over (it compresses far better than speech does) is a loop the model
    got stuck in. Short bursts like laughter are left alone."""
    t = (text or "").strip()
    if not t:
        return False
    if seconds > 0 and len(t.split()) / seconds > 9:
        return False
    if len(t) >= 24:
        raw = t.encode("utf-8")
        if len(raw) / len(zlib.compress(raw)) > 3.0:     # real Hindi, English and mixed text come out at 1.3 to 2.2
            return False
    return True


def _is_mark(tok: str) -> bool:
    return all(unicodedata.category(c)[0] in "PS" for c in tok)


def _split(text: str) -> list:
    """The words of a line, each with its punctuation. A mark standing on its own goes back onto the word before."""
    out, lead = [], ""
    for tok in text.split():
        if _is_mark(tok):
            if out:
                out[-1] += tok
            else:
                lead += tok
            continue
        out.append(lead + tok)
        lead = ""
    return out


def _weight(word: str) -> float:
    """About how long a word takes to say. A letter counts one, a vowel sign half, a joining mark nothing, and a
    digit three (it is spoken as a whole word). Never less than one."""
    total = 0.0
    for c in word:
        cat = unicodedata.category(c)
        if cat[0] == "N":
            total += 3
        elif cat[0] == "L":
            total += 1
        elif cat in ("Mc", "Mn"):
            total += 0 if c in "़्" else 0.5      # the virama and the nukta add no sound of their own
    return max(1.0, total)


def _runs(v):
    if len(v) == 0:
        return []
    edges = np.flatnonzero(np.diff(v.astype(np.int8))) + 1
    starts, ends = np.concatenate([[0], edges]), np.concatenate([edges, [len(v)]])
    return [(bool(v[s]), int(s), int(e - s)) for s, e in zip(starts, ends)]


def _voiced(seg) -> np.ndarray:
    """For every 20 ms of a piece: is someone talking? Judged against the piece's own quiet and loud levels, and
    smoothed: a short dip inside a word is not a pause, and a short blip is not speech."""
    n = len(seg) // FRAME
    if n < 2:
        return np.zeros(n, dtype=bool)
    x = np.asarray(seg[:n * FRAME], dtype=np.float32).reshape(n, FRAME)
    e = np.convolve(np.sqrt((x * x).mean(axis=1)), np.ones(3) / 3, mode="same")
    low, high = float(np.percentile(e, 10)), float(np.percentile(e, 95))
    if high < 0.003:
        return np.zeros(n, dtype=bool)
    v = e > max(low + 0.2 * (high - low), 0.002)
    for val, s, k in _runs(v):                  # a gap shorter than 120 ms between talking is not a pause
        if not val and k < 6 and s > 0 and s + k < n:
            v[s:s + k] = True
    for val, s, k in _runs(v):                  # a burst shorter than 60 ms is not speech
        if val and k < 3:
            v[s:s + k] = False
    return v


def _spans(seg, weights) -> list:
    """(start, end) in seconds, within the piece, for words of the given weights. The words are laid out along the
    time when someone is talking, so pauses stay pauses and no word is put on silence. If there is nothing to go
    by, they are shared out over the whole piece."""
    n = max(1, len(seg) // FRAME)
    idx = np.flatnonzero(_voiced(seg))
    if len(idx) < len(weights):
        idx = np.arange(n)
    count = len(idx)
    cum = np.concatenate([[0.0], np.cumsum(weights)]) / float(sum(weights))
    out = []
    for i in range(len(weights)):
        s = int(idx[min(count - 1, int(cum[i] * count))])
        e = int(idx[min(count - 1, max(0, int(np.ceil(cum[i + 1] * count - 1e-9)) - 1))]) + 1
        out.append((s * FRAME / SR, max(e, s + 1) * FRAME / SR))
    return out


def _place(text: str, audio, a: int, b: int) -> list:
    """The words of `text`, said in audio[a:b], with their times in the whole video."""
    words = _split(text)
    if not words:
        return []
    seg = np.asarray(audio[a:b], dtype=np.float32) / 32768.0
    off = a / SR
    return [{"w": w, "s": round(off + s, 2), "e": round(off + e, 2)}
            for w, (s, e) in zip(words, _spans(seg, [_weight(w) for w in words]))]


# ---------------------------------------------------------------- listening
def _heard(rec, seg) -> str:
    """What Whisper writes for one piece (float32). It goes in padded with silence to just under 30 seconds: that is
    what makes the library allow enough tokens for Hindi."""
    padded = np.zeros(int(PAD_SECONDS * SR), dtype=np.float32)
    k = min(len(seg), len(padded))
    padded[:k] = seg[:k]
    st = rec.create_stream()
    st.accept_waveform(SR, padded)
    with _decode_lock:
        rec.decode_stream(st)
    return (st.result.text or "").strip()


def _cut(audio, a: int, b: int) -> int:
    """Where to split a piece: the quietest moment in its middle third, so no word is cut in half."""
    hop = 800
    lo, hi = a + int((b - a) * 0.35), a + int((b - a) * 0.65)
    k = (hi - lo) // hop
    if k < 2:
        return (a + b) // 2
    e = np.abs(np.asarray(audio[lo:lo + k * hop], dtype=np.float32)).reshape(k, hop).mean(axis=1)
    return lo + int(np.argmin(e)) * hop + hop // 2


def _piece(rec, audio, a: int, b: int, depth: int = 0) -> list:
    seg = np.asarray(audio[a:b], dtype=np.float32) / 32768.0
    if len(seg) < 4800 or _rms(audio[a:b]) < 0.003:
        return []                                       # silence: skipped, saves time and avoids made-up words
    seconds = len(seg) / SR
    try:
        text = _heard(rec, seg)
    except UnicodeDecodeError:
        text = None                                     # cut off in the middle of a letter: the limit was hit
    if (text is None or len(text) >= TOKEN_ROOM) and seconds > 3.0 and depth < 2:
        cut = _cut(audio, a, b)                         # probably cut off at the limit: each half gets its own room
        return _piece(rec, audio, a, cut, depth + 1) + _piece(rec, audio, cut, b, depth + 1)
    if not text or not usable(text, seconds):
        return []
    return _place(text, audio, a, b)


def transcribe(audio, lang: str, on_progress=None) -> list:
    """[{'w': word, 's': start, 'e': end}, ...] for the whole audio (int16, 16 kHz) spoken in `lang`, the same
    shape the English model gives. Done in pieces of 4 to 8 seconds cut at quiet moments."""
    lang = normalize_lang(lang) or "hi"
    pieces = [(a, b) for a, b in _speech._chunks(audio, PIECE_LO, PIECE_HI) if b - a >= 4800 and _rms(audio[a:b]) >= 0.003]
    if not pieces:
        return []
    rec = _recognizer(lang)                              # only now: a video with nobody talking loads nothing
    words = []
    for n, (a, b) in enumerate(pieces, 1):
        words += _piece(rec, audio, a, b)
        if on_progress:
            on_progress(n / len(pieces))
    return _speech.lengthen(words)
