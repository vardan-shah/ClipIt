"""Talking to the AI service. You bring your own key, and choose the service and model in the dashboard
(Settings, AI) or in .env. What is saved from the dashboard is kept in ai.json in the data folder and wins.

    CLIPIT_AI_PROVIDER   gemini | openai | xai | groq | openrouter | anthropic | ollama | custom
    CLIPIT_AI_MODELS     one or more model ids, comma separated, tried in this order
    CLIPIT_AI_KEY        your key (or CLIPIT_AI_KEY_FILE, a file holding it)
    CLIPIT_AI_BASE_URL   only for "custom" (any service that speaks the OpenAI chat format), or to override
    CLIPIT_AI_FALLBACKS  more services to try, in order, when those are out of free requests or down:
                          "groq:llama-3.3-70b-versatile,ollama:llama3.1:8b" (keys: CLIPIT_AI_KEY_GROQ and so on)

Every service is asked for the same thing: JSON that follows a small schema. Gemini takes the schema directly, and so
does Ollama (through its own chat address, which also lets ClipIt say how much text the model may read at once).
The others are told the schema in the prompt and asked for a JSON object, which works with any chat model."""
import json
import os
import re
import threading

import httpx

from . import config

# name -> (label shown on the pages, address, how it is spoken to, where to get a key, an example model id)
PROVIDERS = {
    "gemini": ("Gemini", "https://generativelanguage.googleapis.com/v1beta/models", "gemini", "https://aistudio.google.com/apikey", "gemini-2.5-flash"),
    "openai": ("OpenAI", "https://api.openai.com/v1", "openai", "https://platform.openai.com/api-keys", "gpt-4o-mini"),
    "xai": ("Grok", "https://api.x.ai/v1", "openai", "https://console.x.ai", "grok-4"),
    "groq": ("Groq", "https://api.groq.com/openai/v1", "openai", "https://console.groq.com/keys", "llama-3.3-70b-versatile"),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "openai", "https://openrouter.ai/keys", "google/gemini-2.5-flash"),
    "anthropic": ("Claude", "https://api.anthropic.com/v1", "anthropic", "https://console.anthropic.com", ""),
    "ollama": ("Ollama (on this machine)", "http://127.0.0.1:11434", "ollama", "https://ollama.com", "llama3.1:8b"),
    "custom": ("Custom (OpenAI-compatible)", "", "openai", "", ""),
}
ALIASES = {"google": "gemini", "grok": "xai", "claude": "anthropic", "local": "ollama"}
NO_KEY = {"ollama", "custom"}       # a model running on your own machine needs no key

# ---------------------------------------------------------------- the settings in use
_lock = threading.Lock()
_saved = {"at": None, "data": {}}


def _file():
    return config.DATA_DIR / "ai.json"


def _from_dashboard() -> dict:
    """What was saved from the dashboard, read again only when the file changes."""
    f = _file()
    try:
        at = f.stat().st_mtime_ns
    except OSError:
        at = 0
    if _saved["at"] != at:
        try:
            data = json.loads(f.read_text(encoding="utf-8")) if at else {}
        except (OSError, ValueError):
            data = {}
        _saved.update(at=at, data=data if isinstance(data, dict) else {})
    return _saved["data"]


def current() -> dict:
    """Provider, models, address and key: what the dashboard saved, or else what .env says."""
    d = _from_dashboard()
    p = str(d.get("provider") or config.AI_PROVIDER or "").strip().lower()
    return {"provider": ALIASES.get(p, p),
            "models": list(d["models"]) if d.get("provider") else list(config.AI_MODELS),
            "base_url": (str(d.get("base_url") or "") if d.get("provider") else config.AI_BASE_URL).rstrip("/"),
            "key": str(d["key"]) if d.get("provider") and "key" in d else config.ai_key()}


def provider() -> str:
    return current()["provider"]


def models() -> list:
    return current()["models"]


def key() -> str:
    return current()["key"]


def label() -> str:
    return PROVIDERS.get(provider(), ("",))[0]


def base_url() -> str:
    c = current()
    return c["base_url"] or PROVIDERS.get(c["provider"], ("", ""))[1]


# ---------------------------------------------------------------- which services may be asked, and in what order
def _ollama_root(address: str) -> str:
    """Ollama's own address, without the /v1 that its OpenAI-style address carries (older settings have it)."""
    address = (address or "").rstrip("/")
    return address[:-3] if address.endswith("/v1") else address


def _spec(provider_id: str, address: str = "", key_value: str = "") -> dict:
    """Everything needed to reach one service: which it is, how it is spoken to, where it is, and its key."""
    p = PROVIDERS[provider_id]
    return {"provider": provider_id, "how": p[2], "base": (address or p[1]).rstrip("/"), "key": key_value or ""}


def _usable(spec: dict) -> bool:
    return bool(spec["base"] and (spec["key"] or spec["provider"] in NO_KEY))


def primary():
    """The main service, as the dashboard or .env sets it. None when it is not set up."""
    c = current()
    if c["provider"] not in PROVIDERS or not c["models"]:
        return None
    spec = _spec(c["provider"], c["base_url"], c["key"])
    return spec if _usable(spec) else None


def fallbacks() -> list:
    """The services named in CLIPIT_AI_FALLBACKS that are set up, as [(service, model)] in the order given.
    An entry is "service:model", split at the first colon, so model ids that hold colons ("llama3.1:8b") work."""
    out, c = [], current()
    for item in config.AI_FALLBACKS:
        name, _, model = item.partition(":")
        p = ALIASES.get(name.strip().lower(), name.strip().lower())
        model = model.strip()
        if p not in PROVIDERS or not model:
            continue
        same = c["provider"] == p        # the main service's own address and key are used if no other is given
        spec = _spec(p, config.ai_base_for(p) or (c["base_url"] if same else ""), config.ai_key_for(p) or (c["key"] if same else ""))
        if _usable(spec):
            out.append((spec, model))
    return out


def candidates() -> list:
    """Every (service, model) that may be asked, in the order they are tried: the main service's models first,
    then each fallback."""
    out = []
    spec = primary()
    if spec:
        out += [(spec, m) for m in current()["models"]]
    return out + [x for x in fallbacks() if x not in out]


def ready() -> bool:
    return bool(candidates())


def public() -> dict:
    """What the settings page may see. The key itself never leaves the server: only whether there is one, and
    its last four characters so the owner can tell which key it is."""
    c = current()
    return {"provider": c["provider"], "models": c["models"], "base_url": c["base_url"], "has_key": bool(c["key"]),
            "key_hint": c["key"][-4:] if len(c["key"]) >= 12 else "", "ready": ready(), "label": label(),
            "saved_here": bool(_from_dashboard().get("provider")),
            "fallbacks": [{"provider": PROVIDERS[s["provider"]][0], "model": m} for s, m in fallbacks()],
            "providers": [{"id": k, "label": v[0], "address": v[1], "needs_key": k not in NO_KEY, "key_url": v[3], "example": v[4]}
                          for k, v in PROVIDERS.items()]}


def save(provider_id: str, model_ids, address: str = "", new_key=None) -> dict:
    """Save the choice made in the dashboard. `new_key` None keeps the key that is already there (the page never
    has it to send back); an empty string removes it."""
    p = ALIASES.get(str(provider_id or "").strip().lower(), str(provider_id or "").strip().lower())
    if p not in PROVIDERS:
        raise ValueError("Choose one of the AI services in the list.")
    if isinstance(model_ids, str):
        model_ids = model_ids.split(",")
    ms = [str(m).strip()[:120] for m in (model_ids or []) if str(m).strip()][:5]
    if not ms:
        raise ValueError("Enter the model to use.")
    if any(not re.fullmatch(r"[\w.\-:/@]+", m) for m in ms):
        raise ValueError("A model id has letters, digits and . - : / only.")
    address = str(address or "").strip().rstrip("/")[:300]
    if address and not re.fullmatch(r"https?://[^\s]+", address):
        raise ValueError("The address has to start with http:// or https://")
    if p == "custom" and not address:
        raise ValueError("A custom service needs its address, for example http://127.0.0.1:1234/v1")
    old = current()
    k = old["key"] if new_key is None and old["provider"] == p else str(new_key or "").strip()[:400]
    if not k and p not in NO_KEY:
        raise ValueError("Paste the key for this service.")
    with _lock:
        f = _file()
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"provider": p, "models": ms, "base_url": address, "key": k}), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)        # the key is only for whoever runs the server
        except OSError:
            pass
        tmp.replace(f)
        _saved["at"] = None
    return public()


def list_models(provider_id=None, address=None, with_key=None) -> list:
    """The model ids a service offers, so the settings page can show a list to pick from."""
    c = current()
    p = ALIASES.get(str(provider_id or c["provider"]).lower(), str(provider_id or c["provider"]).lower())
    if p not in PROVIDERS:
        raise ValueError("Choose one of the AI services in the list.")
    k = str(with_key or "").strip() or (c["key"] if c["provider"] == p else "")
    base = str(address or "").strip().rstrip("/") or (c["base_url"] if c["provider"] == p else "") or PROVIDERS[p][1]
    if not base:
        raise ValueError("Enter the service's address first.")
    how = PROVIDERS[p][2]
    if how == "gemini":
        r = httpx.get(base, params={"pageSize": 200}, headers={"x-goog-api-key": k}, timeout=20)
    elif how == "anthropic":
        r = httpx.get(f"{base}/models", params={"limit": 200}, headers={"x-api-key": k, "anthropic-version": "2023-06-01"}, timeout=20)
    elif how == "ollama":      # the models pulled onto this machine
        r = httpx.get(f"{_ollama_root(base)}/api/tags", timeout=20)
    else:
        r = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {k}"} if k else {}, timeout=20)
    if r.status_code != 200:
        raise AIError(f"HTTP {r.status_code} {r.text[:200].replace(k or chr(0), '<key>')}")
    data = r.json()
    if how == "gemini":
        found = [m.get("name", "").split("/")[-1] for m in data.get("models", [])
                 if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    elif how == "ollama":
        found = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
    else:
        found = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
    return sorted({m for m in found if m})[:400]


TEST_PROMPT = 'Answer with a JSON array that holds the single string "ok".'
TEST_SCHEMA = {"type": "ARRAY", "items": {"type": "STRING"}}


def test() -> dict:
    """One tiny request with the main service, to prove the key, the address and the model all work."""
    spec = primary()
    if not spec:
        raise ValueError("Save a service, a model and a key first.")
    model = current()["models"][0]
    out, sent, wrote = call(model, TEST_PROMPT, TEST_SCHEMA, spec)
    return {"ok": True, "model": model, "tokens": sent + wrote, "answer": str(out)[:80]}


class AIError(RuntimeError):
    pass


problem = {"text": "", "at": 0.0}       # why the AI last failed, for the dashboard; cleared when it answers again


def explain(e, spec=None, model=None) -> str:
    """What went wrong with an AI call, in words the owner can act on. When it is known which service and model
    were asked (a fallback, say) they are named; otherwise it speaks of the main service."""
    text, low = str(e), str(e).lower()
    name = model or (models() or ["?"])[0]
    prov = spec["provider"] if spec and spec.get("provider") in PROVIDERS else provider()
    who = PROVIDERS[prov][0] if prov in PROVIDERS else label()
    if "404" in text or "not found" in low or "does not exist" in low or "unknown model" in low or "not_found" in low:
        if prov == "ollama":
            return f"Ollama doesn't have the model \"{name}\" yet. In Terminal, run: ollama pull {name}"
        return f"{who} doesn't know the model \"{name}\". Open Settings, AI, press Find models and pick one from the list."
    if "401" in text or "403" in text or "api key" in low or "api_key" in low or "unauthorized" in low or "permission" in low:
        return f"{who} refused the key. Paste a working key under Settings, AI."
    if "429" in text or "quota" in low or "rate limit" in low or "exhausted" in low:
        return f"{who} says the key has hit its limit or has no credit left. Check the account with {who}, or try again later."
    if "connect" in low or "timed out" in low or "timeout" in low or "getaddrinfo" in low or "refused" in low:
        return f"ClipIt couldn't reach {who}. Check the internet connection" + (" and that Ollama is running." if prov == "ollama" else ".")
    return ""


def explain_all(items) -> str:
    """The same for several services that were asked in turn: items are (error, spec, model). The first two
    different reasons, in the order the services were tried."""
    said = []
    for e, spec, model in items:
        why = explain(e, spec, model)
        if why and why not in said:
            said.append(why)
    return " ".join(said[:2])


def note_problems(items):
    import time
    why = explain_all(items)
    if why:
        problem.update(text=why, at=time.time())


def note_problem(e, spec=None, model=None):
    note_problems([(e, spec, model)])


def clear_problem():
    problem.update(text="", at=0.0)


def _fail(r, spec):
    text = r.text[:300].replace(spec["key"] or "\0", "<key>")
    raise AIError(f"HTTP {r.status_code} {text}")


# ---------------------------------------------------------------- the schema, said in words for chat models
def _json_schema(s):
    """Gemini's schema spelling (ARRAY, OBJECT...) as ordinary JSON Schema."""
    if isinstance(s, dict):
        return {k: (v.lower() if k == "type" and isinstance(v, str) else _json_schema(v)) for k, v in s.items()}
    if isinstance(s, list):
        return [_json_schema(x) for x in s]
    return s


def _wrapped(prompt, schema):
    return (prompt + "\n\nAnswer with JSON only, no other text and no code fences: one object with a single key "
            "\"items\", whose value follows this JSON Schema:\n" + json.dumps(_json_schema(schema)))


def _parse(text):
    """The JSON in an answer, even if the model wrapped it in a code fence or a sentence, or thought out loud first."""
    text = re.sub(r"(?is)<think>.*?</think>", "", text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        out = json.loads(text)
    except ValueError:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if not m:
            raise AIError("The AI did not answer with JSON.")
        out = json.loads(m.group(0))
    if isinstance(out, dict) and "items" in out:
        out = out["items"]
    return out


# ---------------------------------------------------------------- one call
def call(model: str, prompt: str, schema: dict, spec=None):
    """Ask one model. `spec` says which service (the main one when left out). Returns (the parsed JSON answer,
    tokens sent, tokens written back)."""
    if spec is None:
        c = current()
        spec = _spec(c["provider"], c["base_url"], c["key"])
    return {"gemini": _gemini, "openai": _openai, "anthropic": _anthropic, "ollama": _ollama}[spec["how"]](spec, model, prompt, schema)


def _gemini(spec, model, prompt, schema):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json", "responseSchema": schema}}
    r = httpx.post(f"{spec['base']}/{model}:generateContent", json=body, headers={"x-goog-api-key": spec["key"]}, timeout=120)
    if r.status_code != 200:
        _fail(r, spec)
    data = r.json()
    text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    u = data.get("usageMetadata", {})
    sent = int(u.get("promptTokenCount") or 0)
    return json.loads(text), sent, max(0, int(u.get("totalTokenCount") or 0) - sent)   # the answer, and any thinking billed with it


def _openai(spec, model, prompt, schema):
    headers = {"Authorization": f"Bearer {spec['key']}"} if spec["key"] else {}
    body = {"model": model, "messages": [{"role": "user", "content": _wrapped(prompt, schema)}]}
    # Most services accept these two extras; a few models refuse one of them, so they are dropped on a refusal.
    extras = [{"temperature": 0.4, "response_format": {"type": "json_object"}}, {"response_format": {"type": "json_object"}}, {}]
    r = None
    for extra in extras:
        r = httpx.post(f"{spec['base']}/chat/completions", json={**body, **extra}, headers=headers, timeout=180)
        if r.status_code not in (400, 422):
            break
    if r.status_code != 200:
        _fail(r, spec)
    data = r.json()
    u = data.get("usage") or {}
    return _parse(data["choices"][0]["message"].get("content")), int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)


def _anthropic(spec, model, prompt, schema):
    body = {"model": model, "max_tokens": 8192, "messages": [{"role": "user", "content": _wrapped(prompt, schema)}]}
    r = httpx.post(f"{spec['base']}/messages", json=body, timeout=180,
                   headers={"x-api-key": spec["key"], "anthropic-version": "2023-06-01"})
    if r.status_code != 200:
        _fail(r, spec)
    data = r.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    u = data.get("usage") or {}
    return _parse(text), int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)


def _ctx_for(text: str) -> int:
    """How many tokens Ollama should be told to read for this request. Ollama reads only that many and drops the
    rest without a word, which for a long transcript means losing the instructions. So: the set size, or the next
    size up (doubling) for a request that is longer. A token is counted as 2.8 characters, which is more than
    the real size, plus room for the answer."""
    need = int(len(text) / 2.8) + 1800
    ctx = config.OLLAMA_NUM_CTX
    while ctx < need and ctx < config.OLLAMA_MAX_CTX:
        ctx = min(ctx * 2, config.OLLAMA_MAX_CTX)
    if need > ctx:
        raise AIError(f"HTTP 413 That much text does not fit in the {ctx} tokens the model may read. Set "
                      "CLIPIT_AI_WINDOW_MIN to a smaller number (such as 6), or raise CLIPIT_OLLAMA_MAX_CTX.")
    return ctx


def _ollama(spec, model, prompt, schema):
    """A model run by Ollama, through its own chat address rather than its OpenAI-style one: only this one lets
    ClipIt say how much text the model may read (otherwise 4096 tokens) and hand over the JSON shape the answer
    must have, which makes small models far more dependable."""
    text = _wrapped(prompt, schema)
    shape = {"type": "object", "properties": {"items": _json_schema(schema)}, "required": ["items"]}
    options = {"temperature": 0.4, "num_ctx": _ctx_for(text)}
    headers = {"Authorization": f"Bearer {spec['key']}"} if spec["key"] else {}
    r = None
    for fmt in (shape, "json", None):       # an older Ollama refuses a shape: it is asked again with plain JSON, then with nothing
        body = {"model": model, "stream": False, "messages": [{"role": "user", "content": text}], "options": options}
        if fmt:
            body["format"] = fmt
        r = httpx.post(f"{_ollama_root(spec['base'])}/api/chat", json=body, headers=headers, timeout=900)
        if r.status_code not in (400, 422):
            break
    if r.status_code != 200:
        _fail(r, spec)
    data = r.json()
    return _parse((data.get("message") or {}).get("content")), int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)
