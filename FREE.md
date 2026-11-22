# Running ClipIt for free

ClipIt has no credits, plan or subscription of its own. The only thing that can cost money is the AI service you
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

3. Get ClipIt ready, once. `python3 --version` must say 3.10 or higher; if it does not, run
   `brew install python@3.12` first and use `python3.12` in place of `python3` for the `venv` line.

   ```bash
   brew install ffmpeg
   ```

   ```bash
   cd clipit
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

5. Start ClipIt and open http://127.0.0.1:8765:

   ```bash
   python -m studio.server
   ```

Next time, only this: `cd clipit`, then `source .venv/bin/activate`, then `python -m studio.server`.

**Memory and heat on a 16 GB Mac.** The model itself needs about 5 GB. On top of that it needs room to hold the
transcript it is reading: ClipIt asks Ollama for 16,384 tokens, which for this model is roughly 2 GB more (my
arithmetic from the model's size, not a measurement). For an unusually long request it asks for 32,768 (roughly
4 GB), never more. That is comfortable if you close other heavy apps while a video runs. `.env.free.example` also
sets `CLIPIT_JOB_WORKERS=1` so only one video runs at a time. A MacBook Air has no fan, so a long batch may slow
down as it warms up. Ollama frees the model's memory a few minutes after the last request.

**Another model.** `ollama pull <name>`, then put that name in `CLIPIT_AI_MODELS` (or choose it under Settings, AI,
**Find models**, which lists what you have pulled). Some models "think" for a while before they answer (Qwen 3 and
its newer versions do). Picking clips does not need that, and on a laptop it is minutes of waiting, so ClipIt asks
them not to; `CLIPIT_OLLAMA_THINK=1` lets them think anyway. As a rule of thumb, keep the model under about 10 GB on
a 16 GB Mac. `python -m studio.ai_check` shows the seconds one tiny question took, which is the quickest way to
compare two models for speed. Which one picks clips best has to be judged on your own videos. For Hindi and
Hinglish streams, read [the section below](#hindi-hinglish-and-english) first.

## B. Free cloud plans in a chain

The first service you set up is asked first. If it says it is out of free requests (or is overloaded), ClipIt moves
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
- Free plans often come with looser data terms than paid ones. ClipIt sends only the transcript text and a few
  numbers about loudness, never the video or the audio. Read each service's terms if that matters to you.

In `.env` (the example file has this ready to fill in):

```ini
CLIPIT_AI_PROVIDER=gemini
CLIPIT_AI_MODELS=<a model id Gemini lists today>
CLIPIT_AI_KEY=<your Gemini key>
CLIPIT_AI_FALLBACKS=groq:<a Groq model id>,openrouter:<a model id ending in :free>,ollama:llama3.1:8b
CLIPIT_AI_KEY_GROQ=<your Groq key>
CLIPIT_AI_KEY_OPENROUTER=<your OpenRouter key>
```

Each fallback is `service:model`. Only the first colon splits them, so `ollama:llama3.1:8b` means the service
`ollama` and the model `llama3.1:8b`. If a service refuses a request as too long, or its free plan allows few
tokens a minute, add `CLIPIT_AI_WINDOW_MIN=6` so each request carries less.

## C. No AI at all

Leave the AI settings out and ClipIt still works. Clips are picked by loudness. Each one gets a hook, a title and
hashtags built from the loudest, most eventful sentence said in it (shouting, a question, a reaction like "no way")
and from the video's own title. A video called "GTA 6 Launch Day Gameplay LIVE", for example, gets the tags #gta6
#launch #day #gameplay #shorts. It is instant and free, but it picks what is loud, not what is good.

## Hindi, Hinglish and English

Most Indian streamers talk in Hindi, in English, or in both inside one sentence (Hinglish). ClipIt is built to work
for all three. This is what it does at each step.

**Speech to text.** With `CLIPIT_LANGUAGE=auto` (the default) ClipIt works out which language each video is in: from
what YouTube says it is, or else by listening to a few spots of the audio. English goes to the fast English model.
Hindi and Hinglish go to Whisper, which writes Hindi in Devanagari letters. Whisper's Hindi model (about 560 MB)
downloads by itself the first time a Hindi video turns up; `python -m studio.fetch_model hindi` gets it ahead of
time. If you only ever clip Hindi, set `CLIPIT_LANGUAGE=hi` so it never has to guess. `CLIPIT_WHISPER_MODEL=small` is
quicker to run, but makes more mistakes in Hindi (its download is no smaller, about 640 MB).

**Captions, hooks, titles and hashtags come out in Roman letters.** "arre yaar ye kya hua", not अरे यार ये क्या हुआ.
The caption fonts cannot draw Devanagari, and Roman letters are how people in India type and search. English words
that Hindi speech writes in Devanagari come back spelled the English way (गेम is game, क्लिप is clip, कॉल ऑफ ड्यूटी
is Call of Duty, बीजीएमआई is BGMI), from a list of about 360 gaming and streaming words. Every other word is spelled
by rules, the way people type it in chats (नहीं is nahi, चाहिए is chahiye): readable, though not always how one
particular person would type it.

**The AI is told how to read it.** When the speech is Hindi or Hinglish, the AI gets a short guide in front of its
instructions. It says that "yaar", "arre", "ek number", "faad diya" and "pagal" are reactions (so a shouted "arre!"
marks a moment even when few words are said), what "nahi", "mat", "chal" and "ruk" mean, to write the hook and title
the way the streamer talks (Hindi words in Roman letters, mixed with English where they mix it), and to leave swear
words out of every post. An English stream does not get the guide.

**Games played in India.** BGMI, Free Fire, Call of Duty: Mobile, Roblox, Clash of Clans, Clash Royale, Brawl Stars,
Genshin Impact, eFootball and GTA: Vice City are known, next to GTA VI and the others in [GAMING.md](GAMING.md). A
title written in Hindi ("जीटीए 6 गेमप्ले हिंदी में", "फ्री फायर लाइव") finds its game too, and the posts get the
game's tags (#GTA6, #FreeFire).

**Saying "clip it" in Hindi.** On a live stream, "clip it" and "clip that" start a clip. So does क्लिप said in Hindi.
Trigger phrases you set up match whichever way they were typed: "clip kar" in Roman letters matches क्लिप कर said on
stream, and the other way round.

**With no AI.** Hindi speech and Hindi titles still work. The hook and title come from the most eventful sentence, in
Roman letters ("ARRE YAAR YE KYA HUA"). Hinglish reactions such as "arre", "oye", "ek number", "kya baat hai" and
"faad diya" count as eventful, and the tags come from the title with the little words left out (a Hindi title gives
#gta6 #gameplay #hindi #shorts).

**Which AI model for Hindi.** I could not find a trustworthy comparison of models on Hinglish gaming speech, so
ClipIt tests the one you choose. `python -m studio.ai_check` finishes with one real question for every AI that works:
a made-up stretch of a GTA stream with some lines in Devanagari and some in Roman letters, and one real moment in it
(a police chase, a jump, an escape), asked the way ClipIt asks about a video. It says:

| It says | What it means |
|---|---|
| `Hindi and Hinglish: OK` | The model picked that moment, and shows the hook it wrote |
| `Hindi and Hinglish: WEAK` | It answered, but missed the moment. Try another model |
| `Hindi and Hinglish: FAIL` | It could not answer. The line says why |

`python -m studio.ai_check --quick` asks only the tiny question. The first Hindi question can take a minute while
Ollama loads the model. Two to try on a 16 GB MacBook. The sizes and the language lists below were read from the
linked pages on 22 November 2026. They are what the makers say, not a measure of how well the model reads Hindi on
your videos: the check above is what shows that.

| Model | Download | Notes |
|---|---|---|
| `gemma3:12b` | 8.2 GB, says [Ollama](https://ollama.com/library/gemma3:12b) | Google says it has "out-of-the-box support for over 35 languages and pretrained support for over 140" ([announcement](https://blog.google/technology/developers/gemma-3/)); that page does not name Hindi. Should fit a 16 GB Mac with other heavy apps closed (not tried on a Mac here) |
| `llama3.1:8b` | 4.9 GB, says [Ollama](https://ollama.com/library/llama3.1:8b) | The default here. Meta lists eight languages and Hindi is one of them ([model card](https://huggingface.co/meta-llama/Llama-3.1-8B)). The lighter of the two |

Newer models appear every few weeks (Ollama's library already lists `qwen3.5`, and people online are comparing it with
Gemma 4). Neither was tried here. Pull any model you like and run the check: it tells you whether that one reads Hindi
better. If the Mac starts to swap (Activity Monitor's memory pressure turns red), add `CLIPIT_AI_WINDOW_MIN=6` so each
request carries less. Hindi letters take far more of a model's reading room than English ones, so ClipIt counts them
for more when it tells Ollama how much to read.

## When something is wrong

`python -m studio.ai_check` asks every service you set up one tiny question and says what happened:

| It says | What to do |
|---|---|
| Ollama is not running | Open the Ollama app, or run `ollama serve` |
| Ollama does not have that model yet | Run `ollama pull <the model>` |
| The key was refused | Copy it again, whole, and check it belongs to that service |
| Out of free requests for now | Wait for the limit to reset, or add another service to the chain |
| This service does not know that model id | Settings, AI, **Find models** lists the real ones |
| That much text does not fit | Set `CLIPIT_AI_WINDOW_MIN=6`, or raise `CLIPIT_OLLAMA_MAX_CTX` |
| Hindi and Hinglish: WEAK | The model answered the Hindi question but missed the moment. Try another one (see above) |
| Hindi and Hinglish: FAIL | It could not answer the Hindi question. The line says why |

## Settings this edition adds

| Setting | What it does |
|---|---|
| `CLIPIT_AI_FALLBACKS` | `service:model` pairs, separated by commas, asked in order when the main service is busy or refuses |
| `CLIPIT_AI_KEY_<SERVICE>` | The key for one fallback, such as `CLIPIT_AI_KEY_GROQ` (or `..._FILE` for a file holding it) |
| `CLIPIT_AI_BASE_URL_<SERVICE>` | A different address for one fallback, such as an Ollama on another machine |
| `CLIPIT_AI_WINDOW_MIN` | Minutes of transcript per request. Smaller means more, smaller requests |
| `CLIPIT_OLLAMA_NUM_CTX` | Tokens Ollama reads per request (default 16384) |
| `CLIPIT_OLLAMA_MAX_CTX` | The most ClipIt will raise that to for a long request (default 32768) |
| `CLIPIT_OLLAMA_THINK` | `1` lets a model that can think do so before it answers (default: it is asked not to, which is much quicker) |
| `CLIPIT_LANGUAGE` | `auto` (default) finds the language of each video; `en` or `hi` skips the guessing |
| `CLIPIT_WHISPER_MODEL` | Which Whisper model writes Hindi down: `turbo` (default, best), `small` (quicker, less accurate), `medium`, `large-v3` |

## What changed from the original

- `studio/ai.py`: Ollama is now asked through its own chat address, with the reading size set and the shape of the
  answer given. Ollama's [FAQ](https://docs.ollama.com/faq) says it reads only 4,096 tokens by default, and through
  the OpenAI-style address there is no way to raise that, so a long transcript would be cut without a word.
  Also new: the fallback chain, models that think are asked not to, and Hindi letters count for more reading room.
- `studio/brain.py`: a busy service is passed over at once for the next one, and with no AI the hook, title and tags
  come from what was said. For Hindi and Hinglish: the reading guide for the AI, and Hinglish reactions the no-AI
  picker knows.
- `studio/config.py`: the settings above.
- `studio/ai_check.py`: the `python -m studio.ai_check` command, with its Hindi and Hinglish question.
- `studio/whisper.py`, `studio/fetch_model.py`, `studio/transcribe.py`, `studio/live.py`: Hindi and Hinglish speech
  (the language is worked out for each video, and Whisper writes everything that is not English).
- `studio/roman.py` and `studio/loanwords.py`: Hindi in Roman letters, and English words said in Hindi.
- `studio/games.py`: the games played in India, and game titles written in Hindi.
- `tests/test_free.py`, `tests/test_ai.py`, `tests/test_hindi.py`, `tests/test_roman.py` and `tests/test_india.py`:
  checks for all of this, run by `python tests/run.py`.

Everything else (the video pipeline, captions, accounts and the dashboard) works as in the original, apart from what
the original's developer added since, which is merged in.

**About MoneyPrinterTurbo.** It makes new videos from a topic (a script, stock footage, a voice-over). ClipIt cuts
highlights out of videos that already exist. They do different jobs, and merging them would add a lot of code and
heavy dependencies for nothing a clipper needs. The one idea carried over is not depending on a single AI service,
which is the fallback chain above.

## What was tested, and what was not

**Tested by the test suite** (`python tests/run.py`: 749 checks in 25 groups, no keys and no network needed): all of
the above against a pretend network and pretend AI answers, including the Hindi and Hinglish groups
(`tests/test_roman.py`, `tests/test_hindi.py`, `tests/test_india.py`). I also broke the new code on purpose in
nineteen different ways, one at a time, and confirmed a test caught every one.

**Tried by hand with the real thing:** Whisper's Hindi model, on Hindi speech made by a speech synthesiser (not a
person). The speech library cuts Hindi off unless short pieces are padded out to Whisper's 30-second window, which
`studio/whisper.py` does; with that, about one letter in ten came out wrong. On an ordinary processor Hindi took
roughly as long as the speech lasts. Whisper gives no time for each word, so the words of a Hindi caption are spread
over the stretch where someone is talking, and a highlighted word can be a little early or late.

**Also checked:** every package ClipIt needs, and everything those need, has a ready-made install for a Mac with Apple
silicon on Python 3.12 (pip found all of them), so nothing has to be compiled.

**Not tested:** a real Ollama or any real AI model (so how well a model reads Hindi is unknown until you run
`python -m studio.ai_check`), a real cloud service, real Hinglish speech from a person, a whole Hindi video all the
way to a rendered clip, and any of it on a Mac. The machine this was built on had none of them. Your first real
video is the real test, and `python -m studio.ai_check` is the quickest first step.

## Using it responsibly

Clip only videos you made or have permission to use, and follow the rules of any clipping program you join and of
the sites you fetch from and post to.
