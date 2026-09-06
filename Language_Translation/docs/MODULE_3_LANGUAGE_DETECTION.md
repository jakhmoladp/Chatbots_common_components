# Module 3 — Language Detection

> **This file is the working spec for module 3.** To request a change, add it
> under [Change requests](#change-requests) at the bottom rather than describing
> it in chat.

## Purpose

Given text in any language, return a language code **from the supported list**,
or the error code `Language not in list`.

This module is the single authority on which languages the app accepts. Modules
2, 4, 5 and 6 all have opinions about languages; this one has the ruling.

## Contract

```python
from modules.language_detection import detect_language, ERROR_NOT_IN_LIST

result = detect_language("Bonjour, comment allez-vous ?")

result.ok            # bool
result.code          # 'ta'      — only when ok
result.name          # 'Tamil'   — only when ok
result.confidence    # 0.0 to 1.0
result.error         # 'Language not in list' | 'Empty input' | None
result.detected_raw  # what the engine actually guessed, even when rejected
result.method        # 'script' | 'script+langdetect' | 'langdetect'
```

**Input:** any string.

**Output:** a `DetectionResult`. `str(result)` gives either
`"fr (French, confidence 0.99)"` or the error code.

**Errors:** never raises for an unsupported language — that is a *result*, not
an exception. It only raises `RuntimeError` if `langdetect` is not installed.

### Readiness

```python
from modules.language_detection import is_available

ready, reason = is_available()   # (True, None) or (False, 'missing langdetect -- pip install …')
```

`langdetect` is imported lazily, so `import modules.language_detection`
succeeds even when the package is absent. `is_available()` is how a caller
finds out *before* the first message rather than during it. It uses
`importlib.util.find_spec`, so the check is cheap. Every module exports this;
`tests/test_contracts.py` enforces it.

### The three ways `ok` is False

| `error` | Cause |
|---------|-------|
| `Empty input` | The string was empty or whitespace |
| `Language not in list` | Recognised, but not in `SUPPORTED_LANGUAGES` |
| `Language not in list` | Recognised, but below the confidence floor |

The last two share an error code on purpose — the spec asks for exactly one
error string. Use `result.detected_raw` and `result.confidence` to tell them
apart when debugging.

## Supported languages

Defined in `languages.py`. English plus 12 Indian languages:

`en` English · `bn` Bengali · `gu` Gujarati · `hi` Hindi · `kn` Kannada ·
`ml` Malayalam · `mr` Marathi · `ne` Nepali · `or` Odia · `pa` Punjabi ·
`ta` Tamil · `te` Telugu · `ur` Urdu

## Files

| File | Role |
|------|------|
| `detector.py` | The two-stage implementation |
| `languages.py` | The supported list, script ranges and alias map — **the authoritative one** |
| `__init__.py` | Public surface |
| `__main__.py` | CLI |
| `requirements.txt` | `langdetect` |

## Run it standalone

```bash
pip install -r modules/language_detection/requirements.txt   # ~1 MB, instant

python -m modules.language_detection "வணக்கம், எப்படி இருக்கிறீர்கள்?"
python -m modules.language_detection "Bonjour tout le monde"   # → Language not in list
python -m modules.language_detection --list
```

Exit code is 0 when detection succeeds, 1 otherwise — so it composes in shell
scripts.

## How detection works: script first, then langdetect

This is the part worth understanding, because it is what makes Indian languages
work at all.

### Stage 1 — Unicode script

Most Indian languages are written in a script that **exactly one** of them uses.
Tamil text is in the Tamil block; nothing else is. So the script *is* the
answer, and no statistical guessing is needed:

| Script | Language | Unicode block |
|--------|----------|---------------|
| Tamil | `ta` | U+0B80–U+0BFF |
| Telugu | `te` | U+0C00–U+0C7F |
| Kannada | `kn` | U+0C80–U+0CFF |
| Malayalam | `ml` | U+0D00–U+0D7F |
| Gujarati | `gu` | U+0A80–U+0AFF |
| Gurmukhi | `pa` | U+0A00–U+0A7F |
| Odia | `or` | U+0B00–U+0B7F |

These return `method="script"` with confidence 0.99 and never touch langdetect.

### Stage 2 — langdetect, narrowed by script

Three scripts are shared, so the script narrows the field and langdetect picks
the winner:

| Script | Candidates | Also used by (unsupported) |
|--------|-----------|---------------------------|
| Devanagari | `hi`, `mr`, `ne` | Sanskrit, Bhojpuri, Maithili |
| Bengali | `bn` | Assamese |
| Arabic | `ur` | Arabic, Persian, Sindhi |

**A single candidate still goes through langdetect.** This is deliberate and it
is the subtle part: "Urdu is the only Arabic-script language we support" is not
the same claim as "this Arabic-script text is Urdu". If the constrained lookup
finds no candidate in langdetect's ranking, the result is `Language not in
list` — so Arabic input is correctly rejected rather than silently mistranslated
as Urdu. There is a regression test for exactly this
(`test_arabic_is_not_mistaken_for_urdu`).

Latin script is deliberately **not** in the script table. It falls straight
through to unconstrained langdetect, so French and Spanish are properly rejected
instead of being forced into English, the only Latin-script language we support.

### Why this ordering

langdetect alone was the previous implementation, and it has two weaknesses that
script detection fixes outright:

- **Short text.** Under ~20 characters langdetect's n-grams fall below the
  confidence floor. `"வணக்கம்"` is one word, and script detection nails it.
  There is a test for short Indic input.
- **Odia.** langdetect has no Odia profile at all. Script detection adds the
  language for free.

## Configuration knobs

| Constant | Default | Effect |
|----------|---------|--------|
| `MIN_CONFIDENCE` | `0.60` | Below this, return the error code instead of guessing |
| `MIN_SCRIPT_SHARE` | `0.60` | A script must be this share of the letters before it is trusted |
| `SCRIPT_CONFIDENCE` | `0.99` | Confidence reported when a unique script settles it |
| `CODE_ALIASES` | `zh-cn→zh`, … | Fold regional variants into a supported code |

`MIN_SCRIPT_SHARE` is what handles code-mixed text. A Hindi sentence with a few
English words is still ≥60% Devanagari and resolves to Hindi; a mostly-English
sentence with one Hindi word falls through to langdetect.

## About langdetect

A Python port of Google's language-detection library. Naive Bayes over character
n-grams, 55 languages, pure Python, ~1 MB, no model download.

**It is non-deterministic by default.** The algorithm samples randomly, so the
same input can give different answers across runs. `detector.py` sets
`DetectorFactory.seed = 0` to pin it. Do not remove that line.

## Adding a language

Four files must agree, and `tests/test_contracts.py` fails if they don't:

1. `modules/language_detection/languages.py` → add to `SUPPORTED_LANGUAGES`,
   and to `UNAMBIGUOUS_SCRIPTS` or `AMBIGUOUS_SCRIPTS` as appropriate
2. `modules/translate_to_english/models.py` → add the FLORES code
3. `modules/translate_from_english/models.py` → add the FLORES code
4. `modules/text_to_speech/voices.py` → add a voice, or declare it text-only

Then add the code to `LANGUAGE_CHOICES` in `app.py` and a test sentence to
`SAMPLES` in `tests/test_language_detection.py` (a test enforces that too).

**Detection is the binding constraint, not translation.** IndicTrans2 handles
all 22 scheduled languages; this module handles 12. Before adding one, work out
which stage will catch it:

| Language | Script stage | langdetect | Verdict |
|----------|-------------|-----------|---------|
| Assamese `as` | Bengali — shared with `bn` | no profile | **blocked** |
| Sanskrit `sa` | Devanagari — shared | no profile | **blocked** |
| Sindhi `sd` | Arabic — shared | no profile | **blocked** |
| Kashmiri `ks` | Arabic/Devanagari — shared | no profile | **blocked** |
| Santali `sat` | Ol Chiki — unique | not needed | addable, but no gTTS voice |

A language on a *unique* script is easy: add the Unicode range and it works
without langdetect. A language sharing a script with something we already
support needs a langdetect profile to disambiguate, and langdetect has profiles
for only 11 Indian languages.

To go further you would swap langdetect for something with wider Indic
coverage — fastText's `lid.176` model has profiles for Assamese, Odia and
Sanskrit. That is a module 3 change only; nothing else in the pipeline moves.

## Why the language list is duplicated

Modules 3, 4, 5 and 6 each keep their own copy of the languages they handle,
rather than importing a shared `constants.py`.

This looks like a mistake and is not. A shared constants file is a shared
dependency: it means module 4 cannot be lifted out and used in another project
without dragging module 3 along, and it means "these four modules are
independent" is a claim the code contradicts.

The lists are also genuinely not the same list. Module 4 needs `xx→en`
checkpoints, module 5 needs `en→xx` checkpoints, and those sets differ — some
languages have one direction and not the other. Module 6 needs gTTS locales,
where Chinese is `zh-CN`, not `zh`. Forcing them into one table would mean
inventing a schema that satisfies all four, which is a bigger coupling than the
duplication it removes.

`tests/test_contracts.py` checks the lists agree where they must. That converts
"someone forgot to update a file" from a runtime surprise into a failing test.

## Testing

```bash
pytest tests/test_language_detection.py -v
```

Fast — no model downloads. Covers each supported language, the unsupported
path, gibberish, and empty input.

## Known limitations

- **Romanised Indic text is not detected.** "aap kaise ho" has no Devanagari
  for the script stage to find, so it falls through to langdetect, which reads
  it as a Latin-script language and rejects it. This is the biggest practical
  gap — many Indian users type this way. Fixing it needs a transliteration
  detector, which is a module 3 change only.
- **Short *Latin* text still fails.** "ok" is valid in many languages. Indic
  short text is fine now thanks to the script stage.
- **Assamese is reported as Bengali.** They share a script and langdetect has
  no Assamese profile, so Assamese input resolves to `bn` and gets translated
  as Bengali.
- **Heavily code-mixed text** ("Hinglish" with both scripts) resolves to
  whichever script passes `MIN_SCRIPT_SHARE`, or falls through to langdetect.

## Change requests

<!-- Add instructions here. Example:

### CR-1: Return the top 3 candidates
Expose the full ranked candidate list on DetectionResult so the UI can offer
"did you mean Spanish?" when confidence is borderline.

-->

_None yet._
