"""Check the AI setup without opening the dashboard:   python -m studio.ai_check

Asks every service that is set up (the main one, then each fallback) one tiny question, and says what worked, how long
it took, and what to do about what did not. Nothing is saved and nothing is charged beyond that.

A service that answers the tiny question is then given one real question: a made-up stretch of a stream in Hindi and
Hinglish, asked the way ClipIt asks it. Some small models answer English well and fumble Hindi, and this is the way to
find that out before a whole stream is spent on it. Leave it out with:   python -m studio.ai_check --quick

(This is the one place besides brain.ask_ai that asks a service directly: it has to ask each one on its own, not the
first that answers.)"""
import sys
import time

import httpx

from . import ai, brain

# A made-up stretch of a GTA stream, said the way an Indian streamer says it: some lines in Devanagari, some in Roman
# letters. Each line is (starts, ends, loud, what was said). The one real moment is the police chase, the jump and the
# escape, between 13 and 31 seconds; the rest is the usual hello, wandering about, and "subscribe".
HINDI_SAMPLE = [
    (0.0, 6.0, False, "bhai sabko namaste, aaj GTA 6 mein pehli baar story mission kar raha hoon"),
    (6.5, 12.5, False, "pehle thoda city ghoom lete hain, dekho kitna mast graphics hai yaar"),
    (13.0, 18.0, False, "अरे यार ये क्या, पुलिस पीछे लग गई, अब क्या करूं"),
    (19.0, 24.0, True, "ruk ruk ruk ek number jump maara bhai, gaadi udd gayi"),
    (24.5, 30.5, True, "अरे पागल है क्या ये, मर गया मैं, बच गया यार, कमाल हो गया"),
    (32.0, 36.0, False, "chalo ab agla mission pe chalte hain"),
    (37.0, 42.0, False, "aur haan, channel ko subscribe zaroor karna"),
]
HINDI_MOMENT = (13.0, 31.0)
HINDI_WAIT = 240          # seconds: the first question can take a while, since the model has to be loaded first


def _hint(e, spec, model) -> str:
    msg = str(e)
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        if spec["provider"] == "ollama":
            return "Ollama is not running. Open the Ollama app (or run: ollama serve) and try again."
        return "Could not reach it. Check the internet connection and the address."
    if "HTTP 404" in msg and spec["provider"] == "ollama":
        return f"Ollama does not have that model yet. Run: ollama pull {model}"
    if "HTTP 401" in msg or "HTTP 403" in msg:
        return "The key was refused. Check it was copied whole, and that it is a key for this service."
    if "HTTP 429" in msg:
        return "Out of free requests for now, or too many at once. It works again once the limit resets."
    if "HTTP 404" in msg:
        return "This service does not know that model id. In the dashboard, Settings, AI, Find models lists the real ones."
    return msg[:300]


def _hindi_prompt() -> str:
    """The question the pipeline asks about a video, with the sample as the transcript."""
    lines = [{"s": s, "e": e, "text": text, "loud": loud} for s, e, loud, text in HINDI_SAMPLE]
    game = "GTA 6"
    return (brain.HEAD.format(title="GTA 6 pehli baar story mission | Hindi gameplay", uploader="Test stream", n=2)
            + brain._game_rules(game)
            + brain._rules(5, 25, brain._fmt(lines)))


def _try_hindi(spec, model) -> str:
    """One line on how the model did with Hindi and Hinglish: OK, WEAK (it answered, but missed the moment) or FAIL."""
    t0 = time.time()
    try:
        out, _sent, _wrote = ai.call(model, _hindi_prompt(), brain.SCHEMA, spec, timeout=HINDI_WAIT)
    except Exception as e:  # noqa: BLE001
        return f"Hindi and Hinglish: FAIL, {_hint(e, spec, model)}"
    took = time.time() - t0
    items = [c for c in out if isinstance(c, dict)] if isinstance(out, list) else []
    best, best_overlap = None, 0.0
    for c in items:
        s, e = brain._num(c.get("start")), brain._num(c.get("end"))
        overlap = min(e, HINDI_MOMENT[1]) - max(s, HINDI_MOMENT[0])
        if overlap > best_overlap:
            best, best_overlap = c, overlap
    if best is not None and best_overlap >= 5:
        hook = brain._tidy(best, 0, 0)["hook"]
        return (f"Hindi and Hinglish: OK, {took:.1f}s. It picked {brain._num(best.get('start')):.0f}s to "
                f"{brain._num(best.get('end')):.0f}s and wrote the hook {hook!r}.")
    if spec["provider"] == "ollama":
        others = [m for m in ("gemma3:12b", "llama3.1:8b") if m != model]
        more = (f"Hindi is hard for some small models, and another may do better, for example {' or '.join(others)}. "
                f"To try one: ollama pull {others[0]}, use it in your .env instead, and run this check again.")
    else:
        more = "Hindi is hard for some small models. Another model of this service, or a bigger one, may do better."
    return (f"Hindi and Hinglish: WEAK, {took:.1f}s. It answered, but did not pick the police chase and the jump "
            f"({HINDI_MOMENT[0]:.0f}s to {HINDI_MOMENT[1]:.0f}s). {more}")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--help" in argv or "-h" in argv:
        print("python -m studio.ai_check           asks each AI that is set up a tiny question, then a Hindi and Hinglish one")
        print("python -m studio.ai_check --quick   the tiny question only")
        return 0
    quick = "--quick" in argv
    cands = ai.candidates()
    if not cands:
        print("No AI is set up. Copy .env.free.example to .env and fill it in, or choose one in the dashboard (Settings, AI).")
        print("ClipIt still works without one: clips are then picked by loudness only.")
        return 1
    ok = 0
    for spec, model in cands:
        name = f"{ai.PROVIDERS[spec['provider']][0]} / {model}"
        t0 = time.time()
        try:
            out, sent, wrote = ai.call(model, ai.TEST_PROMPT, ai.TEST_SCHEMA, spec)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {name}: {_hint(e, spec, model)}")
            continue
        ok += 1
        print(f"OK    {name}: {time.time() - t0:.1f}s, {sent + wrote} tokens, answered {str(out)[:40]}")
        if not quick:
            print("      trying a stretch of Hindi and Hinglish (the first time can take a minute) ...", flush=True)
            print("      " + _try_hindi(spec, model))
    print(f"\n{ok} of {len(cands)} worked.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
