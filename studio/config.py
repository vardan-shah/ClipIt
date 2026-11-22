"""All settings come from environment variables (or a .env file next to the project), so the same code runs
on a laptop and on a server. Nothing here is specific to one machine."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def _accept_old_names():
    """Settings used to be called PEAKCUT_<NAME>, from before this was ClipIt. Those still work: when only the old
    name is set it is used as the new one. When both are set, the new name wins."""
    for k, v in list(os.environ.items()):
        if k.startswith("PEAKCUT_"):
            os.environ.setdefault("CLIPIT_" + k[len("PEAKCUT_"):], v)


_accept_old_names()
env = os.environ.get


_kept: dict = {}


def _keep(key, make, seconds=60):
    """Settings read from files (keys, the Google client) are looked at once a minute, not on every request."""
    import time
    got = _kept.get(key)
    if not got or time.time() - got[0] > seconds:
        got = _kept[key] = (time.time(), make())
    return got[1]


def _secret(var: str, file_var: str, pattern: str = r"\S{16,}") -> str:
    """A secret given directly (VAR) or as a path to a file holding it (VAR_FILE)."""
    return _keep(("secret", var, file_var), lambda: _read_secret(var, file_var, pattern))


def _read_secret(var: str, file_var: str, pattern: str) -> str:
    if env(var):
        return env(var).strip()
    path = env(file_var)
    if path and Path(path).exists():
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        m = re.search(pattern, text)
        return m.group(0) if m else text.strip().strip('"')
    return ""


# ---------------------------------------------------------------- where things live
# Everything ClipIt keeps is in one folder. Which one: CLIPIT_DATA in .env if it is set; otherwise the folder the
# owner chose in Settings, Storage (kept in storage.json); otherwise "data" inside ClipIt's own folder.
STORAGE_FILE = Path(env("CLIPIT_STORAGE_FILE") or ROOT / "storage.json")


def _move_folder(old: Path, new: Path) -> bool:
    """Move everything from the old folder into the new one. Done at start, before anything is open. True when
    nothing is left behind; anything that could not be moved stays where it was and is tried again next start."""
    import shutil
    if not old.is_dir() or old.resolve() == new.resolve():
        return True
    items = list(old.iterdir())
    if items:
        print(f"\n  Moving ClipIt's folder to {new} ({len(items)} things). This is done once and can take a while...", flush=True)
    done = True
    for item in items:
        target = new / item.name
        try:
            if target.exists() and item.is_dir():
                for sub in item.iterdir():           # the folder is already there (made empty, or half moved): fill it
                    if not (target / sub.name).exists():
                        shutil.move(str(sub), str(target / sub.name))
                if not any(item.iterdir()):
                    item.rmdir()
                else:
                    done = False
            elif not target.exists():
                shutil.move(str(item), str(target))
            else:
                done = False
        except OSError as e:
            print(f"  Could not move {item.name}: {e}", flush=True)
            done = False
    if done:
        try:
            old.rmdir()
        except OSError:
            pass
        print("  Moved.\n", flush=True)
    return done


def _data_folder():
    if env("CLIPIT_DATA"):
        return Path(env("CLIPIT_DATA")), "env"
    try:
        chosen = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        chosen = {}
    if not chosen.get("path"):
        return ROOT / "data", "default"
    new = Path(chosen["path"])
    try:
        new.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise SystemExit(f"\n  ClipIt's folder is set to {new}, and that can't be reached right now.\n"
                         f"  Connect that drive and start ClipIt again, or delete {STORAGE_FILE} to go back to the\n"
                         f"  folder inside ClipIt (your videos and clips stay where they are).\n")
    if chosen.get("move_from"):
        if _move_folder(Path(chosen["move_from"]), new):
            STORAGE_FILE.write_text(json.dumps({"path": str(new)}, indent=1), encoding="utf-8")
    return new, "chosen"


DATA_DIR, DATA_FROM = _data_folder()
USERS_DIR = DATA_DIR / "users"          # users/<user id>/{creators,jobs,accounts}
MODELS_DIR = Path(env("CLIPIT_MODELS") or DATA_DIR / "models")
TMP_DIR = DATA_DIR / "tmp"
FONTS_DIR = DATA_DIR / "fonts"          # caption fonts, copied from studio/fonts so every server renders the same
# YouTube already has a word-by-word transcript of most videos. With this on, that is what the AI reads to find the
# clips (seconds instead of transcribing hours), and our own model is run only on the clips themselves.
YT_TRANSCRIPT = env("CLIPIT_YT_TRANSCRIPT", "1") != "0"
# the compact model for processors; a machine with a graphics card sets CLIPIT_ASR_MODEL to the full-precision one
ASR_MODEL_NAME = env("CLIPIT_ASR_MODEL", "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8")
ASR_MODEL_DIR = MODELS_DIR / ASR_MODEL_NAME
# The language spoken in the videos. "auto" (the default) finds it out for each video: English is done by the model
# above, which is quick and very good; Hindi, Hinglish (Hindi with English words in it) and other languages are done
# by Whisper, which knows about a hundred of them. Set "en" or "hi" to skip the guessing.
LANGUAGE = env("CLIPIT_LANGUAGE", "auto").strip().lower() or "auto"
# Which Whisper model does the non-English work: "turbo" (the best for Hindi; a download of about 560 MB), "small"
# (quicker to run, but it makes more mistakes in Hindi, and its download is no smaller), "medium" or "large-v3".
WHISPER_MODEL = env("CLIPIT_WHISPER_MODEL", "turbo").strip().lower() or "turbo"
DATABASE_URL = env("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'clipit.db').as_posix()}"
# Commercials and "be right back" screens are stitched into streams. A clip taken from one is worthless, so those
# seconds can be found and left out. It is off by default: it reads the whole video once, which is not free, and
# a video that is meant to be still must not lose its clips. CLIPIT_SKIP_STATIC=1 turns it on.
# The threshold is the mean luma difference between frames: under it, nothing moved.
SKIP_STATIC = env("CLIPIT_SKIP_STATIC", "0") == "1"
STATIC_THRESHOLD = float(env("CLIPIT_STATIC_THRESHOLD", "0.4"))
STATIC_MIN_SECONDS = float(env("CLIPIT_STATIC_MIN_SECONDS", "6"))
# How long one AI answer may take on a live stream. It is short on purpose: while the AI thinks, the
# recording carries on, so a slow answer costs a check, not the stream.
LIVE_AI_TIMEOUT = float(env("CLIPIT_LIVE_AI_TIMEOUT", "45"))

for d in (USERS_DIR, MODELS_DIR, TMP_DIR, FONTS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def user_dir(uid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_]{6,40}", uid or ""):
        raise ValueError("bad user id")
    return USERS_DIR / uid


# ---------------------------------------------------------------- the site
HOST = env("CLIPIT_HOST", "127.0.0.1")
PORT = int(env("CLIPIT_PORT") or "8765")
PUBLIC_URL = (env("CLIPIT_PUBLIC_URL") or f"http://127.0.0.1:{PORT}").rstrip("/")   # e.g. https://clips.example.com
HTTPS = PUBLIC_URL.startswith("https://")
SESSION_DAYS = int(env("CLIPIT_SESSION_DAYS", "30"))
# Accounts are off by default: ClipIt opens straight into the dashboard, with no sign-in, which is what you want
# on your own computer. On a server that other people can reach, set CLIPIT_ACCOUNTS=1: everyone then signs up
# and signs in, and each person only sees their own videos.
ACCOUNTS = env("CLIPIT_ACCOUNTS", "0") == "1"
# The buttons along the top of the dashboard: the project's code, and a page to follow its maker (feedback goes there
# too). There is no follow page unless you set one (CLIPIT_FOLLOW_URL, for example your Instagram page); without it,
# feedback opens a new issue on the project's code page. Set either to an empty value to hide that button.
REPO_URL = env("CLIPIT_REPO_URL", "https://github.com/vardan-shah/ClipIt").strip()
FOLLOW_URL = env("CLIPIT_FOLLOW_URL", "").strip()

# ---------------------------------------------------------------- limits (per user, and for the whole server)
# Your own ClipIt has no limits unless you set them: 0 (the default) means "none" for every limit below. The
# machine still protects itself: new work waits while the processor, memory or disk are nearly full (load.py).
_NONE = 10 ** 7                      # what "no limit" becomes: far beyond anything real, and still a plain number


def _limit(name: str, default: str = "0"):
    v = float(env(name) or default)
    return _NONE if v <= 0 else v


MAX_UPLOAD_MB = int(_limit("CLIPIT_MAX_UPLOAD_MB"))              # the largest video file someone may upload
# A big file is sent in pieces of this size and joined here, because web servers and CDNs in front of the app
# refuse very large single requests (Cloudflare stops at 100 MB).
UPLOAD_PART_MB = max(5, int(env("CLIPIT_UPLOAD_PART_MB", "40")))
# The most videos that may ever run at once. How many actually run is decided by how busy the machine is (load.py).
JOB_WORKERS = int(env("CLIPIT_JOB_WORKERS") or max(2, os.cpu_count() or 4))
MAX_ACTIVE_JOBS_PER_USER = int(_limit("CLIPIT_MAX_JOBS_PER_USER", "5"))    # videos sent and worked on at once
MAX_LIVE_TOTAL = int(env("CLIPIT_MAX_LIVE") or max(4, 2 * (os.cpu_count() or 4)))   # ceiling; real load decides below it
MAX_LIVE_PER_USER = int(_limit("CLIPIT_MAX_LIVE_PER_USER"))     # streams one person records at once
MAX_VIDEO_HOURS = _limit("CLIPIT_MAX_VIDEO_HOURS")              # longest video (or chosen part of one) that is processed
MAX_LIVE_HOURS = _limit("CLIPIT_MAX_LIVE_HOURS")                # a recording stops by itself after this long
MAX_USER_GB = _limit("CLIPIT_MAX_USER_GB")                      # disk space one account may fill
MAX_CREATORS = int(_limit("CLIPIT_MAX_CREATORS"))               # creators one account may add
ALLOWED_SITES = tuple(s.strip().lower() for s in env(
    "CLIPIT_ALLOWED_SITES", "youtube.com,youtu.be,twitch.tv,kick.com").split(",") if s.strip())

# ---------------------------------------------------------------- AI (bring your own key: see studio/ai.py)
# These are the starting values. Whatever is saved from the dashboard (Settings, AI) is used instead.
AI_PROVIDER = env("CLIPIT_AI_PROVIDER", "gemini").strip().lower()            # gemini, openai, xai, groq, openrouter, anthropic, ollama, custom
AI_MODELS = [m.strip() for m in env("CLIPIT_AI_MODELS", "").split(",") if m.strip()]   # tried in this order
AI_BASE_URL = env("CLIPIT_AI_BASE_URL", "").rstrip("/")                      # only for "custom", or to override a provider's address


# Extra services to fall back on when the main one is out of free requests or down. Each is "service:model", separated
# by commas, tried in this order after the main service's own models. Each service's key is CLIPIT_AI_KEY_<SERVICE>
# (or CLIPIT_AI_KEY_<SERVICE>_FILE), for example CLIPIT_AI_KEY_GROQ. A custom service's address is
# CLIPIT_AI_BASE_URL_CUSTOM. This is how several free plans are used in turn, so no one of them has to be topped up.
AI_FALLBACKS = [m.strip() for m in env("CLIPIT_AI_FALLBACKS", "").split(",") if m.strip()]
# How many minutes of transcript the AI reads in one request. 0 = the default (15).
AI_WINDOW_MIN = float(env("CLIPIT_AI_WINDOW_MIN") or 0)
# A model run by Ollama reads only this many tokens at once, and quietly drops the rest if the request is longer
# (Ollama's own default is 4096). ClipIt sets it on every request, and raises it for one that would not fit.
OLLAMA_NUM_CTX = int(env("CLIPIT_OLLAMA_NUM_CTX") or 16384)
OLLAMA_MAX_CTX = int(env("CLIPIT_OLLAMA_MAX_CTX") or 32768)
# Some models (Qwen 3 and its newer versions, for one) write out pages of "thinking" before the answer. On a laptop
# that is minutes of waiting, and picking clips does not need it, so ClipIt tells the model not to think. Set this to
# 1 to let it think anyway.
OLLAMA_THINK = env("CLIPIT_OLLAMA_THINK", "0") == "1"


def ai_key() -> str:
    return _secret("CLIPIT_AI_KEY", "CLIPIT_AI_KEY_FILE", r"\S{8,}")


def ai_key_for(service: str) -> str:
    """The key of one fallback service (see AI_FALLBACKS)."""
    name = re.sub(r"\W", "_", service).upper()
    return _secret(f"CLIPIT_AI_KEY_{name}", f"CLIPIT_AI_KEY_{name}_FILE", r"\S{8,}")


def ai_base_for(service: str) -> str:
    name = re.sub(r"\W", "_", service).upper()
    return env(f"CLIPIT_AI_BASE_URL_{name}", "").strip().rstrip("/")


def ai_ready() -> bool:
    from . import ai
    return ai.ready()


# ---------------------------------------------------------------- account emails (see mailer.py)
SMTP_HOST = env("CLIPIT_SMTP_HOST", "")
SMTP_PORT = int(env("CLIPIT_SMTP_PORT", "587"))
SMTP_USER = env("CLIPIT_SMTP_USER", "")
MAIL_FROM = env("CLIPIT_MAIL_FROM", "")
CONTACT_EMAIL = env("CLIPIT_CONTACT_EMAIL", "")
LEGAL_NAME = env("CLIPIT_LEGAL_NAME", "")            # the business that runs ClipIt, for the legal pages
LEGAL_COUNTRY = env("CLIPIT_LEGAL_COUNTRY", "")      # whose law applies, for the terms
# Set to 1 on a public site with email set up: password sign-ups must then confirm their address before clipping.
VERIFY_EMAIL = env("CLIPIT_VERIFY_EMAIL", "0") == "1"


def smtp_password() -> str:
    return _secret("CLIPIT_SMTP_PASSWORD", "CLIPIT_SMTP_PASSWORD_FILE", r"\S{4,}")


# ---------------------------------------------------------------- Google (sign in with Google, and connecting YouTube)
def google_client() -> tuple:
    """(client id, client secret). Either GOOGLE_CLIENT_ID/SECRET, or GOOGLE_CLIENT_FILE = the JSON Google lets you download."""
    return _keep("google", _read_google_client)


def _read_google_client() -> tuple:
    if env("GOOGLE_CLIENT_ID") and env("GOOGLE_CLIENT_SECRET"):
        return env("GOOGLE_CLIENT_ID").strip(), env("GOOGLE_CLIENT_SECRET").strip()
    path = env("GOOGLE_CLIENT_FILE")
    if path and Path(path).exists():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            web = data.get("web") or data.get("installed") or {}
            return web.get("client_id", ""), web.get("client_secret", "")
        except ValueError:
            pass
    return "", ""


# ---------------------------------------------------------------- video
MAX_SOURCE_HEIGHT = 1080
OUT_W, OUT_H, OUT_FPS = 1080, 1920, 30
