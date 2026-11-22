# Working on ClipIt

A short map for contributors and AI coding assistants.

## Installing or updating ClipIt for someone

**Before installing, ask the person where to put it**, and suggest a short, permanent folder: `C:\clipit` on
Windows, `~/clipit` on a Mac or Linux. Do not just clone into the folder you happen to be running in: AI assistants
often run in a temporary, scratch or session workspace, which gets deleted, and whose path is long enough that
Windows cannot load the speech library (Windows can't open files whose full path is over 260 characters; the error
is "DLL load failed ... The filename or extension is too long"). Tell the person where you put it.

**When updating**, look at where ClipIt is first. If its folder path is long (roughly over 100 characters) or inside
a temporary or assistant workspace, ask the person whether to move it to `C:\clipit` (or `~/clipit`) as part of the
update. Moving is safe when done like this: clone the latest version into the new folder, copy over `.env`,
`storage.json` and the `data` folder if there is one (the videos and clips; `storage.json` may point to a data folder
elsewhere, which then stays where it is), install the requirements, start it from the new folder, check the clips
are there, and only then offer to delete the old folder. Never delete anything without asking.

## Run and test

- Run: `python -m studio.server` (settings from `.env`; see `.env.example`). Needs Python 3.10+ and `ffmpeg`.
- The speech model (about 480 MB) downloads by itself on first start; `python -m studio.fetch_model` gets it ahead of time.
- Tests: `python tests/run.py`. It starts a throwaway copy on a spare port with an empty data folder. Run it
  before and after any change to `studio/`. No keys needed.
- To try a risky change by hand without touching real data:
  `CLIPIT_DATA=<temp folder> CLIPIT_PORT=8766 python -m studio.server`.

## Where things are

| File | What it does |
|---|---|
| `studio/server.py` | Every web route, and the gate that runs before each request (who is asking, limits, headers) |
| `studio/config.py` | Every setting, read from environment variables |
| `studio/ai.py` | The only code that talks to an AI service, and the AI settings saved from the dashboard (`ai.json` in the data folder) |
| `studio/ai_check.py` | `python -m studio.ai_check`: asks each AI service that is set up one tiny question, then a stretch of Hindi and Hinglish, and says what worked |
| `studio/brain.py` | The prompts: finding clips, live judging, hooks and titles, caption fixes; passing a busy service over to the next fallback; the hook, title and tags used when there is no AI |
| `studio/usage.py` | The record of AI calls and tokens shown on the AI usage page |
| `studio/jobs.py` | The video pipeline and the fair queue |
| `studio/live.py` | Live recording and clipping |
| `studio/transcribe.py`, `studio/asr_worker.py` | Speech to text, here or on a second machine |
| `studio/whisper.py`, `studio/fetch_model.py` | Speech to text for Hindi and every language but English (Whisper through sherpa-onnx), and downloading the speech models |
| `studio/roman.py`, `studio/loanwords.py` | Hindi (and other scripts) in Roman letters, and the English words that Hindi speech spells in Devanagari |
| `studio/games.py` | Which game a stream or video is, from its title (Hindi titles too), and the game's tags |
| `studio/facecam.py`, `studio/quality.py` | Finding the facecam in a gaming stream; spotting ad breaks and frozen screens |
| `studio/render.py` | Cutting, layouts and captions (ffmpeg and Pillow) |
| `studio/media.py` | Downloading (yt-dlp), probing, audio |
| `studio/auth.py`, `studio/account.py`, `studio/admin.py` | Sign-in, deleting things, the admin dashboard |
| `studio/db.py` | Database tables (SQLAlchemy core; SQLite or PostgreSQL) |
| `web/index.html` | The whole signed-in app, one file, no build step |

## Rules worth knowing

- **Sign-in is off by default** (`config.ACCOUNTS`): every request then belongs to one built-in owner
  (`auth.local_user()`). With `CLIPIT_ACCOUNTS=1` it is a normal multi-user site. Both paths are tested.
- **Who is asking** always comes from the session (`ctx.uid()`), never from the request body. Background threads
  set it themselves with `ctx.as_user(...)`.
- **Anything that changes what a user sees must call `ctx.bump()`**. The page polls `/api/sync`, which answers
  from memory when that user's counter has not moved.
- **Text from videos is untrusted**: it goes into prompts through `brain._safe` and out through `brain._text`.
- **Anything written for a post is in Roman letters.** Hindi speech comes back in Devanagari, and the caption fonts
  cannot draw it, so what the AI writes (hooks, titles, tags) goes through `roman.to_roman` in `brain._tidy`, and
  caption words through `roman.words`. An English word said in Hindi (गेम) is spelled the English way from
  `studio/loanwords.py`: add words there, one line each, and `tests/test_india.py` checks the table has no clashes.
- **Adding an AI provider**: add a row to `PROVIDERS` in `studio/ai.py`. If it speaks the OpenAI chat format that
  is all; otherwise add one function `(spec, model, prompt, schema)` that returns
  `(parsed JSON, tokens in, tokens out)`, and list it in `call()`. Ollama is the example: it has its own function
  because it must be told how much to read.
- **Every AI call goes through `brain.ask_ai`**, which tries the main service's models and then each fallback
  (`CLIPIT_AI_FALLBACKS`). Do not call `ai.call` from anywhere else.
- **Clips are rendered in a short temporary folder** and moved into place (`render.render_clip`): ffmpeg's caption
  step cannot open paths longer than 260 characters on Windows.
- **Secrets** are read from the environment or from files named by `*_FILE` settings. Never write a key, a real
  address or a personal path into a tracked file.
- **Pages** are plain HTML, CSS and JavaScript. Keep the existing palette, no shadows, and hover states that
  change colour only.
- Comments and messages are written in plain language for people who do not program. Keep that tone.
