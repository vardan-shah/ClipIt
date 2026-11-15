# Running PeakCut for free

PeakCut has no credits, plan or subscription of its own. The only thing that can cost money is the AI service you
choose to pick clips and write hooks and titles. Speech to text already runs on your own computer, and downloading,
cutting and captioning use free tools. This edition gives you three ways to make the AI part free too.

| | A. On your own computer | B. Free cloud plans in a chain | C. No AI |
|---|---|---|---|
| Cost | Nothing | Nothing, while you stay inside each plan's free limits | Nothing |
| Needs internet | Once, to download the model | Yes | Only to fetch videos |
| Quality of the picks | Depends on the model; small ones are weaker than large cloud models | Larger models, so usually better picks (not measured here) | Loudness only; no sense of what is funny or surprising |
| Limits | Your computer's speed and memory | Each service's free limits per minute and per day | None |
| What leaves your computer | Nothing | The transcript text, never the video or the audio | Nothing |

**Where to start:** A. It works today with nothing to sign up for. Run one video through it. If the clips it picks
feel weak, or it is too slow, add the cloud services from B in front of it.

## A. Everything on your own computer

You need the [Ollama](https://ollama.com/download) app, about 5 GB of disk for the model, and `ffmpeg`.
These steps are for a Mac, in Terminal.

1. Open the Ollama app so it is running (a llama icon appears in the menu bar).
2. Download the model, once (a 4.9 GB download according to Ollama's [library page](https://ollama.com/library/llama3.1)):

   ```bash
   ollama pull llama3.1:8b
   ```

3. Get PeakCut ready, once. `python3 --version` must say 3.10 or higher; if it does not, run
   `brew install python@3.12` first and use `python3.12` in place of `python3` for the `venv` line.

   ```bash
   brew install ffmpeg
   ```

   ```bash
   cd peakcut
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   ```bash
   python -m studio.fetch_model
   cp .env.free.example .env
   ```

4. Check the AI. This asks it one tiny question and prints how long it took:

   ```bash
   python -m studio.ai_check
   ```

   You want a line that starts with `OK    Ollama (on this machine) / llama3.1:8b`.

5. Start PeakCut and open http://127.0.0.1:8765:

   ```bash
   python -m studio.server
   ```

Next time, only this: `cd peakcut`, then `source .venv/bin/activate`, then `python -m studio.server`.

**Memory and heat on a 16 GB Mac.** The model itself needs about 5 GB. On top of that it needs room to hold the
transcript it is reading: PeakCut asks Ollama for 16,384 tokens, which for this model is roughly 2 GB more (my
arithmetic from the model's size, not a measurement). For an unusually long request it asks for 32,768 (roughly
4 GB), never more. That is comfortable if you close other heavy apps while a video runs. `.env.free.example` also
sets `PEAKCUT_JOB_WORKERS=1` so only one video runs at a time. A MacBook Air has no fan, so a long batch may slow
down as it warms up. Ollama frees the model's memory a few minutes after the last request.

**Another model.** `ollama pull <name>`, then put that name in `PEAKCUT_AI_MODELS` (or choose it under Settings, AI,
**Find models**, which lists what you have pulled). Prefer plain "instruct" models over ones that "think" before
answering: PeakCut ignores the thinking text, but you still wait while it is written. As a rule of thumb, keep the
model under about 10 GB on a 16 GB Mac. `python -m studio.ai_check` shows the seconds one tiny question took, which
is the quickest way to compare two models for speed. Which one picks clips best has to be judged on your own videos.

## B. Free cloud plans in a chain

The first service you set up is asked first. If it says it is out of free requests (or is overloaded), PeakCut moves
on to the next one at once instead of waiting. If every service is busy at the same moment it waits 4, then 8, then
12 seconds between rounds, and after that picks that stretch of the video by loudness instead of stopping. A service
whose key or model is refused is skipped for that question.

Put your own computer last in the chain, as in the example file, and the chain can never run dry.

| Service | Get a key | What I found on 15 November 2026 |
|---|---|---|
| Google Gemini | https://aistudio.google.com/apikey | Free use exists; the limits differ per model and are shown in AI Studio. I could not open Google's limits page from here, so check it yourself. |
| Groq | https://console.groq.com/keys | Free plan, with limits per organisation. [Its limits page](https://console.groq.com/docs/rate-limits) sends you to your own account for the exact numbers and did not state the free-plan ones. |
| OpenRouter | https://openrouter.ai/keys | Models whose id ends in `:free`. Per its [limits page](https://openrouter.ai/docs/api-reference/limits): 20 requests a minute, and 50 a day until you have bought 10 credits (1,000 after). Do not buy credits. |

Plans and limits change. If a service starts failing, `python -m studio.ai_check` says why.

**How much is used.** About 4 requests per hour of video to pick the moments, plus one short request per finished
clip to tidy the caption words. A one-hour video with 8 clips is therefore around 12 requests, so even OpenRouter's
50 a day covers several videos.

**Two cautions.**
- Never add a card or turn on billing on these accounts. That is what keeps them free.
- Free plans often come with looser data terms than paid ones. PeakCut sends only the transcript text and a few
  numbers about loudness, never the video or the audio. Read each service's terms if that matters to you.

In `.env` (the example file has this ready to fill in):

```ini
PEAKCUT_AI_PROVIDER=gemini
PEAKCUT_AI_MODELS=<a model id Gemini lists today>
PEAKCUT_AI_KEY=<your Gemini key>
PEAKCUT_AI_FALLBACKS=groq:<a Groq model id>,openrouter:<a model id ending in :free>,ollama:llama3.1:8b
PEAKCUT_AI_KEY_GROQ=<your Groq key>
PEAKCUT_AI_KEY_OPENROUTER=<your OpenRouter key>
```

Each fallback is `service:model`. Only the first colon splits them, so `ollama:llama3.1:8b` means the service
`ollama` and the model `llama3.1:8b`. If a service refuses a request as too long, or its free plan allows few
tokens a minute, add `PEAKCUT_AI_WINDOW_MIN=6` so each request carries less.

## C. No AI at all

Leave the AI settings out and PeakCut still works. Clips are picked by loudness. Each one gets a hook, a title and
hashtags built from the loudest, most eventful sentence said in it (shouting, a question, a reaction like "no way")
and from the video's own title. A video called "GTA 6 Launch Day Gameplay LIVE", for example, gets the tags #gta6
#launch #day #gameplay #shorts. It is instant and free, but it picks what is loud, not what is good.

## When something is wrong

`python -m studio.ai_check` asks every service you set up one tiny question and says what happened:

| It says | What to do |
|---|---|
| Ollama is not running | Open the Ollama app, or run `ollama serve` |
| Ollama does not have that model yet | Run `ollama pull <the model>` |
| The key was refused | Copy it again, whole, and check it belongs to that service |
| Out of free requests for now | Wait for the limit to reset, or add another service to the chain |
| This service does not know that model id | Settings, AI, **Find models** lists the real ones |
| That much text does not fit | Set `PEAKCUT_AI_WINDOW_MIN=6`, or raise `PEAKCUT_OLLAMA_MAX_CTX` |

## Settings this edition adds

| Setting | What it does |
|---|---|
| `PEAKCUT_AI_FALLBACKS` | `service:model` pairs, separated by commas, asked in order when the main service is busy or refuses |
| `PEAKCUT_AI_KEY_<SERVICE>` | The key for one fallback, such as `PEAKCUT_AI_KEY_GROQ` (or `..._FILE` for a file holding it) |
| `PEAKCUT_AI_BASE_URL_<SERVICE>` | A different address for one fallback, such as an Ollama on another machine |
| `PEAKCUT_AI_WINDOW_MIN` | Minutes of transcript per request. Smaller means more, smaller requests |
| `PEAKCUT_OLLAMA_NUM_CTX` | Tokens Ollama reads per request (default 16384) |
| `PEAKCUT_OLLAMA_MAX_CTX` | The most PeakCut will raise that to for a long request (default 32768) |

## What changed from the original

- `studio/ai.py`: Ollama is now asked through its own chat address, with the reading size set and the shape of the
  answer given. Ollama's [FAQ](https://docs.ollama.com/faq) says it reads only 4,096 tokens by default, and through
  the OpenAI-style address there is no way to raise that, so a long transcript would be cut without a word.
  Also new: the fallback chain, and thinking text is ignored.
- `studio/brain.py`: a busy service is passed over at once for the next one, and with no AI the hook, title and tags
  come from what was said.
- `studio/config.py`: the settings above.
- `studio/ai_check.py`: the `python -m studio.ai_check` command.
- `tests/test_free.py` and `tests/test_ai.py`: checks for all of this, run by `python tests/run.py`.

The video pipeline, captions, live clipping, accounts and the dashboard are untouched.

**About MoneyPrinterTurbo.** It makes new videos from a topic (a script, stock footage, a voice-over). PeakCut cuts
highlights out of videos that already exist. They do different jobs, and merging them would add a lot of code and
heavy dependencies for nothing a clipper needs. The one idea carried over is not depending on a single AI service,
which is the fallback chain above.

## What was tested, and what was not

Tested: the whole test suite, including 26 new checks, against a pretend network. I also broke the new code five
different ways on purpose and confirmed the tests caught every one.

Also checked: every package PeakCut needs, and everything those need, has a ready-made install for a Mac with Apple
silicon on Python 3.12 (pip found all of them), so nothing has to be compiled.

Not tested: a real Ollama or any real model, a real cloud service, the real speech model, a whole video all the
way to a rendered clip, and any of it on a Mac. The machine this was built on had none of them. Your first real
video is the real test, and `python -m studio.ai_check` is the quickest first step.

## Using it responsibly

Clip only videos you made or have permission to use, and follow the rules of any clipping program you join and of
the sites you fetch from and post to.
