# Developer Guide

## 1. Project purpose

`SwearingBot` is a Telegram bot that sends periodic AI-generated messages to chats in several modes:

- `swear`: short insulting/joking messages
- `pause`: periodic reminder messages
- `talk`: short conversational replies based on recent chat history
- `news`: short news-style posts based on detected conversation topic

The bot can also attach generated voice messages (Silero TTS) in `swear` mode.

## 2. Current state at a glance

- Main runtime file: `swear.py`
- CLI/package entrypoint (`main.py`) currently prints a placeholder message only
- No automated tests in this repository
- Python files compile successfully with:

```powershell
uv run python -m compileall main.py config.py swearing_gen.py sber_swearing_gen.py converstion_complete.py voice_gen.py tts_gen.py swear.py news_post_gen.py news_post_gen_v2.py
```

## 3. Repository map

- `swear.py`: Telegram bot, command handlers, scheduler, mode switching, conversation memory
- `config.py`: loads secrets from env file and exposes `Config`
- `swearing_gen.py`: OpenAI-based insult generator
- `converstion_complete.py`: OpenAI-based short conversation continuation (`Colocutor`)
- `news_post_gen.py`: first version of news post generation (OpenAI + NewsAPI)
- `news_post_gen_v2.py`: active news post generator (LangChain + OpenAI + NewsAPI)
- `tts_gen.py`: Silero TTS wrapper, transliteration helper, WAV generation
- `voice_gen.py`: ElevenLabs helper (currently not used by `swear.py`)
- `sber_swearing_gen.py`: GigaChat/Sber alternative generator (currently not used by `swear.py`)
- `models/v4_ru.pt`: local Silero model asset
- `requirements.in`, `requirements.txt`, `pyproject.toml`, `uv.lock`: dependency definitions/locks
- `run.cmd`: Windows runner (currently starts `main.py`, not the bot)

## 4. Runtime architecture

### 4.1 Core flow

1. Bot starts (`swear.py`), initializes:
- Telegram bot client
- TTS model and voice list
- generators for swear/talk/news modes

2. On `/start`, per-chat sender objects are created for all modes.

3. A scheduler thread runs `schedule.run_pending()` once per second.

4. Each active mode has a randomized next-send interval, implemented by `PeriodicMessageSender`.

5. Incoming user text is appended to per-chat memory (`chats_conversations`) with stack size `16`.

### 4.2 Modes

- `swear`: uses `SwearingGenerator.get_answer(prompt)` with per-chat prompt (`/person` sets target)
- `pause`: sends static reminder templates
- `talk`: uses `Colocutor.get_answer(last_messages)`
- `news`: uses `NewsPostGenerator_v2.get_answer(last_messages)`

### 4.3 Voice behavior

- Voice generation is tied to `swear` mode.
- On each swear message, voice is attached with roughly 30% probability.
- Voice text is transliterated and synthesized using Silero into in-memory WAV.

## 5. Configuration and secrets

`config.py` loads dotenv from:

- `Path.home() / ".env" / "gv.env"`
- Example on Windows: `C:\Users\<user>\.env\gv.env`

Required variables (depending on enabled features):

- `TELEGRAM_SWEAR_BOT_TOKEN`
- `OPENAI_API_KEY`
- `SILERO_LOCAL_PATH`
- `SWEAR_PROMPT` (optional fallback prompt)
- `NEWSAPI_API_KEY` (for `news` mode)
- `ELEVENLABS_API_KEY` (only if `voice_gen.py` is used)
- `GIGA_CHAT_USER_ID`, `GIGA_CHAT_SECRET`, `GIGA_CHAT_AUTH` (only for `sber_swearing_gen.py`)

Recommended `gv.env` starter:

```env
TELEGRAM_SWEAR_BOT_TOKEN=...
OPENAI_API_KEY=...
SILERO_LOCAL_PATH=C:/Projects/SwearingBot/models/v4_ru.pt
SWEAR_PROMPT=Make a short funny insult.
NEWSAPI_API_KEY=...
ELEVENLABS_API_KEY=...
GIGA_CHAT_USER_ID=...
GIGA_CHAT_SECRET=...
GIGA_CHAT_AUTH=...
```

## 6. Setup and run

### 6.1 Environment setup (uv)

```powershell
uv sync
```

### 6.2 Run bot (actual runtime)

```powershell
uv run python swear.py
```

### 6.3 Current mismatch to know

- `run.cmd` executes `main.py`, which currently only prints `"Hello from swearingbot!"`.
- For real bot behavior, run `swear.py` directly.

## 7. External integrations

- Telegram Bot API via `pyTelegramBotAPI` (`telebot`)
- OpenAI Chat Completions (models currently used: `gpt-4.1-nano`, `gpt-4.1-mini`, `gpt-4o`, `gpt-4o-mini`)
- NewsAPI (`newsapi.org`)
- Silero TTS model (`v4_ru.pt`)
- ElevenLabs (optional helper file)
- Sber GigaChat (optional helper file)

## 8. Development workflow

### 8.1 Safe checks

```powershell
uv run python -m compileall main.py config.py swearing_gen.py sber_swearing_gen.py converstion_complete.py voice_gen.py tts_gen.py swear.py news_post_gen.py news_post_gen_v2.py
```

### 8.2 Where to change behavior

- Bot command/mode logic: `swear.py`
- Swear prompt style/model: `swearing_gen.py`
- Conversation tone: `converstion_complete.py`
- News generation strategy: `news_post_gen_v2.py`
- Voice synthesis behavior: `tts_gen.py`
- Secrets loading path/strategy: `config.py`

### 8.3 Adding a new periodic mode

1. Add generator function in `swear.py`
2. Add mode sender inside `chat_senders[chat_id]` initialization
3. Add command name in `@bot.message_handler(commands=[...])`
4. Ensure markdown escaping if mode uses rich text
5. Re-run compile check

## 9. Known issues and technical debt

1. Entrypoint mismatch:
- `main.py` and `run.cmd` do not start the real bot runtime.

2. Dependency source overlap:
- `pyproject.toml`, `requirements.in`, and `requirements.txt` are not fully aligned (name casing and package set differ).

3. Startup fragility:
- If `SILERO_LOCAL_PATH` is missing, TTS initialization can fail during startup.

4. Global initialization on import:
- Bot clients and models are initialized at import time in `swear.py`, making testing and partial imports harder.

5. No tests:
- Core behavior (scheduling, command routing, markdown escaping, generation fallbacks) is untested.

6. Optional modules are not wired:
- `sber_swearing_gen.py` and `voice_gen.py` exist but are not integrated into active flow.

7. Logging and resilience:
- Retry logic exists in some places but is inconsistent across all external API calls.

## 10. Suggested cleanup roadmap

1. Make `swear.py` the explicit project entrypoint (`[project.scripts]`) and update `run.cmd`.
2. Consolidate dependencies to one source of truth (`pyproject.toml` + `uv.lock`).
3. Add a config validation step at startup (fail fast with clear error messages).
4. Introduce basic tests for:
- mode switching
- schedule behavior
- markdown escaping
- conversation memory trimming
5. Move side-effect initialization behind `main()` to improve import safety and testability.
