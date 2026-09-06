# Module 4 — Indian Language → English

> **This file is the working spec for module 4.** To request a change, add it
> under [Change requests](#change-requests) at the bottom rather than describing
> it in chat.

## Purpose

Translate text from a supported Indian language into English. This is the
inbound half of the pivot: everything the chatbot sees is English.

## Contract

```python
from modules.translate_to_english import translate_to_english

english = translate_to_english("नमस्ते, आप कैसे हैं?", "hi")
# → "Hello, how are you?"
```

**Input:** `text` (str) and `source_language` (ISO 639-1 code present in
`FLORES_CODES`).

**Output:** English text as a plain `str`.

**Special cases:**
- Empty or whitespace-only input returns `""`.
- `source_language="en"` returns the text unchanged. This is deliberate — the
  caller runs detection first and often gets `en` back, and it should not have
  to special-case that.

**Errors:**
- `UnsupportedLanguageError` (a `ValueError`) — no FLORES mapping for that code.
- `TranslationError` (a `RuntimeError`) — dependencies missing, model gated or
  unreachable, or inference failed.

### Readiness

```python
from modules.translate_to_english import is_available

ready, reason = is_available()
```

Everything heavy is imported lazily, so `import modules.translate_to_english`
succeeds on a machine with no torch — the failure would otherwise surface
mid-conversation. `is_available()` uses `importlib.util.find_spec`, which
matters here: importing `torch` costs seconds and hundreds of megabytes, and a
health check must not do that.

It reports the toolkit separately from the rest, because that is the dependency
most likely to be missing and it needs a different fix (a compiler, not a
`pip install`).

## Supported sources

`bn` Bengali · `gu` Gujarati · `hi` Hindi · `kn` Kannada · `ml` Malayalam ·
`mr` Marathi · `ne` Nepali · `or` Odia · `pa` Punjabi · `ta` Tamil ·
`te` Telugu · `ur` Urdu

Plus `en`, handled as a pass-through.

## Prerequisites

**Both are one-off, and both are real blockers — the module cannot run without
them.** Modules 1, 2, 3 and 6 need neither.

### 1. Microsoft C++ Build Tools (Windows)

`IndicTransToolkit` publishes wheels for macOS and Linux only. On Windows `pip`
falls back to the source distribution and compiles a Cython extension, which
fails with:

```
error: Microsoft Visual C++ 14.0 or greater is required.
```

Install from <https://visualstudio.microsoft.com/visual-cpp-build-tools/>,
select the **"Desktop development with C++"** workload, then reopen your
terminal.

### 2. A Hugging Face account — the model is gated

`ai4bharat/indictrans2-indic-en-dist-200M` is marked `gated: auto`. Approval is
automatic, but you must be signed in and have accepted the terms:

1. Create a free account at <https://huggingface.co>.
2. Visit the [model page](https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M)
   and accept the terms.
3. Create a token at <https://huggingface.co/settings/tokens>.
4. `huggingface-cli login` and paste it, or set the `HF_TOKEN` env var.

Without this, `_load()` raises `TranslationError` with these instructions
attached.

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
pip install -r modules/translate_to_english/requirements.txt

python -m modules.translate_to_english --from hi "नमस्ते, आप कैसे हैं?"
python -m modules.translate_to_english --from ta "வணக்கம், எப்படி இருக்கிறீர்கள்?"
python -m modules.translate_to_english --list
```

## Engine

**IndicTrans2** from AI4Bharat, checkpoint
`ai4bharat/indictrans2-indic-en-dist-200M` (~900 MB distilled). Purpose-built
for the 22 scheduled Indian languages and the best open Indic translation
available.

**One model covers every source language.** This is the structural difference
from a per-pair setup: instead of a separate 300 MB checkpoint per language,
there is a single model and a language *tag* telling it what it is reading.
Hence `@lru_cache(maxsize=1)` — a second entry would never be used.

Three things the code has to get right:

- **`trust_remote_code=True`.** IndicTrans2 ships a custom architecture
  (`modeling_indictrans.py`) that is not part of `transformers`. Without the
  flag, loading fails.
- **FLORES-200 codes.** The model wants `hin_Deva`, not `hi` — language *and*
  script. `models.py` owns that mapping.
- **`IndicProcessor`.** `preprocess_batch` normalises the script, masks
  entities such as URLs and numbers, and prepends the language tags;
  `postprocess_batch` restores the entities. Skipping this step produces
  noticeably worse output — it is not optional decoration.

For the larger `ai4bharat/indictrans2-indic-en-1B`, change `MODEL_NAME` in
`models.py`. Nothing else moves.

## Configuration knobs

| Constant | Default | Effect |
|----------|---------|--------|
| `MODEL_NAME` | `…-dist-200M` | Swap for the 1B checkpoint for better quality |
| `MAX_CHARS_PER_CHUNK` | `400` | Text longer than this is split on sentence boundaries |
| `@lru_cache(maxsize=1)` on `_load` | `1` | One model serves all languages |

## Why the chunking exists

IndicTrans2 is trained on single sentences. Feed it a paragraph and quality
drops sharply.

`_chunk()` splits on `.` `!` `?` **and the danda `।` and double danda `॥`** —
Devanagari and several other Indic scripts use the danda as a full stop, and an
ASCII-only splitter would treat a whole Hindi paragraph as one sentence. The
Arabic question mark `؟` is there for Urdu. (Module 5 needs none of this: its
input is always English.)

The visible cost: **pronouns can drift across chunk boundaries**, because each
chunk is translated with no knowledge of the others.

## Adding a language

1. Confirm IndicTrans2 supports it — it covers all 22 scheduled languages, so
   translation is rarely the blocker.
2. Add the FLORES-200 code to `FLORES_CODES` and the name to `LANGUAGE_NAMES`.
3. Update modules 3, 5 and 6 to match — see
   [MODULE_3](MODULE_3_LANGUAGE_DETECTION.md#adding-a-language). **Detection is
   usually the real constraint**, not this module.
4. Run `pytest tests/test_contracts.py`.

## Testing

Not covered by automated tests — the model is ~900 MB and gated, so CI would
need a token and a large download. `tests/test_contracts.py` does verify this
module's language list agrees with modules 3, 5 and 6; that runs instantly and
downloads nothing.

Verify translation by hand:

```bash
python -m modules.translate_to_english --from hi "मैं एक कप चाय चाहता हूँ।"
# expect something like: "I want a cup of tea."

python -m modules.translate_to_english --from ta "நான் ஒரு கப் தேநீர் வேண்டும்."
# expect something like: "I want a cup of tea."
```

## Known limitations

- **Two setup prerequisites**, above. Neither is optional.
- **First call downloads ~900 MB** and takes a minute or two.
- **CPU inference is slow** — expect 1–3 seconds per sentence with `num_beams=5`.
  Lower it in `translate_to_english` to trade quality for speed.
- **No context across chunks** — see the chunking section.
- **Romanised input is not handled.** The model expects native script. Text
  detected as Hindi but typed in Latin letters will not translate well — though
  in practice module 3 rejects it first.

## Change requests

<!-- Add instructions here. Example:

### CR-1: Add a batch API
Expose translate_many(texts, source_language) that preprocesses and tokenizes
the whole list in one batch instead of looping. IndicTrans2 batches well, so
this should be several times faster for bulk work.

-->

_None yet._
