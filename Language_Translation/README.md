# Translation Chatbot — English and Indian languages

A chatbot you can talk to in one language and be answered in another. Speak or
type in Tamil, the bot thinks in English, and it replies in Hindi — out loud.

Scope is **English plus 12 Indian languages**. Translation uses
[IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) from AI4Bharat, which is
purpose-built for Indian languages rather than a general multilingual model.

> 🚧 **Project is mid-build.** Modules 1, 2, 3 and 6 are verified working;
> modules 4 and 5 are written but have never been run because their
> dependencies are not installed yet. Voice input (module 2) is verified
> reliable for **Hindi and Tamil only** — the other 10 languages transcribe
> into the wrong script. **Start with [HANDOFF.md](HANDOFF.md)** — it lists
> exactly what is done, what is unverified, and what to do next.

The point of this project is not the chatbot. It is the **six independent
modules** that make the translation round trip work, each one replaceable
without touching the other five.

---

## The pipeline

```
                                  ┌──────────────────────────┐
   🎤 voice ──▶ [2] Speech-to-text │  modules/speech_to_text  │
                                  └────────────┬─────────────┘
                                               │ text
   ⌨️  text ───────────────────────────────────┤
                                               ▼
                                  ┌──────────────────────────┐
                 [3] Detect       │modules/language_detection│──▶ 'Language not in list'
                                  └────────────┬─────────────┘
                                               │ e.g. 'fr'
                                               ▼
                                  ┌──────────────────────────┐
                 [4] To English   │modules/translate_to_english│
                                  └────────────┬─────────────┘
                                               │ English
                                               ▼
                                        ┌─────────────┐
                                        │   bot.py    │  ← the chatbot brain
                                        └──────┬──────┘     (a stub you replace)
                                               │ English
                                               ▼
                                  ┌────────────────────────────┐
                 [5] From English │modules/translate_from_english│
                                  └────────────┬───────────────┘
                                               │ user's chosen language
                                               ▼
                                  ┌──────────────────────────┐
                 [6] Text-to-voice│  modules/text_to_speech  │──▶ 🔊 audio
                                  └──────────────────────────┘

                 [1] Streamlit UI  app.py — orchestrates all of the above
```

---

## The six modules

| # | Module | Folder | Instructions | Engine |
|---|--------|--------|--------------|--------|
| 1 | Streamlit chatbot UI | `app.py` | [MODULE_1_STREAMLIT_UI.md](docs/MODULE_1_STREAMLIT_UI.md) | Streamlit |
| 2 | Speech-to-text | `modules/speech_to_text/` | [MODULE_2_SPEECH_TO_TEXT.md](docs/MODULE_2_SPEECH_TO_TEXT.md) | faster-whisper (local) |
| 3 | Language detection | `modules/language_detection/` | [MODULE_3_LANGUAGE_DETECTION.md](docs/MODULE_3_LANGUAGE_DETECTION.md) | Unicode script + langdetect |
| 4 | Indian language → English | `modules/translate_to_english/` | [MODULE_4_TO_ENGLISH.md](docs/MODULE_4_TO_ENGLISH.md) | IndicTrans2 (local) |
| 5 | English → chosen language | `modules/translate_from_english/` | [MODULE_5_FROM_ENGLISH.md](docs/MODULE_5_FROM_ENGLISH.md) | IndicTrans2 (local) |
| 6 | Text-to-voice | `modules/text_to_speech/` | [MODULE_6_TEXT_TO_SPEECH.md](docs/MODULE_6_TEXT_TO_SPEECH.md) | gTTS |

**Each markdown file above is the working spec for its module.** Going forward,
give instructions for a module by editing its markdown file, not by describing
changes in chat. The file states the contract, the current behaviour, and a
"Change requests" section at the bottom for pending work.

---

## Supported languages

| Code | Language | Detect | Translate | Speak |
|------|----------|:------:|:---------:|:-----:|
| `en` | English   | ✓ | ✓ | ✓ |
| `hi` | Hindi     | ✓ | ✓ | ✓ |
| `bn` | Bengali   | ✓ | ✓ | ✓ |
| `mr` | Marathi   | ✓ | ✓ | ✓ |
| `te` | Telugu    | ✓ | ✓ | ✓ |
| `ta` | Tamil     | ✓ | ✓ | ✓ |
| `gu` | Gujarati  | ✓ | ✓ | ✓ |
| `kn` | Kannada   | ✓ | ✓ | ✓ |
| `ml` | Malayalam | ✓ | ✓ | ✓ |
| `pa` | Punjabi   | ✓ | ✓ | ✓ |
| `ur` | Urdu      | ✓ | ✓ | ✓ |
| `ne` | Nepali    | ✓ | ✓ | ✓ |
| `or` | Odia      | ✓ | ✓ | **text-only** |

**Odia is text-only.** IndicTrans2 translates it fine, but Google's TTS endpoint
has no Odia voice. The chat replies in Odia text and captions that audio is
unavailable, rather than dropping the language. Module 6 declares the gap in
`TEXT_ONLY_LANGUAGES`, and a contract test stops any future language from
losing its voice silently.

Anything else returns the error code **`Language not in list`**, exactly as the
spec requires. To add a language, see the "Adding a language" section in each of
modules 3, 4, 5 and 6 — all four have to agree, and `tests/test_contracts.py`
fails if they don't.

Languages IndicTrans2 supports that this app does not yet: Assamese, Sanskrit,
Sindhi, Kashmiri, Maithili, Manipuri, Bodo, Dogri, Konkani, Santali. The blocker
is detection and speech, not translation — see
[MODULE_3](docs/MODULE_3_LANGUAGE_DETECTION.md).

---

## Setup

Python 3.10 or newer.

### Prerequisites for modules 4 and 5 — do these first

IndicTrans2 gives the best Indian-language quality available, and it asks for
two one-off setup steps in return. **Modules 1, 2, 3 and 6 need neither** and
work without them.

**1. Microsoft C++ Build Tools** (Windows only)

`IndicTransToolkit` publishes no Windows wheel, so `pip` compiles a Cython
extension from source and fails without a compiler. Install from
<https://visualstudio.microsoft.com/visual-cpp-build-tools/> and select the
**"Desktop development with C++"** workload. Reopen your terminal afterwards.

**2. A Hugging Face account** — the IndicTrans2 models are gated

```bash
# Accept the terms on both model pages while signed in:
#   https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
#   https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M

pip install huggingface-hub
huggingface-cli login        # paste a token from hf.co/settings/tokens
```

### Install and run

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate     # macOS / Linux

# 2. Install everything
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens at http://localhost:8501.

> **First run is slow.** Modules 2, 4 and 5 download model weights on first use
> — roughly 140 MB for Whisper and ~900 MB for each IndicTrans2 direction. They
> are cached in `~/.cache/huggingface` and reused after that.

### Installing one module at a time

You do not need the full install to work on a single module. Each has its own
requirements file:

```bash
pip install -r modules/language_detection/requirements.txt   # ~1 MB, instant
pip install -r modules/text_to_speech/requirements.txt       # ~1 MB, instant
pip install -r modules/speech_to_text/requirements.txt       # ~50 MB
pip install -r modules/translate_to_english/requirements.txt # ~2 GB, needs both prerequisites
```

Start with module 3 — it installs in seconds and has the fastest feedback loop.

---

## Running a module on its own

Every module has a command-line entry point, so you can test it without the UI:

```bash
python -m modules.language_detection "வணக்கம், எப்படி இருக்கிறீர்கள்?"
python -m modules.language_detection --list

python -m modules.translate_to_english --from hi "नमस्ते, आप कैसे हैं?"
python -m modules.translate_from_english --to ta "Hello, how are you?"

python -m modules.speech_to_text samples/greeting.mp3 --verbose
python -m modules.text_to_speech --lang hi "नमस्ते" -o hello_hi.mp3
```

---

## What "independent" means here

This is the constraint the whole layout is built around, so it is worth being
precise about it:

1. **No module imports another module.** Not directly, not indirectly. Only
   `app.py` imports more than one. `tests/test_contracts.py` walks the AST of
   every module file and fails the build if this is violated.
2. **Each module owns its own copy of the language data it needs.** Module 3
   has `languages.py`, modules 4 and 5 each have a `models.py`, module 6 has
   `voices.py`. This is deliberate duplication — a shared `constants.py` would
   be a hidden coupling that makes "swap out module 4" a lie.
3. **Each module declares its own dependencies** in its own `requirements.txt`,
   and reports its own readiness via `is_available() -> (bool, reason)`. That
   is what lets `app.py` build a health list without knowing that module 4
   needs `torch` and module 6 needs `gTTS`.
4. **Each module can be run and tested alone** via `python -m modules.<name>`.
5. **A broken module degrades one feature, not the app.** `app.py` imports
   lazily and shows a per-module health list in the sidebar. With only
   `langdetect` and `gTTS` installed, the app still starts, modules 3 and 6
   still work, and the rest report exactly which `pip install` is missing.

The cost is that adding a language means editing four files. The test suite
turns that from a silent bug into a failing test, which is the trade worth
making.

---

## Replacing the chatbot brain

[`bot.py`](bot.py) is a stub with canned responses. Its contract is **English
in, English out** — keep that and you can swap in an LLM, a RAG pipeline, or a
rules engine without touching any of the six modules.

---

## Project layout

```
Language_Translation/
├── README.md                  ← you are here
├── app.py                     ← module 1: Streamlit UI + pipeline
├── bot.py                     ← the chatbot brain (stub)
├── requirements.txt           ← everything
├── docs/                      ← one instruction file per module
│   ├── MODULE_1_STREAMLIT_UI.md
│   ├── MODULE_2_SPEECH_TO_TEXT.md
│   ├── MODULE_3_LANGUAGE_DETECTION.md
│   ├── MODULE_4_TO_ENGLISH.md
│   ├── MODULE_5_FROM_ENGLISH.md
│   └── MODULE_6_TEXT_TO_SPEECH.md
├── modules/
│   ├── speech_to_text/        ← module 2
│   ├── language_detection/    ← module 3
│   ├── translate_to_english/  ← module 4
│   ├── translate_from_english/← module 5
│   └── text_to_speech/        ← module 6
├── samples/                   ← put test audio here
└── tests/
    ├── test_language_detection.py
    └── test_contracts.py      ← enforces module independence
```

---

## Tests

```bash
pytest tests/ -v
```

`test_language_detection.py` and `test_contracts.py` run in seconds with no
model downloads — `test_contracts.py` only reads source files and language maps.

---

## Known limitations

- **Voice input is only reliable for Hindi and Tamil.** Whisper (module 2)
  transliterates most other Indic languages into the wrong script instead of
  their own — verified on real transcription runs across three model sizes,
  see [MODULE_2](docs/MODULE_2_SPEECH_TO_TEXT.md#known-limitations) for the
  full evidence table. Typed input is unaffected and covers all 12 languages.
  The app warns in the UI when a transcript falls outside the verified set.
- **IndicTrans2 is sentence-level.** Long paragraphs are split and translated
  piecewise, so pronouns can drift across sentence boundaries.
- **Pivoting through English loses nuance.** Tamil → English → Hindi is worse
  than Tamil → Hindi directly. This is the price of needing only 2 models
  instead of one per pair — and IndicTrans2 has no direct Indic-to-Indic
  checkpoint in this project's setup.
- **Odia has no voice.** See the language table above.
- **gTTS needs internet** and is an unofficial endpoint; it can rate-limit.
- **Romanised Indic text is not detected.** Hindi typed in Latin script
  ("aap kaise ho") has no Devanagari for the script stage to find, and
  langdetect reads it as some Latin-script language. It returns
  `Language not in list`. This is the single biggest practical gap.
- **Assamese and Sanskrit are undetectable here.** They share scripts with
  Bengali and Hindi respectively, and langdetect has no profile for either.
