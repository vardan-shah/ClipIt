"""The product is called ClipIt. Settings used to be called PEAKCUT_<NAME> (from before it was ClipIt): those still work,
and the new name wins when both are set. The old product name must not creep back into the pages, the code or the
docs, for example by merging the original project again: only the licence, the credit in the README and the
old-settings fallback may mention it."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
fails = []
def check(n, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"   got {got!r}")); ok or fails.append(n)

# ---- old settings names keep working
def settings(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PEAKCUT_", "CLIPIT_"))}
    env.update(DATABASE_URL="", PYTHONPATH=str(ROOT), **extra)
    r = subprocess.run([sys.executable, "-c", "from studio import config; print(config.DATA_DIR); print(config.PORT)"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    return r.stdout.split("\n")[:2] if r.returncode == 0 else r.stderr[-300:]

old_data, new_data = tempfile.mkdtemp(prefix="pc-old-"), tempfile.mkdtemp(prefix="pc-new-")
check("an old PEAKCUT_ name still sets the folder and the port", settings(PEAKCUT_DATA=old_data, PEAKCUT_PORT="8123"), [old_data, "8123"])
check("a CLIPIT_ name sets them too", settings(CLIPIT_DATA=new_data, CLIPIT_PORT="8124"), [new_data, "8124"])
check("when both are set, the new name wins",
      settings(PEAKCUT_DATA=old_data, PEAKCUT_PORT="8123", CLIPIT_DATA=new_data, CLIPIT_PORT="8124"), [new_data, "8124"])
check("a new name left empty on purpose is not filled in from the old one",
      settings(CLIPIT_DATA=new_data, PEAKCUT_PORT="8123", CLIPIT_PORT=""), [new_data, "8765"])

# ---- the old product name appears only where it has to
SKIP_DIRS = {".git", "data", "venv", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".idea", ".vscode"}
ALLOWED = {"LICENSE", "README.md", "studio/config.py", "tests/test_naming.py"}
hits, theirs = [], []
for folder, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for name in names:
        p = Path(folder) / name
        rel = p.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue                       # pictures, videos, fonts
        if re.search(r"peak.?cut", text, re.I) or re.search(r"peak.?cut", rel, re.I):
            hits.append(rel)
        if rel != "README.md" and re.search(r"haziq", text, re.I):
            theirs.append(rel)
check("the old product name is nowhere outside the licence, the credit and the settings fallback", sorted(hits), [])
check("nothing sends people to the original developer's pages (only the README credit does)", sorted(x for x in theirs if x != "tests/test_naming.py"), [])

readme = (ROOT / "README.md").read_text(encoding="utf-8")
check("the README says ClipIt is based on PeakCut, and by whom", "PeakCut" in readme and "haziqahmedqasmi" in readme)
check("the README starts with the ClipIt name", readme.lstrip().startswith("# ClipIt"))
check("the licence still carries the original notice", "PeakCut contributors" in (ROOT / "LICENSE").read_text(encoding="utf-8"))
for page in ("landing", "index", "auth", "reset", "admin", "legal"):
    html = (ROOT / "web" / f"{page}.html").read_text(encoding="utf-8")
    check(f"{page}.html is titled ClipIt", re.search(r"<title>[^<]*ClipIt", html) is not None)

print("ALL PASSED" if not fails else f"{len(fails)} failed")
import shutil
for d in (old_data, new_data):
    shutil.rmtree(d, ignore_errors=True)
sys.exit(1 if fails else 0)
