# Module 2 — Speech-to-Text

> **This file is the working spec for module 2.** To request a change, add it
> under [Change requests](#change-requests) at the bottom rather than describing
> it in chat.

## Purpose

Turn recorded speech into text. Nothing else — it does not detect language for
the pipeline and it does not translate.

## Contract

```python
from modules.speech_to_text import transcribe, transcribe_bytes

result = transcribe("samples/greeting.mp3")            # from a file path
result = transcribe_bytes(raw_bytes, suffix=".wav")    # from an upload

result.text                  # str   — the transcript
result.language               # str   — Whisper's guess, e.g. 'hi'. A HINT ONLY.
result.language_confidence   # float — 0.0 to 1.0
result.duration_seconds      # float
result.segments              # list  — [{'start', 'end', 'text'}, ...]
```

**Input:** path to `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.webm`, `.mp4`.
Optional `language=` hint (ISO 639-1) — pass it when you already know what was
spoken; it is faster and more accurate than letting Whisper detect.

**Output:** a frozen `TranscriptionResult`. `str(result)` gives the text.

**Errors:** raises `TranscriptionError` for a missing, empty, or unreadable
file, or an unsupported extension.

**`RELIABLE_LANGUAGES`** — `frozenset({"hi", "ta"})`. The set of languages
verified to come back in correct native script. Everything else this module
accepts audio for may transcribe into the wrong script — check
`result.language` against this set before trusting the output blindly. See
"Known limitations" below for the full evidence.

### Readiness

```python
from modules.speech_to_text import is_available

ready, reason = is_available()   # (True, None) or (False, 'missing faster_whisper -- pip install …')
```

`faster-whisper` is imported lazily, so `import modules.speech_to_text`
succeeds even when it is not installed. `is_available()` is how a caller finds
out *before* the first recording rather than during it. It uses
`importlib.util.find_spec`, so the check is cheap. Every module exports this;
`tests/test_contracts.py` enforces it.

## Files

| File | Role |
|------|------|
| `transcriber.py` | The implementation |
| `__init__.py` | Public surface |
| `__main__.py` | CLI |
| `requirements.txt` | `faster-whisper` |

## Run it standalone

```bash
pip install -r modules/speech_to_text/requirements.txt

python -m modules.speech_to_text samples/test_hi.mp3
python -m modules.speech_to_text samples/test_hi.mp3 --verbose
python -m modules.speech_to_text samples/test_hi.mp3 --language hi --model small
```

## Engine

**faster-whisper** — a CTranslate2 reimplementation of OpenAI's Whisper. Runs
locally on CPU, needs no API key and no internet after the first download.

| Size | Download | Speed (CPU) | Use when |
|------|----------|-------------|----------|
| `tiny` | ~75 MB | fastest | Testing the plumbing |
| `base` | ~140 MB | ~real-time | Not recommended — see below |
| `small` | ~480 MB | ~2× slower | **Default.** Minimum verified to output correct script for Hindi/Tamil. |
| `medium` | ~1.5 GB | ~6× slower | Did not fix the limitation below; not worth the cost here |

`base` was the original default and was tested: it transliterates Hindi into
Latin script ("Namaste, How are you?" instead of "नमस्ते, आप कैसे हैं?"). `small`
fixes that specific case. Neither size fixes most of the other 10 languages —
see the next section before assuming voice input works for a language just
because the model loaded without error.

## Configuration knobs

Set as environment variables, or edit the constants in `transcriber.py`:

| Variable | Default | Effect |
|----------|---------|--------|
| `WHISPER_MODEL_SIZE` | `small` | Model size from the table above |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8` is ~2× faster and half the RAM; `float32` was tested and did not fix the script issue below |

Two other choices live in the code:

- `vad_filter=True` — voice activity detection trims silence, which cuts
  runtime on recordings with dead air at the start.
- `beam_size=5` — beam search width. Lower is faster and slightly worse.

## Why we don't trust `result.language`

Whisper reports its own language guess, and it is usually right. We still route
the transcript through **module 3** instead of using it, for three reasons:

1. There must be **one** authority on what a language code means. Two detectors
   disagreeing is a bug that only shows up in production.
2. Whisper's code set is much wider than our supported list. It will happily
   return `sw`, and then module 4 has no model for it — the error surfaces one
   step too late, with a worse message.
3. Typed input has no Whisper stage at all. Routing both paths through module 3
   means one code path, not two.

The field is still exposed because it is genuinely useful for debugging, and
because a future change might use it as a hint to module 3.

## Caching

`_load_model` is wrapped in `@lru_cache(maxsize=2)`. Loading takes seconds and
the weights are hundreds of megabytes; caching keeps them resident. Two entries
means you can A/B two model sizes without thrashing.

In the Streamlit app this sits *inside* an `@st.cache_resource` import, so the
model loads once per server process.

## Testing

There is no automated test — it would need a checked-in audio fixture and a
model download in CI. To test by hand, generate a clip with module 6 and read
it back:

```bash
python -m modules.text_to_speech --lang hi "नमस्ते, आप कैसे हैं" -o samples/test_hi.mp3
python -m modules.speech_to_text samples/test_hi.mp3 --verbose
```

That round trip exercises modules 2 and 6 together without either importing the
other.

## Known limitations

### Native-script transcription by language — the important one

**Verified on real transcription runs, not assumed.** Whisper does not reliably
transcribe most Indic languages in their own script — it transliterates toward
Devanagari (Hindi's script) instead. Tested with gTTS-synthesized audio for all
12 target languages, across `base`/`small`/`medium` and `int8`/`float32`:

| Language | Language ID | Script/text | Verdict |
|---|---|---|---|
| Hindi (`hi`) | correct | correct Devanagari | **reliable** |
| Tamil (`ta`) | correct | correct Tamil script | **reliable** |
| Marathi (`mr`) | misdetected as `hi` | Devanagari (its real script) but garbled | unreliable |
| Nepali (`ne`) | correct | Devanagari (its real script) but garbled | unreliable |
| Bengali (`bn`) | correct | forced into Devanagari | broken |
| Telugu (`te`) | correct | forced into Devanagari | broken |
| Gujarati (`gu`) | correct | forced into Devanagari | broken |
| Kannada (`kn`) | correct | forced into Devanagari | broken |
| Malayalam (`ml`) | misdetected as `ta` | forced into Tamil script | broken |
| Punjabi (`pa`) | misdetected as `hi` | forced into Devanagari (not Gurmukhi) | broken |
| Urdu (`ur`) | misdetected as `hi` | forced into Devanagari (not Nastaliq) | broken |
| Odia (`or`) | not tested | — | no gTTS voice to generate a test clip |

Bumping the model size made this **worse**, not better — `medium` on the
Bengali sample produced Telugu-script output with a hallucinated English word.
`float32` compute instead of `int8` did not help either. This points to a
training-data imbalance in Whisper itself (Hindi dominates its Indic data), not
a configuration problem in this module.

`RELIABLE_LANGUAGES = frozenset({"hi", "ta"})` in `transcriber.py` records the
verified-good set. `app.py` checks `result.language` against it after
transcription and shows a caption warning the user when it falls outside —
see `transcribe_upload()` in [MODULE_1](MODULE_1_STREAMLIT_UI.md). Typed input
is unaffected and covers all 12 languages.

**Caveats on this finding, in case it turns out to be too pessimistic:**
- All test audio was **gTTS-synthesized**, not real human speech. Synthetic
  speech may transcribe differently — for better or worse — than a natural
  recording. This has not been checked against a real microphone.
- `large-v3` (~3 GB) was not tested. It is Whisper's strongest multilingual
  model and might do better on low-resource Indic languages, though a bigger
  model already made Bengali worse once, so this is not a confident bet.

If you want to push on this further: record real speech in one of the "broken"
languages and re-run `python -m modules.speech_to_text <file> --verbose`, or
try `WHISPER_MODEL_SIZE=large-v3`.

### Other limitations

- **Whisper hallucinates on silence.** VAD filtering mostly handles it, but a
  clip of pure noise can produce a plausible-looking sentence.
- **First call is slow** — the model downloads, then loads.
- **CPU only** as configured. For a CUDA GPU, change `device="cpu"` to
  `device="cuda"` and `compute_type` to `"float16"` in `_load_model`.

## Change requests

<!-- Add instructions here. Example:

### CR-1: Return word-level timestamps
Pass word_timestamps=True to model.transcribe and expose the word list on
TranscriptionResult.

-->

_None yet._
