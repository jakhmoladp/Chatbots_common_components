# Module 1 — Streamlit Chatbot UI

> **This file is the working spec for module 1.** To request a change, add it
> under [Change requests](#change-requests) at the bottom rather than describing
> it in chat.

## Purpose

The face of the app and the only component allowed to know about more than one
module. It collects input (typed or spoken), drives the pipeline, and renders
the result.

## Files

| File | Role |
|------|------|
| `app.py` | The whole UI and the pipeline orchestration |
| `bot.py` | The chatbot brain — English in, English out. A stub. |

## Contract

This module has no importable API; it is the entry point.

```bash
streamlit run app.py
```

## The pipeline it owns

`run_pipeline(user_text, target_language, speak)` in `app.py` is the single
function that stitches the modules together:

| Step | Calls | On failure |
|------|-------|-----------|
| 1 | `language_detection.detect_language(text)` | Show the error code, stop |
| 2 | `translate_to_english.translate_to_english(text, code)` | Show error, stop |
| 3 | `bot.reply(english)` | — |
| 4 | `translate_from_english.translate_from_english(english, target)` | Show error, stop |
| 5 | `text_to_speech.can_speak(target)` then `synthesize_bytes(...)` | Warn, keep the text |

Step 5 checks `can_speak()` before synthesising. Odia is translatable but has no
gTTS voice, and a declared gap should produce a clear caption rather than an
exception caught in a `try` block.

Speech-to-text runs *before* the pipeline, in the input handler, because it
turns audio into the same text a keyboard would have produced.

`run_pipeline` returns a `trace` dict rather than just the answer, so the UI can
show the intermediate English pivot. That is a teaching feature — flip "Show
pipeline details" off in the sidebar to hide it.

## Screen layout

**Sidebar**
- *Reply language* — the "language previously selected by user" from the spec.
  Stored in `st.session_state.target_language`, consumed by modules 5 and 6.
- *Speak replies* — toggles module 6.
- *Show pipeline details* — reveals the detected code and the English pivot.
- *Module status* — a green tick or red cross per module. See below.
- *Clear conversation*.

**Main pane** — title, caption naming the current reply language, the chat
transcript, suggestion pills on an empty conversation, and `st.chat_input`
pinned at the bottom.

## Input: one widget, three ways in

```python
prompt = st.chat_input(
    "Type a message, attach audio, or record…",
    accept_file=True,
    file_type=AUDIO_TYPES,
    accept_audio=True,
    submit_mode="disable",
)
```

`st.chat_input` handles typing, file attachment and live recording in a single
widget, returning a `ChatInputValue` with `.text`, `.files` and `.audio`.

Three things this buys us:

- **`accept_audio` records at 16 kHz by default**, which is exactly the sample
  rate Whisper wants. Recording at 44.1 kHz and resampling would be wasted work.
- **A submission is a discrete event.** An earlier version of this file used a
  sidebar `st.audio_input` plus a hash of the clip in session state, because
  that widget keeps returning the same audio on every rerun and would otherwise
  re-transcribe and re-answer forever. `st.chat_input` has no such problem, and
  the hash guard is gone.
- **`submit_mode="disable"`** greys out the input while the pipeline runs, so a
  user cannot queue three messages while a model is loading.

When both text and audio arrive, audio wins and the transcript becomes the
message — the recording is the more deliberate act.

## How module loading works

`load_module(name)` does two things, and only doing the first is a trap:

1. Import the package, catching any exception.
2. Call the module's own `is_available()`, which returns `(ready, reason)`.

Step 2 is necessary because **every module defers its heavy import to first
use**. `import modules.translate_to_english` succeeds perfectly well on a
machine with no `torch` installed — the failure only surfaces mid-conversation.
Without step 2 the sidebar shows five green ticks and then the app dies on the
first message.

Each module answers for itself, so `app.py` needs no knowledge of what any
module depends on. `tests/test_contracts.py` enforces that all five export
`is_available()`.

The function is decorated with `@st.cache_resource` so the import cost and the
model weights are paid once per server process, not once per rerun.

## State

| Key | Holds |
|-----|-------|
| `history` | List of `{role, content, caption?, audio?, trace?}` turns |
| `target_language` | ISO 639-1 code chosen in the sidebar |
| `pending` | `(text, caption)` awaiting processing, or None |

`pending` exists because two input paths — the chat input and the suggestion
pills — both need to inject a message, and the pills path needs an
`st.rerun()` to clear itself. Funnelling both through one slot means the
turn-handling code is written once.

## Configuration knobs

| What | Where |
|------|-------|
| Languages offered in the dropdown | `LANGUAGE_CHOICES` in `app.py` |
| Default reply language | `DEFAULT_TARGET` in `app.py` (`"hi"`) |
| Suggestion chips | `SUGGESTIONS` in `app.py` |
| Page title / icon / layout | `st.set_page_config(...)` at the top of `app.py` |

`DEFAULT_TARGET` must be a key of `LANGUAGE_CHOICES`. The initialiser also
*repairs* a stale `target_language` rather than trusting it: a browser session
started before the language list changed would otherwise crash the selectbox
with `ValueError: 'fr' is not in list`. This is not hypothetical — it happened
when the app moved from European to Indian languages.

## Testing

Streamlit ships `AppTest`, which runs the script headlessly with no browser:

```python
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=90).run()
assert not at.exception

at.session_state.pending = ("नमस्ते, आप आज कैसे हैं?", None)
at.run()
print([e.value for e in at.error])
```

Setting `pending` directly is the easiest way to drive a turn — it skips having
to construct a `ChatInputValue`.

Then check by hand in the browser:

1. Sidebar module status matches what is actually installed.
2. Type `नमस्ते, आप कैसे हैं?` with reply language Tamil → a Tamil answer appears.
3. Type `Bonjour, comment allez-vous ?` → red `Language not in list`.
4. Record audio → transcript appears in your turn, captioned "transcribed from
   audio".
5. Change reply language mid-conversation → the *next* answer switches language;
   past turns stay as they were.
6. Select **Odia** → sidebar shows a text-only caption, and replies arrive as
   text with no audio player.
7. Turn off wifi and send a message → text reply still appears, with an amber
   caption explaining that audio failed.

## Design decisions

**Why one file instead of Streamlit multipage?** There is one screen. Multipage
would add navigation with nothing to navigate to.

**Why is the bot a stub?** The brief is a translation feature. Making the brain
pluggable keeps the demo runnable with zero API keys and zero cost, and makes
the seam obvious.

**Why show the English pivot?** Because when a translation looks wrong, the
pivot tells you which of the two hops broke it.

## Change requests

<!-- Add instructions here. Example:

### CR-1: Add a "download transcript" button
Export the conversation as a .txt file with both the original and translated
text for each turn.

-->

_None yet._
