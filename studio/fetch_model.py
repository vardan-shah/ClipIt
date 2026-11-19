"""The speech-to-text models: downloaded once, by themselves, the first time they are needed.

Nothing has to be run by hand. (python -m studio.fetch_model still works, for getting them ahead of time.)
There are two kinds:

  * the English model (Parakeet), about 480 MB, which does English quickly and very well;
  * Whisper, which knows Hindi and about a hundred other languages: a small one (tiny, about 116 MB) that only
    listens to tell which language a video is in, and the one that writes Hindi down (turbo, about 560 MB).

Each is unpacked next to where it will live and moved into place only when it is whole, so a download that was
cut off can never leave half a model behind."""
import shutil
import sys
import tarfile
import threading
import urllib.request

from . import config

_RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"
URL = f"{_RELEASE}/{config.ASR_MODEL_NAME}.tar.bz2"
# The sizes of the Whisper downloads, in MB. Only these names are accepted, so a typo in a setting can never
# become part of an address or a folder name.
WHISPER_MB = {"tiny": 116, "base": 208, "small": 639, "medium": 1930, "turbo": 564, "large-v3": 1070}
_lock = threading.Lock()
state = {"doing": False, "percent": 0, "error": ""}


def ready() -> bool:
    """Is the whole English model there: the word list and all three parts?"""
    d = config.ASR_MODEL_DIR
    if not (d / "tokens.txt").is_file():
        return False
    return all(any(d.glob(f"{part}*.onnx")) for part in ("encoder", "decoder", "joiner"))


def whisper_dir(name: str):
    return config.MODELS_DIR / f"sherpa-onnx-whisper-{name}"


def whisper_files(name: str):
    """(encoder, decoder, word list) of a Whisper model as file names, or None if it is not all there. The compact
    files (int8) are used when the download has them, else the full ones."""
    if name not in WHISPER_MB:
        return None
    d = whisper_dir(name)
    for kind in ("int8", ""):
        end = f".{kind}.onnx" if kind else ".onnx"
        enc, dec, tok = d / f"{name}-encoder{end}", d / f"{name}-decoder{end}", d / f"{name}-tokens.txt"
        if enc.is_file() and dec.is_file() and tok.is_file():
            return str(enc), str(dec), str(tok)
    return None


def whisper_ready(name: str) -> bool:
    return whisper_files(name) is not None


def _progress(blocks, size, total):
    if total > 0:
        state["percent"] = min(99, int(blocks * size * 100 / total))


def _download(url: str, folder: str, final, what: str, mb: int) -> None:
    """Fetch one model's .tar.bz2, unpack it, and move the folder `folder` from it to `final`. The caller holds the
    lock and has checked it is really missing."""
    state.update(doing=True, percent=0, error="")
    print(f"\n  Downloading {what} (one time, about {mb} MB)...\n", flush=True)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp, part = config.MODELS_DIR / "speech-model.tar.bz2", config.MODELS_DIR / "speech-model.unpacking"
    try:
        urllib.request.urlretrieve(url, tmp, _progress)
        shutil.rmtree(part, ignore_errors=True)
        part.mkdir()
        with tarfile.open(tmp, "r:bz2") as t:
            for m in t.getmembers():  # only plain files and folders that stay inside the unpacking folder
                if (m.isfile() or m.isdir()) and not m.name.startswith(("/", "..")) and ".." not in m.name.split("/"):
                    t.extract(m, part)
        got = part / folder
        if not got.is_dir():
            raise OSError("the download did not contain the model")
        shutil.rmtree(final, ignore_errors=True)        # a half-finished one from before
        got.rename(final)
        print("  Speech model ready.\n", flush=True)
    except Exception as e:  # noqa: BLE001
        state["error"] = str(e)[-200:]
        raise RuntimeError(f"ClipIt couldn't download its speech model (about {mb} MB, needed once). Check the "
                           "internet connection and free disk space, then try again.") from e
    finally:
        state["doing"] = False
        tmp.unlink(missing_ok=True)
        shutil.rmtree(part, ignore_errors=True)


def ensure() -> None:
    """Make sure the English model is on this computer, downloading it if it is not. One download at a time:
    anything else that needs a model meanwhile waits for it here."""
    if ready():
        return
    with _lock:
        if ready():
            return
        _download(URL, config.ASR_MODEL_NAME, config.ASR_MODEL_DIR, "the speech model", 480)


def ensure_whisper(name: str) -> None:
    """The same for a Whisper model ("tiny", "small", "turbo"...)."""
    if name not in WHISPER_MB:
        raise ValueError(f"There is no Whisper model called {name!r}. Choose one of: {', '.join(WHISPER_MB)}.")
    if whisper_ready(name):
        return
    with _lock:
        if whisper_ready(name):
            return
        folder = f"sherpa-onnx-whisper-{name}"
        what = "the speech model that writes Hindi and other languages" if name != "tiny" else "the small model that tells which language is spoken"
        _download(f"{_RELEASE}/{folder}.tar.bz2", folder, whisper_dir(name), what, WHISPER_MB[name])


def startup_plan(remote_speech: bool = False) -> list:
    """What to have on this computer, for the language setting: [("speech", name)] and [("whisper", name)] entries.
    The English model always, unless the English speech is done on another machine (`remote_speech`). With the
    language on "auto", also the small Whisper model that tells languages apart (the big one that writes Hindi waits
    until a video in Hindi turns up). With Hindi (or another language) set by hand, the big one straight away."""
    from . import whisper
    plan = [] if remote_speech else [("speech", config.ASR_MODEL_NAME)]
    language = whisper.setting()
    if language == "auto":
        plan.append(("whisper", whisper.lid_name()))
    elif language != "en":
        plan.append(("whisper", config.WHISPER_MODEL))
    return plan


def fetch_plan(plan=None) -> None:
    for kind, name in (plan if plan is not None else startup_plan()):
        if kind == "speech":
            ensure()
        else:
            ensure_whisper(name)


def main():
    """python -m studio.fetch_model          what the language setting needs
       python -m studio.fetch_model hindi    ...and the big Hindi model too, so the first Hindi video starts at once"""
    from . import whisper
    plan = startup_plan()
    if "hindi" in sys.argv[1:] or "all" in sys.argv[1:]:
        for item in (("whisper", config.WHISPER_MODEL), ("whisper", whisper.lid_name())):
            if item not in plan:
                plan.append(item)
    for kind, name in plan:
        have = ready() if kind == "speech" else whisper_ready(name)
        print(f"{'English speech model' if kind == 'speech' else 'Whisper ' + name}: {'already here' if have else 'downloading'}")
    fetch_plan(plan)


if __name__ == "__main__":
    main()
