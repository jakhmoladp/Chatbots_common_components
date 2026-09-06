# Module 6 — Text-to-Voice

> **This file is the working spec for module 6.** To request a change, add it
> under [Change requests](#change-requests) at the bottom rather than describing
> it in chat.

## Purpose

Turn text into spoken audio, in the language the text is written in. It is the
last step of the pipeline and the only one whose failure is non-fatal — if
speech fails, the user still has the written reply.

## Contract

```python
from modules.text_to_speech import synthesize, synthesize_bytes

path  = synthesize("नमस्ते, आप कैसे हैं?", language="hi")             # → temp .mp3 path
path  = synthesize("நல்வரவு", language="ta", out_path="out/ta.mp3")   # → "out/ta.mp3"
audio = synthesize_bytes("নমস্কার", language="bn")                    # → bytes
```

**Input:** `text` (str), `language` (ISO 639-1 code), optional `slow=True` for
slower speech.

**Output:**
- `synthesize()` → the path to an MP3 file.
- `synthesize_bytes()` → raw MP3 bytes, which is what `app.py` uses so nothing
  touches disk.

**Errors:** raises `SynthesisError` on empty input, a missing `gTTS`
dependency, or a network/service failure.

### Readiness

```python
from modules.text_to_speech import is_available

ready, reason = is_available()   # (True, None) or (False, 'missing gtts -- pip install …')
```

Note the limit of this check: it confirms `gTTS` is installed, but it cannot
confirm the network is reachable without making a real request. **A `True` here
does not guarantee synthesis will succeed** — callers must still handle
`SynthesisError`. `app.py` does, by downgrading a TTS failure to a warning.
Every module exports this; `tests/test_contracts.py` enforces it.

> **`synthesize()` with no `out_path` creates a temp file the caller owns.**
> Nothing deletes it for you. Prefer `synthesize_bytes()` unless you need a file.

## Supported languages

`en` English · `bn` Bengali · `gu` Gujarati · `hi` Hindi · `kn` Kannada ·
`ml` Malayalam · `mr` Marathi · `ne` Nepali · `pa` Punjabi · `ta` Tamil ·
`te` Telugu · `ur` Urdu

Verified against `gtts.lang.tts_langs()`. gTTS itself supports many more
languages; this list is the one kept in sync with the translation modules.

### The Odia gap

**Odia (`or`) is translatable but not speakable.** IndicTrans2 handles it, so
module 5 produces Odia text, but Google's TTS endpoint has no Odia voice.

Rather than drop a scheduled Indian language over a missing voice, module 6
*declares* the gap in `TEXT_ONLY_LANGUAGES`:

```python
from modules.text_to_speech import can_speak, TEXT_ONLY_LANGUAGES

can_speak("or")          # False
TEXT_ONLY_LANGUAGES      # {'or': 'Odia'}
```

`app.py` calls `can_speak()` before attempting synthesis, shows a caption in the
sidebar when the selected reply language is text-only, and replies in Odia text
as normal.

Two contract tests hold this together: one asserts every reply language is
either speakable or declared text-only, so a future language cannot silently
lose its audio; the other asserts a declared gap is a language module 5 can
actually produce, so the list cannot go stale.

`synthesize()` raises `SynthesisError` naming the language if you call it for
Odia anyway — better than reading Odia text aloud in an English voice.

## Files

| File | Role |
|------|------|
| `synthesizer.py` | The implementation |
| `voices.py` | Supported languages, text-only gaps, and the gTTS locale map |
| `__init__.py` | Public surface |
| `__main__.py` | CLI |
| `requirements.txt` | `gTTS` |

## Run it standalone

```bash
pip install -r modules/text_to_speech/requirements.txt   # ~1 MB, instant

python -m modules.text_to_speech --lang hi "नमस्ते" -o hello_hi.mp3
python -m modules.text_to_speech --lang ta "வணக்கம்" -o hello_ta.mp3
python -m modules.text_to_speech --lang en --slow "Speak slowly please"
python -m modules.text_to_speech --list
```

With no `-o`, it prints the temp file path it wrote.

## Engine

**gTTS** — a thin client for Google Translate's text-to-speech endpoint.

The trade-off, stated plainly: the voices are good and the language coverage is
wide, but **it requires an internet connection** and it is an *unofficial*
endpoint. There is no SLA. It can rate-limit you, and it could change without
notice. That is why `app.py` treats a TTS failure as a warning rather than an
error — the pipeline is designed to survive this module going down.

If you need offline speech, `pyttsx3` (Windows SAPI) is the drop-in
alternative. It needs no internet but the voices are noticeably robotic, and
non-English voices depend on what the OS has installed.

## The locale map

`voices.py` holds `GTTS_LOCALES`, which exists because gTTS does not take pure
ISO 639-1 for every language:

| Our code | gTTS wants |
|----------|-----------|
| `zh` | `zh-CN` |
| `pt` | `pt-BR` |

Every Indian language currently supported takes its plain ISO 639-1 code, so the
map is dormant for them — it is kept because the next language added may not be.

Between this and the Odia gap, module 6's view of "supported languages" differs
from module 3's in two independent ways: some codes need rewriting, and some
codes have no voice at all. That is the concrete reason module 6 keeps its own
language table rather than importing module 3's. The lists are *nearly* the
same, and "nearly" is what makes shared constants dangerous.

## Configuration knobs

| Constant | Default | Effect |
|----------|---------|--------|
| `MAX_CHARS_PER_REQUEST` | `1500` | Longer text is split and the MP3 fragments concatenated |

Concatenating MP3 fragments works because MP3 is a stream of independent
frames — no container surgery is needed. You may hear a small seam at the
join.

## Adding a language

1. Check gTTS supports it:
   ```bash
   python -c "from gtts.lang import tts_langs; print(sorted(tts_langs()))"
   ```
2. **If it has a voice** — add it to `SUPPORTED_LANGUAGES` in `voices.py`, and
   add a `GTTS_LOCALES` entry if gTTS wants a regional code.
3. **If it has no voice** — add it to `TEXT_ONLY_LANGUAGES` instead. Do not
   drop the language; the pipeline handles text-only fine.
4. Update modules 3, 4 and 5 to match — see
   [MODULE_3](MODULE_3_LANGUAGE_DETECTION.md#adding-a-language).
5. Run `pytest tests/test_contracts.py`.

Indian languages gTTS currently has **no** voice for: Odia, Assamese, Sanskrit,
Sindhi, Konkani, Maithili, Dogri, Manipuri. Of these only Odia is reachable
today, because the others are blocked at detection anyway.

## Testing

No automated test — it would make a network call. Verify by hand:

```bash
python -m modules.text_to_speech --lang ta "வணக்கம், எப்படி இருக்கிறீர்கள்" -o samples/test_ta.mp3
```

Then play the file. For a check that does not need your ears, feed it to module
2 and see whether the transcript matches:

```bash
python -m modules.speech_to_text samples/test_ta.mp3
```

`tests/test_contracts.py` verifies every language module 5 can produce is either
speakable or declared text-only. That runs instantly and makes no network call.

## Known limitations

- **Needs internet.** No connection, no audio.
- **Unofficial endpoint** — can rate-limit or break without notice.
- **No Odia voice.** See [the Odia gap](#the-odia-gap).
- **No voice selection.** One voice per language; no gender, pitch or speed
  control beyond the `slow` flag.
- **Punctuation drives prosody.** Text without full stops is read as one long
  breathless run. Indic text punctuated with the danda `।` rather than `.` still
  works, but pausing is less natural.
- **Wrong language code, wrong accent.** Passing English text with `lang="ta"`
  produces English words read with Tamil phonetics. Always pass the code that
  matches the text — in the app this is the same code given to module 5.

## Change requests

<!-- Add instructions here. Example:

### CR-1: Add an offline fallback
If gTTS raises (no network), fall back to pyttsx3 automatically and mark the
result so the UI can note that the offline voice was used.

-->

_None yet._
