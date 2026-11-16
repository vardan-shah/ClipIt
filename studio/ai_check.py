"""Check the AI setup without opening the dashboard:   python -m studio.ai_check

Asks every service that is set up (the main one, then each fallback) one tiny question, and says what worked, how long
it took, and what to do about what did not. Nothing is saved and nothing is charged beyond that one tiny question."""
import sys
import time

import httpx

from . import ai


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


def main() -> int:
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
    print(f"\n{ok} of {len(cands)} worked.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
