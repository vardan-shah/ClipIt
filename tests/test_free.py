"""Running PeakCut for nothing: Ollama on this machine, several free plans used in turn, and clips that are still
written up when no AI answers. The network is replaced, so nothing leaves this machine and no key is needed."""
import contextlib
import io
import json
import os
import sys
import tempfile
import types

os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="pc-free-")
os.environ["DATABASE_URL"] = ""
os.environ.update(PEAKCUT_AI_PROVIDER="gemini", PEAKCUT_AI_MODELS="model-a, model-b", PEAKCUT_AI_KEY="test-key-123456",
                  PEAKCUT_AI_BASE_URL="", PEAKCUT_AI_KEY_GROQ="groq-key-123456", PEAKCUT_AI_WINDOW_MIN="",
                  PEAKCUT_AI_FALLBACKS="groq:g-model, ollama:llama3.1:8b, nonsense:x, openrouter:meta/llama:free")
sys.path.insert(0, ".")
import httpx  # noqa: E402
import numpy as np  # noqa: E402
from studio import ai, ai_check, auth, brain, config, ctx, db, usage  # noqa: E402

db.init()
fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra and not ok else ""))
    ok or fails.append(name)


class Reply:
    def __init__(self, status, data):
        self.status_code, self._data, self.text = status, data, json.dumps(data)

    def json(self):
        return self._data


CLIP = {"start": 1, "end": 20, "score": 80, "hook": "WOW", "title": "t", "description": "d", "hashtags": ["a"], "reason": "r"}
BUSY, BAD_KEY = Reply(429, {"error": "slow down"}), Reply(401, {"error": "bad key"})
OK_OPENAI = Reply(200, {"choices": [{"message": {"content": json.dumps({"items": [CLIP]})}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
OK_OLLAMA = Reply(200, {"message": {"content": json.dumps({"items": [CLIP]})}, "prompt_eval_count": 40, "eval_count": 8})
OK_GEMINI = Reply(200, {"candidates": [{"content": {"parts": [{"text": json.dumps([CLIP])}]}}], "usageMetadata": {"promptTokenCount": 30, "totalTokenCount": 50}})
GARBLED = Reply(200, {"choices": [{"message": {"content": "Sorry, I could not find any moments."}}], "usage": {}})

seen, script, slept = [], {}, []


def fake_post(url, json=None, headers=None, timeout=None, **_k):  # noqa: A002
    """A word in the address -> the replies to give, in order (the last one is given again and again)."""
    seen.append((url, json, headers or {}))
    for word, replies in script.items():
        if word in url:
            r = replies.pop(0) if len(replies) > 1 else replies[0]
            if isinstance(r, Exception):
                raise r
            return r
    return Reply(404, {})


def hits(word):
    return sum(1 for u, _b, _h in seen if word in u)


def reset(**replies):
    seen.clear()
    slept.clear()
    script.clear()
    script.update({k: list(v) for k, v in replies.items()})


ai.httpx.post = fake_post
brain.time = types.SimpleNamespace(sleep=lambda s: slept.append(s))      # no real waiting in a test

# ---- which services are used, and in what order
fb = ai.fallbacks()
check("fallbacks: those set up are kept, in order, with their own key and address",
      [(s["provider"], m) for s, m in fb] == [("groq", "g-model"), ("ollama", "llama3.1:8b")]
      and fb[0][0]["key"] == "groq-key-123456" and fb[0][0]["base"].startswith("https://api.groq.com")
      and fb[1][0]["base"] == "http://127.0.0.1:11434", str(fb))
check("fallbacks: a model id with colons survives, an unknown service and one without a key are left out",
      "x" not in [m for _s, m in fb] and "meta/llama:free" not in [m for _s, m in fb])
check("candidates: the main service's models first, then the fallbacks",
      [m for _s, m in ai.candidates()] == ["model-a", "model-b", "g-model", "llama3.1:8b"], str([m for _s, m in ai.candidates()]))
check("the settings page is told about the fallbacks, never a key",
      [f["provider"] for f in ai.public()["fallbacks"]] == ["Groq", "Ollama (on this machine)"] and "groq-key" not in json.dumps(ai.public()))

# ---- a busy plan is passed over at once
reset(**{"generativelanguage": [BUSY], "groq.com": [OK_OPENAI]})
out, model, spent = brain.ask_ai("pick")
check("a rate-limited service hands over to the next one without waiting",
      (model, spent, slept) == ("g-model", 15, []) and hits("generativelanguage") == 2 and hits("groq.com") == 1, str((model, spent, slept)))

reset(**{"generativelanguage": [BUSY], "groq.com": [BUSY], "11434": [BUSY]})
try:
    brain.ask_ai("pick")
    check("when every service is busy it waits a little, goes round again, and then gives up", False, "no error")
except RuntimeError as e:
    check("when every service is busy it waits a little, goes round again, and then gives up",
          slept == [4, 8, 12] and "did not answer" in str(e) and hits("groq.com") == 3, str((slept, e)))

# ---- a service that refuses is not asked again
reset(**{"generativelanguage": [BAD_KEY], "groq.com": [BUSY, OK_OPENAI]})
out, model, _s = brain.ask_ai("pick")
check("a refused key is dropped for this question; the busy one is asked again after a pause",
      model == "g-model" and hits("generativelanguage") == 2 and hits("groq.com") == 2 and slept == [4], str((model, slept, hits("generativelanguage"))))

reset(**{"generativelanguage": [BAD_KEY], "groq.com": [GARBLED, OK_OPENAI]})
out, model, _s = brain.ask_ai("pick")
check("an answer that is not JSON gets one more try at once, with no wait", model == "g-model" and hits("groq.com") == 2 and slept == [])

# ---- the usage page counts the call once, whoever served it
u1, _ = auth._create("free-one@example.com", "One", password_hash="x")
with ctx.as_user(u1.id):
    reset(**{"generativelanguage": [BUSY], "groq.com": [OK_OPENAI]})
    brain.ask_ai("pick", purpose="Test")
    s = usage.summary({})
    check("a call served by a fallback is recorded once, with its tokens", s["calls_total"] == 1 and s["tokens_total"] == 15, str(s["calls_total"]))

# ---- Ollama: its shape, its reading size, its age
reset(**{"11434": [OK_OLLAMA]})
out, sent, wrote = ai.call("llama3.1:8b", "hello", brain.SCHEMA, ai.fallbacks()[1][0])
check("ollama: answer and tokens read from its own fields", out == [CLIP] and (sent, wrote) == (40, 8))
reset(**{"11434": [Reply(400, {"error": "invalid format"}), Reply(400, {"error": "invalid format"}), OK_OLLAMA]})
out, _s, _w = ai.call("llama3.1:8b", "hello", brain.SCHEMA, ai.fallbacks()[1][0])
formats = [b.get("format", "none") for _u, b, _h in seen]
check("ollama: an old version that refuses the shape is asked with plain JSON, then with nothing",
      out == [CLIP] and isinstance(formats[0], dict) and formats[1:] == ["json", "none"], str(formats))
reset(**{"11434": [OK_OLLAMA]})
try:
    ai.call("llama3.1:8b", "x" * 50000, brain.SCHEMA, ai.fallbacks()[1][0])
    check("ollama: a long request raises the reading size instead of being cut off", seen[0][1]["options"]["num_ctx"] == 32768, str(seen[0][1]["options"]))
except ai.AIError as e:
    check("ollama: a long request raises the reading size instead of being cut off", False, str(e)[:100])
try:
    ai.call("llama3.1:8b", "x" * 120000, brain.SCHEMA, ai.fallbacks()[1][0])
    check("ollama: a request too long for any reading size is refused, with what to change", False, "no error")
except ai.AIError as e:
    check("ollama: a request too long for any reading size is refused, with what to change",
          "PEAKCUT_AI_WINDOW_MIN" in str(e) and brain._how_it_failed(e) == "refused", str(e)[:100])
reset(**{"11434": [Reply(404, {"error": "model 'nope' not found"})]})
try:
    ai.call("nope", "hello", brain.SCHEMA, ai.fallbacks()[1][0])
except ai.AIError as e:
    check("ollama: a model that is not pulled is a refusal, not a retry", "HTTP 404" in str(e) and brain._how_it_failed(e) == "refused")


def fake_get(url, **_k):
    return Reply(200, {"models": [{"name": "llama3.1:8b"}, {"name": "qwen2.5:7b"}]}) if url.endswith("/api/tags") else Reply(404, {})


ai.httpx.get = fake_get
check("ollama: the models pulled onto this machine are listed", ai.list_models("ollama") == ["llama3.1:8b", "qwen2.5:7b"])

# ---- a window of transcript can be made smaller for a small model
words = [{"w": f"w{i}", "s": i * 0.5, "e": i * 0.5 + 0.4} for i in range(2400)]       # 20 minutes of talk
reset(**{"generativelanguage": [OK_GEMINI]})
brain.find_clips(words, np.zeros(1200), 1200.0, title="T", uploader="U")
big = hits("generativelanguage")
config.AI_WINDOW_MIN = 5
reset(**{"generativelanguage": [OK_GEMINI]})
brain.find_clips(words, np.zeros(1200), 1200.0, title="T", uploader="U")
small = hits("generativelanguage")
config.AI_WINDOW_MIN = 0
check("PEAKCUT_AI_WINDOW_MIN: smaller windows mean more, smaller requests", small > big >= 2, str((small, big)))

# ---- only fallbacks set up
saved = (config.AI_MODELS, os.environ["PEAKCUT_AI_KEY"])
config.AI_MODELS, os.environ["PEAKCUT_AI_KEY"] = [], ""
config._kept.clear()
check("a fallback alone is enough to be ready", ai.ready() and [m for _s, m in ai.candidates()] == ["g-model", "llama3.1:8b"])
try:
    ai.test()
    check("the dashboard test needs the main service to be set up", False, "no error")
except ValueError:
    check("the dashboard test needs the main service to be set up", True)

# ---- no AI at all: clips are still written up from what was said
config.AI_FALLBACKS = []
os.environ["PEAKCUT_AI_KEY_GROQ"] = ""
config._kept.clear()
check("with nothing set up there is no AI", not ai.ready() and ai.candidates() == [])
check("hashtags come from the video's own title", brain._title_tags("GTA 6 Launch Day Gameplay LIVE") == ["gta6", "launch", "day", "gameplay", "shorts"],
      str(brain._title_tags("GTA 6 Launch Day Gameplay LIVE")))
talk = ["so we are just driving around the city today", "and the radio is playing some music in the background", "i am looking for a place to park",
        "there is a lot of traffic on this road", "No way that just happened!", "did you see that?", "that car just flew right over me",
        "okay anyway let us keep going down the street", "i think the mission is on the other side", "we should probably hurry up now"]
spoken, t = [], 0.0
for s_ in talk:
    for w_ in s_.split():
        spoken.append({"w": w_, "s": round(t, 2), "e": round(t + 0.4, 2)})
        t += 0.45
    t += 0.9
db_ = np.full(int(t) + 2, -40.0)
at = int(next(w["s"] for w in spoken if w["w"] == "No"))
db_[at:at + 4] = -5.0                                              # shouting right there
clips, info = brain.find_clips(spoken, db_, float(len(db_)), title="GTA 6 Launch Day Gameplay", uploader="U", max_clips=1, min_len=10, max_len=30)
c = clips[0] if clips else {}
check("no AI: the loud moment is still picked", len(clips) == 1 and info["model"] is None and "loudness" in info["note"], str((clips, info)))
check("no AI: the hook and title come from the loudest sentence", c.get("hook", "").startswith("NO WAY") and c.get("title", "").startswith("No way that just happened"), str(c))
check("no AI: tags come from the video's title", "gta6" in c.get("hashtags", []) and c.get("hashtags", [""])[-1] == "shorts", str(c.get("hashtags")))
quiet, _i = brain.find_clips([{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4} for i, w in enumerate(("hello there everybody welcome to the stream " * 6).split())],
                             np.full(40, -40.0), 40.0, title="", uploader="", max_clips=1, min_len=10, max_len=30)
check("no AI: nothing eventful said gives the plain hook, never an empty one", quiet and quiet[0]["hook"] == "WAIT FOR IT", str(quiet))

# ---- the health check
config.AI_FALLBACKS = ["groq:g-model", "ollama:llama3.1:8b"]
os.environ["PEAKCUT_AI_KEY_GROQ"] = "groq-key-123456"
config.AI_MODELS = ["model-a"]
os.environ["PEAKCUT_AI_KEY"] = "test-key-123456"
config._kept.clear()
reset(**{"generativelanguage": [BAD_KEY], "groq.com": [OK_OPENAI], "11434": [httpx.ConnectError("refused")]})
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    code = ai_check.main()
text = buf.getvalue()
check("ai_check: says what worked and what did not, with what to do", code == 0 and "OK    Groq / g-model" in text and "key was refused" in text
      and "Ollama is not running" in text and "1 of 3 worked" in text, text)
config.AI_MODELS, config.AI_FALLBACKS = [], []
os.environ["PEAKCUT_AI_KEY"] = ""
config._kept.clear()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    code = ai_check.main()
check("ai_check: with nothing set up it says how to start and that PeakCut still works", code == 1 and "still works" in buf.getvalue())

print("ALL PASSED" if not fails else f"{len(fails)} failed")
import shutil  # noqa: E402
db.engine.dispose()
shutil.rmtree(os.environ["PEAKCUT_DATA"], ignore_errors=True)
sys.exit(1 if fails else 0)
