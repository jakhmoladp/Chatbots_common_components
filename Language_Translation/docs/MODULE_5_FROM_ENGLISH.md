# Module 5 — English → Language Selected by the User

> **This file is the working spec for module 5.** To request a change, add it
> under [Change requests](#change-requests) at the bottom rather than describing
> it in chat.

## Purpose

Translate the chatbot's English response into whichever Indian language the user
picked in the sidebar. This is the outbound half of the pivot.

**It is the mirror of module 4, not a mode of it.** IndicTrans2 ships a separate
checkpoint per direction; neither is the other run backwards.

## Contract

```python
from modules.translate_from_english import translate_from_english

reply = translate_from_english("Hello, how are you?", "ta")
# → "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?"
```

**Input:** `text` (English str) and `target_language` (ISO 639-1 code present in
`FLORES_CODES`).

**Output:** translated text as a plain `str`.

**Special cases:**
- Empty or whitespace-only input returns `""`.
- `target_language="en"` returns the text unchanged, so the caller never has to
  special-case an English-to-English round trip.

**Errors:**
- `UnsupportedLanguageError` (a `ValueError`) — no FLORES mapping for that code.
- `TranslationError` (a `RuntimeError`) — dependencies missing, model gated or
  unreachable, or inference failed.

### Readiness

```python
from modules.translate_from_english import is_available

ready, reason = is_available()
```

Everything heavy is imported lazily, so `import modules.translate_from_english`
succeeds on a machine with no torch — the failure would otherwise surface
mid-conversation. `is_available()` uses `importlib.util.find_spec`, which
matters here: importing `torch` costs seconds and hundreds of megabytes, and a
health check must not do that.

## Supported targets

`bn` Bengali · `gu` Gujarati · `hi` Hindi · `kn` Kannada · `ml` Malayalam ·
`mr` Marathi · `ne` Nepali · `or` Odia · `pa` Punjabi · `ta` Tamil ·
`te` Telugu · `ur` Urdu

Plus `en`, handled as a pass-through.

> **Odia has no voice.** Module 5 produces Odia text happily; module 6 cannot
> speak it. See [MODULE_6](MODULE_6_TEXT_TO_SPEECH.md#the-odia-gap).

## Prerequisites

Identical to module 4, and the same two blockers apply. See
[MODULE_4 § Prerequisites](MODULE_4_TO_ENGLISH.md#prerequisites) for the full
walkthrough — in short:

1. **Microsoft C++ Build Tools** on Windows, because `IndicTransToolkit` has no
   Windows wheel and compiles a Cython extension.
2. **A Hugging Face account**, because
   [`ai4bharat/indictrans2-en-indic-dist-200M`](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M)
   is gated. Accept the terms on *this* model page too — accepting module 4's
   does not cover it.

## Files

| File | Role |
|------|------|
| `translator.py` | The implementation |
| `models.py` | `MODEL_NAME` and the ISO 639-1 → FLORES-200 map |
| `__init__.py` | Public surface |
| `__main__.py` | CLI |
| `requirements.txt` | `transformers`, `torch`, `IndicTransToolkit`, … |

## Run it standalone

```bash
pip install -r modules/translate_from_english/requirements.txt

python -m modules.translate_from_english --to hi "Hello, how are you?"
python -m modules.translate_from_english --to ta "Good morning, my friend."
python -m modules.translate_from_english --list
```

## Engine

**IndicTrans2** from AI4Bharat, checkpoint
`ai4bharat/indictrans2-en-indic-dist-200M` (~900 MB distilled).

**One model covers every target language**, selected by a FLORES-200 language
tag rather than by loading a different checkpoint. Hence `@lru_cache(maxsize=1)`.

The same three requirements as module 4 apply: `trust_remote_code=True`,
FLORES-200 codes (`tam_Taml`, not `ta`), and `IndicProcessor` for pre- and
post-processing. Here `postprocess_batch` matters slightly more, because it also
fixes up the output script.

## Configuration knobs

| Constant | Default | Effect |
|----------|---------|--------|
| `MODEL_NAME` | `…-dist-200M` | Swap for `ai4bharat/indictrans2-en-indic-1B` for better quality |
| `MAX_CHARS_PER_CHUNK` | `400` | Text longer than this is split on sentence boundaries |
| `@lru_cache(maxsize=1)` on `_load` | `1` | One model serves all languages |

Running the full app loads modules 4 and 5 simultaneously — roughly 1.8 GB of
weights. On a machine with 8 GB, expect swapping if much else is open.

Note the sentence splitter here only handles `.` `!` `?`. The input is always
English, so the danda and Arabic question mark that module 4 handles cannot
appear. That asymmetry is intentional, not an oversight.

## Where the target language comes from

The user picks it in the sidebar. `app.py` stores it in
`st.session_state.target_language` and passes it to this module on every turn.

Changing it mid-conversation affects the *next* reply only; earlier turns stay
in the transcript as they were. The same code is also handed to module 6 so the
speech matches the text.

## Adding a language

1. Confirm IndicTrans2 supports it — it covers all 22 scheduled languages, so
   translation is rarely the blocker.
2. Add the FLORES-200 code to `FLORES_CODES` and the name to `LANGUAGE_NAMES`.
3. Update modules 3, 4 and 6 to match — see
   [MODULE_3](MODULE_3_LANGUAGE_DETECTION.md#adding-a-language). **Detection is
   usually the real constraint**, not this module.
4. If gTTS has no voice for it, add it to `TEXT_ONLY_LANGUAGES` in module 6
   rather than dropping the language.
5. Run `pytest tests/test_contracts.py`.

## Testing

Not covered by automated tests — the model is ~900 MB and gated. Verify by hand:

```bash
python -m modules.translate_from_english --to hi "I want a cup of tea."
python -m modules.translate_from_english --to ta "I want a cup of tea."
```

A useful sanity check is a round trip through module 4:

```bash
python -m modules.translate_from_english --to hi "Where is the train station?" \
  | python -m modules.translate_to_english --from hi
```

If what comes back is close to the original, both modules are healthy. Note the
two commands each load their own model — this is two independent processes, and
neither module imports the other.

## Known limitations

- **Two setup prerequisites**, above. Neither is optional.
- **Pivoting loses nuance.** Tamil → English → Hindi is worse than Tamil →
  Hindi directly. IndicTrans2 does publish an Indic-to-Indic checkpoint; this
  project does not use it, because the whole architecture assumes an English
  pivot so the chatbot only ever has to think in one language.
- **Gendered languages guess.** English "I am tired" has no gender; Hindi must
  choose between *थका* and *थकी*. The model picks, usually masculine.
- **Formality is not controllable.** Hindi *तुम* vs *आप*, Tamil's honorific
  levels — the model picks and you cannot steer it.
- **CPU inference is slow** — 1–3 seconds per sentence.

## Change requests

<!-- Add instructions here. Example:

### CR-1: Preserve markdown formatting
Bold, links and code spans currently get mangled. Strip them before
translation, translate, then reapply by position.

-->

_None yet._
