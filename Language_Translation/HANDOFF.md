# Handoff — state of the project as of 2026-08-08 (session 2)

Written across two build sessions, for whoever (or whatever) picks this up
next. The [README](README.md) and `docs/MODULE_*.md` describe how the project
*works*; this file describes **what has actually been run, what has not, and
what to do next**. Delete it once the project is fully working.

**Session 2 changed the picture on module 2** — it now runs, but voice input
turned out to be reliable for only 2 of 12 languages. See §2 and §3.

---

## 1. What exists

A Streamlit translation chatbot for **English + 12 Indian languages**, built as
six deliberately independent modules. Full layout and rationale are in the
[README](README.md). Every module has a spec at `docs/MODULE_N_*.md`, and each
of those ends with a **Change requests** section — that is where instructions
for that module are meant to go.

```
app.py              module 1  Streamlit UI + pipeline orchestration
bot.py                        chatbot brain — A STUB, see §5
modules/speech_to_text/       module 2  faster-whisper
modules/language_detection/   module 3  Unicode script + langdetect
modules/translate_to_english/ module 4  IndicTrans2 (indic → en)
modules/translate_from_english/ module 5  IndicTrans2 (en → indic)
modules/text_to_speech/       module 6  gTTS
tests/                        43 tests, all passing
docs/                         one spec per module
```

**Languages:** `en` `hi` `bn` `mr` `te` `ta` `gu` `kn` `ml` `pa` `ur` `ne`, plus
`or` (Odia) as text-only. Anything else returns `Language not in list`.

---

## 2. Verification status — read this before trusting anything

| Module | Code | Actually executed? | Notes |
|---|---|---|---|
| 1 · Streamlit UI | done | **Yes** | Boots clean; verified with `AppTest`. Both error paths produce correct messages. |
| 2 · Speech-to-text | done | **Yes — with a real caveat** | Runs. Verified reliable for **Hindi and Tamil only**. The other 10 languages transcribe into the wrong script — this is a genuine Whisper limitation, not unfinished code. Full evidence in §3. |
| 3 · Language detection | done | **Yes** | 13/13 languages correct, 5/5 rejections correct, on real sentences. |
| 4 · Indic → English | done | **NO — see §4** | IndicTrans2. Written from docs, never executed. Highest risk in the project. |
| 5 · English → Indic | done | **NO — see §4** | Same. |
| 6 · Text-to-voice | done | **Yes** | Generated playable Hindi, Tamil, Bengali, Telugu, Gujarati, Kannada, Malayalam, Punjabi, Urdu, Nepali and Marathi MP3s in `samples/`. |

**Installed in `.venv` right now:** `streamlit` 1.61.1, `langdetect` 1.0.9,
`gTTS` 2.5.4, `pytest` 9.1.1, `faster-whisper` 1.2.1.

**NOT installed:** `torch`, `transformers`, `IndicTransToolkit`,
`sentencepiece`, `sacremoses`, `huggingface-hub`.

This is why the sidebar currently shows modules 4 and 5 in red, and 2/3/6 green.
That is correct behaviour, not a bug.

---

## 3. Module 2 finding: voice input only reliable for Hindi and Tamil

This is the single most important thing learned in session 2. Full detail and
the complete per-language evidence table is in
[docs/MODULE_2_SPEECH_TO_TEXT.md § Known limitations](docs/MODULE_2_SPEECH_TO_TEXT.md#known-limitations).
Short version:

Whisper (via faster-whisper) transliterates most Indic languages toward
**Devanagari** (Hindi's script) instead of transcribing them in their own
script — confirmed across `base`/`small`/`medium` model sizes and both
`int8`/`float32` compute types, so it is not a config problem in this module.
Bigger models made it *worse* on the one case tested at all three sizes
(Bengali): `medium` produced Telugu-script output with a hallucinated English
word mixed in.

**Only Hindi and Tamil were verified reliable.** This is recorded as
`RELIABLE_LANGUAGES = frozenset({"hi", "ta"})` in
`modules/speech_to_text/transcriber.py`, and `app.py` checks a transcript's
detected language against it, showing a caption warning when it falls outside.
Typed input is unaffected and covers all 12 languages — this only limits the
*voice* input path.

**What was NOT tested, in case this turns out to be too pessimistic:**
- All test audio was gTTS-*synthesized*, not real human speech. This has not
  been checked against a real microphone recording, which might behave
  differently.
- `large-v3` (~3 GB) was not tried. It's Whisper's strongest multilingual
  model, though a bigger model already made Bengali worse once.

If you want to push on this: record real speech in a "broken" language (say,
Telugu or Gujarati) and run
`.venv\Scripts\python -m modules.speech_to_text <file> --verbose`, or try
`WHISPER_MODEL_SIZE=large-v3`. Update `RELIABLE_LANGUAGES` and the evidence
table in the module doc if the result changes.

The user was asked how to handle this finding (document-and-move-on vs.
real-mic test vs. large-v3) and did not respond in the session, so the
reversible, no-cost option was taken: document it, ship a UI warning, don't
block on further investigation. This is a decision worth revisiting if the
user has a preference.

---

## 4. The next task: make modules 4 and 5 actually run

This is the critical path. Everything else is polish.

### Step 1 — Microsoft C++ Build Tools (one-off, ~15–30 min)

`IndicTransToolkit` publishes **no Windows wheel** (verified: macOS + Linux
only, all Python versions). `pip` compiles a Cython extension from source and
fails with `error: Microsoft Visual C++ 14.0 or greater is required`.

Install from <https://visualstudio.microsoft.com/visual-cpp-build-tools/> and
select the **"Desktop development with C++"** workload. Reopen the terminal
afterwards.

### Step 2 — Hugging Face account (one-off, ~5 min)

Both IndicTrans2 checkpoints are **gated** (`gated: auto` — approval is
automatic, but you must be signed in and have accepted the terms).

1. Free account at <https://huggingface.co>
2. Accept terms on **both** pages (accepting one does not cover the other):
   - <https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M>
   - <https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M>
3. Token at <https://huggingface.co/settings/tokens>
4. `huggingface-cli login`, or set `HF_TOKEN`

### Step 3 — Install and run

```bash
cd "C:\Users\Devendra Prasad\OneDrive\MyProjects\Language_Translation"
.venv\Scripts\pip install -r requirements.txt      # ~2.5 GB, mostly torch

# Smallest possible first test — this downloads ~900 MB on first call
.venv\Scripts\python -m modules.translate_to_english --from hi "नमस्ते, आप कैसे हैं?"
```

### Step 4 — Expect to fix things

The IndicTrans2 code in `modules/translate_*/translator.py` was written from the
documented API and **has never executed**. Most likely breakages, in order:

1. **`tokenizer.batch_decode(...)`** — the current code uses the standard
   `batch_decode(generated, skip_special_tokens=True)`. Some IndicTrans2
   examples instead use
   `tokenizer.batch_decode(generated.detach().cpu().tolist(), src=False)`. If
   output is garbled or empty, this is the first thing to change.
2. **`IndicProcessor` import path** — moved between releases. The code already
   tries `from IndicTransToolkit.processor import IndicProcessor` then falls
   back to `from IndicTransToolkit import IndicProcessor`. If both fail, check
   what the installed version actually exposes.
3. **`trust_remote_code=True`** may prompt interactively on first load, which
   would hang Streamlit. If so, pre-download once from a plain terminal.
4. **`num_beams=5`** may be slow on CPU. Drop to 1 while debugging.

Once it runs, do a round-trip sanity check:

```bash
.venv\Scripts\python -m modules.translate_from_english --to hi "Where is the train station?" | .venv\Scripts\python -m modules.translate_to_english --from hi
```

Module 2 is already done — no step 5 needed there anymore.

---

## 5. Decisions already made — please don't silently undo these

| Decision | Why | Where |
|---|---|---|
| **IndicTrans2, not NLLB-200** | User chose it *after* being told about the compiler and gating. They accept setup friction for quality. NLLB was the recommended easier path and was explicitly declined. | modules 4, 5 |
| **English pivot** | Bot only ever thinks in English, so it needs 2 models not N². Costs some nuance on indic→indic. | whole pipeline |
| **No module imports a sibling** | The user's explicit requirement. `tests/test_contracts.py` walks the AST and fails the build if violated. | all modules |
| **Duplicated language lists** | Each module owns its own copy. A shared `constants.py` would be a hidden coupling that makes "modules are independent" false. Contract tests keep the copies honest. | modules 3–6 |
| **Script detection before langdetect** | Fixes short-Indic-text failures and adds Odia. | module 3 |
| **Odia is text-only, not dropped** | IndicTrans2 translates it; gTTS has no voice. Declared in `TEXT_ONLY_LANGUAGES`. | module 6 |
| **`is_available()` on every module** | Imports are lazy, so a module can import fine and still be unusable. Without this the sidebar showed five green ticks with no torch installed. | all modules |
| **`small` Whisper model, not `base`** | `base` transliterates Hindi into Latin script; `small` is the minimum that gets Hindi and Tamil right. Neither fixes the other 10 languages — see §3. | module 2 |
| **Voice input gated by `RELIABLE_LANGUAGES`** | Rather than silently feed a garbled transcript downstream, `app.py` warns the user when the transcribed language falls outside the verified-good set. | modules 1, 2 |

### Traps already hit and fixed — don't reintroduce

- **Health check that only tries the import.** Lazy imports mean that always
  succeeds. Must call `is_available()`.
- **Single-candidate script detection.** Treating `Arabic → ur` and
  `Latin → en` as certainties made Arabic detect as Urdu and French as English.
  Shared scripts must be confirmed by langdetect. Regression test exists.
- **Default reply language not in the language list.** Crashed the app on boot
  with `ValueError: 'fr' is not in list`. The initialiser now repairs a stale
  `st.session_state.target_language`.
- **Sidebar `st.audio_input` + hash guard.** Replaced by
  `st.chat_input(accept_audio=True)`, which records at 16 kHz and is a discrete
  submit event. Do not go back to the old pattern.
- **Guessing model names.** Several plausible `Helsinki-NLP/opus-mt-*` Indic
  checkpoints return 401 and do not exist. **Verify against the HF API before
  writing a model name into code.**
- **A health check that only imports a module proves nothing about voice
  quality either.** `faster-whisper` importing fine says nothing about which
  languages it transcribes correctly — that took actually running it against
  real audio in all 12 languages to find out. Don't assume a module "works"
  from it loading without error; test its actual output where the risk is
  language-specific, not just library-specific.

---

## 6. Work remaining, roughly in priority order

1. **[Critical] Get modules 4 and 5 running** — §4 above.
2. **[High] End-to-end test** — speak Hindi into the app, get spoken Tamil out.
   Nothing has exercised the full six-module chain yet (module 2 → 3 → 4 → bot
   → 5 → 6 in one request). Do this as soon as 4/5 are running.
3. **[Medium] Decide whether to chase the module 2 finding further** — §3. Real
   mic test, or try `large-v3`, or accept Hindi/Tamil-only voice input as the
   shipped scope. This is a product decision as much as a technical one.
4. **[Medium] Replace `bot.py`** — it is a stub with canned replies. Contract is
   English in, English out; swap in an LLM and nothing else changes. Note the
   user has an Anthropic API key set up for their other project (VoiceNotes).
5. **[Medium] Romanised Indic input** — "aap kaise ho" is currently rejected.
   This is the biggest practical gap for Indian users, and it also means a
   Hindi speaker cannot work around the module 2 script issue by typing in
   Latin script. It is a module 3 change only. Would need transliteration
   detection.
6. **[Low] Widen language coverage** — Assamese, Sanskrit, Sindhi and Kashmiri
   are blocked at *detection*, not translation. Swapping langdetect for
   fastText `lid.176` would unblock several. Module 3 change only.
7. **[Low] Delete this file** once 1–2 are done.

---

## 7. Practical notes

- **Python:** use `.venv\Scripts\python.exe`. The bare `python` on PATH is
  3.13 at `AppData\Local\Programs\Python\Python313`; `python3` is a Microsoft
  Store stub that does not work.
- **Run the app:** `.venv\Scripts\streamlit run app.py`
- **Tests:** `.venv\Scripts\python -m pytest tests/ -q` — 42 passing, runs in
  under a second, downloads nothing.
- **Headless UI testing:** `streamlit.testing.v1.AppTest` works well. Set
  `at.session_state.pending = ("text", None)` to drive a turn without
  constructing a `ChatInputValue`.
- **Unicode in PowerShell:** set `$env:PYTHONIOENCODING = "utf-8"` before
  printing Indic text, or it mangles.
- **Streamlit docs:** the installed package ships version-matched reference
  docs at
  `.venv\Lib\site-packages\streamlit\.agents\skills\developing-with-streamlit\`.
  Worth reading before changing `app.py` — it is how the `accept_audio` and
  `width="stretch"` improvements were found.
- **`samples/`** holds a `test_<code>.mp3` for every one of the 12 languages
  (generated by module 6), except Odia which has no voice. Useful fixtures for
  testing modules 2 and 3.
- **PowerShell + native exe + `2>&1` is unreliable.** Redirecting a native
  exe's stderr inside PowerShell wraps it in a NativeCommandError and reports
  exit 1 even on success, and can break downstream piping (e.g. into
  `Select-String`). Prefer `*> file.log` and then `Get-Content file.log`
  instead of piping directly. Also remember `Set-Location` explicitly at the
  start of every PowerShell call — its working directory does not inherit from
  a prior Bash `cd`.
