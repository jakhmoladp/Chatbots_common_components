"""Module 1 -- Streamlit chatbot UI.

This is the only file that knows about more than one module. It owns the
pipeline; the modules themselves stay ignorant of each other.

    voice in -> [2] speech-to-text -> text
    text     -> [3] detect language -> code (or 'Language not in list')
    text     -> [4] translate to English
    English  -> bot.reply() -> English
    English  -> [5] translate to the user's chosen language
    reply    -> [6] text-to-speech -> audio out

Run with:  streamlit run app.py
Design notes: docs/MODULE_1_STREAMLIT_UI.md
"""

from __future__ import annotations

import streamlit as st

import bot

st.set_page_config(page_title="Translation chatbot", page_icon=":material/translate:")

# English plus the Indian languages the round trip supports. Kept here because
# the UI is allowed to know the intersection of what modules 3, 4, 5 and 6 each
# support -- the modules themselves each own their own list.
LANGUAGE_CHOICES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "mr": "Marathi",
    "te": "Telugu",
    "ta": "Tamil",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
    "ne": "Nepali",
}

AUDIO_TYPES = ["wav", "mp3", "m4a", "ogg", "flac"]

SUGGESTIONS = {
    ":blue[:material/waving_hand:] नमस्ते": "नमस्ते, आप आज कैसे हैं?",
    ":green[:material/waving_hand:] வணக்கம்": "வணக்கம், நீங்கள் இன்று எப்படி இருக்கிறீர்கள்?",
    ":violet[:material/coffee:] বাংলা": "সুপ্রভাত, আমি এক কাপ চা চাই।",
    ":orange[:material/error:] Unsupported": "Bonjour, comment allez-vous aujourd'hui ?",
}


# --------------------------------------------------------------------------
# Module loading
#
# Each module is imported lazily and independently. A module whose dependency
# is missing degrades that one feature instead of crashing the whole app --
# this is what "the modules are independent" buys us at runtime.
# --------------------------------------------------------------------------

MODULES = {
    "speech_to_text": "2 · Speech-to-text",
    "language_detection": "3 · Language detection",
    "translate_to_english": "4 · To English",
    "translate_from_english": "5 · From English",
    "text_to_speech": "6 · Text-to-speech",
}


@st.cache_resource(show_spinner=False)
def load_module(name: str):
    """Import one module and confirm it can run, returning (module, error).

    Two separate things have to be true, and only checking the first is a trap:
    the package must import, *and* its third-party dependencies must be
    present. Every module defers its heavy import (torch, faster-whisper) to
    first use, so `import modules.translate_to_english` succeeds happily on a
    machine with no torch installed and only blows up mid-conversation.

    Each module answers for itself via is_available(), so this function needs
    no knowledge of what any individual module depends on.

    Cached as a resource because the imports pull large model libraries into
    memory and must happen once per server process, not once per rerun.
    """
    try:
        if name == "speech_to_text":
            from modules import speech_to_text as module
        elif name == "language_detection":
            from modules import language_detection as module
        elif name == "translate_to_english":
            from modules import translate_to_english as module
        elif name == "translate_from_english":
            from modules import translate_from_english as module
        elif name == "text_to_speech":
            from modules import text_to_speech as module
        else:
            return None, f"Unknown module {name!r}"
    except Exception as exc:  # ImportError, or a broken optional backend
        return None, str(exc)

    ready, reason = module.is_available()
    if not ready:
        return None, reason
    return module, None


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def run_pipeline(user_text: str, target_language: str, speak: bool) -> dict:
    """Take the user's raw text through all the back-end modules.

    Returns a dict describing everything that happened, so the UI can show the
    intermediate steps rather than just the final answer.
    """
    trace: dict = {
        "detected": None,
        "detected_name": None,
        "english_in": None,
        "english_out": None,
        "reply": None,
        "audio": None,
        "error": None,
        "warnings": [],
    }

    # --- Module 3: detect ---------------------------------------------------
    detection_mod, err = load_module("language_detection")
    if err:
        trace["error"] = f"Language detection unavailable: {err}"
        return trace

    result = detection_mod.detect_language(user_text)
    if not result.ok:
        # This is the spec's error path. Surface the code verbatim.
        trace["error"] = result.error
        if result.detected_raw:
            trace["warnings"].append(
                f"The engine guessed `{result.detected_raw}` at "
                f"{result.confidence:.0%} confidence, which is not in the supported list."
            )
        return trace

    trace["detected"] = result.code
    trace["detected_name"] = result.name

    # --- Module 4: source -> English ---------------------------------------
    to_en_mod, err = load_module("translate_to_english")
    if err:
        trace["error"] = f"Translation to English unavailable: {err}"
        return trace

    try:
        trace["english_in"] = to_en_mod.translate_to_english(user_text, result.code)
    except Exception as exc:
        trace["error"] = f"Could not translate to English: {exc}"
        return trace

    # --- The bot itself -----------------------------------------------------
    trace["english_out"] = bot.reply(trace["english_in"])

    # --- Module 5: English -> the language the user picked ------------------
    from_en_mod, err = load_module("translate_from_english")
    if err:
        trace["error"] = f"Translation from English unavailable: {err}"
        return trace

    try:
        trace["reply"] = from_en_mod.translate_from_english(
            trace["english_out"], target_language
        )
    except Exception as exc:
        trace["error"] = f"Could not translate the reply: {exc}"
        return trace

    # --- Module 6: speak the reply -----------------------------------------
    # A TTS failure is not fatal; the user still gets the text.
    if speak:
        tts_mod, err = load_module("text_to_speech")
        if err:
            trace["warnings"].append(f"Text-to-speech unavailable: {err}")
        elif not tts_mod.can_speak(target_language):
            # A declared gap, not a failure. Odia is the current example.
            name = LANGUAGE_CHOICES.get(target_language, target_language)
            trace["warnings"].append(f"{name} is text-only — gTTS has no voice for it.")
        else:
            try:
                trace["audio"] = tts_mod.synthesize_bytes(
                    trace["reply"], language=target_language
                )
            except Exception as exc:
                trace["warnings"].append(f"Could not generate audio: {exc}")

    return trace


def transcribe_upload(audio_file) -> tuple[str | None, str | None, str | None]:
    """Run module 2 over an uploaded or recorded clip.

    Returns (text, error, warning). error means the transcript is unusable;
    warning means it worked but may be unreliable -- see RELIABLE_LANGUAGES.
    """
    stt_mod, err = load_module("speech_to_text")
    if err:
        return None, f"Speech-to-text unavailable: {err}", None

    name = getattr(audio_file, "name", "recording.wav")
    suffix = f".{name.rsplit('.', 1)[-1].lower()}" if "." in name else ".wav"

    try:
        result = stt_mod.transcribe_bytes(audio_file.getvalue(), suffix=suffix)
    except Exception as exc:
        return None, f"Could not transcribe the audio: {exc}", None

    if not result.text.strip():
        return None, "The recording produced no text. Try again, closer to the mic.", None

    warning = None
    if result.language not in stt_mod.RELIABLE_LANGUAGES:
        # Verified on real runs: Whisper transliterates most Indic languages
        # toward Devanagari instead of their own script. Only Hindi and Tamil
        # were confirmed reliable. See docs/MODULE_2_SPEECH_TO_TEXT.md.
        name = LANGUAGE_CHOICES.get(result.language, result.language or "this language")
        warning = (
            f"Voice input is only verified reliable for Hindi and Tamil. "
            f"The transcript (detected as {name}) may be in the wrong script — "
            f"check it before sending, or type instead."
        )
    return result.text, None, warning


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []
#: Default reply language. Must be a key of LANGUAGE_CHOICES.
DEFAULT_TARGET = "hi"

if "target_language" not in st.session_state:
    st.session_state.target_language = DEFAULT_TARGET
elif st.session_state.target_language not in LANGUAGE_CHOICES:
    # A session started before the language list changed would otherwise crash
    # the selectbox with "not in list". Fall back rather than break the app.
    st.session_state.target_language = DEFAULT_TARGET
if "pending" not in st.session_state:
    st.session_state.pending = None


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")

    codes = list(LANGUAGE_CHOICES)
    st.session_state.target_language = st.selectbox(
        "Reply language",
        options=codes,
        index=codes.index(st.session_state.target_language),
        format_func=lambda c: f"{LANGUAGE_CHOICES[c]} ({c})",
        help="Module 5 translates every bot reply into this language.",
    )

    speak_replies = st.toggle(
        "Speak replies",
        value=True,
        help="Module 6. Needs an internet connection.",
    )

    # Warn up front rather than after the user sends a message and gets silence.
    tts_mod, _tts_err = load_module("text_to_speech")
    if speak_replies and tts_mod and not tts_mod.can_speak(st.session_state.target_language):
        st.caption(
            f":orange[:material/volume_off:] "
            f"{LANGUAGE_CHOICES[st.session_state.target_language]} is text-only — "
            "no voice available."
        )
    show_trace = st.toggle(
        "Show pipeline details",
        value=True,
        help="Reveal the detected language and the English pivot text.",
    )

    st.divider()
    st.subheader("Module status")
    with st.container(border=True):
        for key, label in MODULES.items():
            _, load_error = load_module(key)
            if load_error:
                st.markdown(f":red[:material/cancel:] {label}")
            else:
                st.markdown(f":green[:material/check_circle:] {label}")
    st.caption("A red module degrades one feature; the rest of the app keeps working.")

    st.divider()
    if st.button("Clear conversation", width="stretch", icon=":material/delete:"):
        st.session_state.history = []
        st.rerun()


# --------------------------------------------------------------------------
# Main pane
# --------------------------------------------------------------------------

st.title("Translation chatbot")
st.caption(
    "Type in any supported language, or speak (most reliable in Hindi and "
    "Tamil). The bot thinks in English and answers in "
    f"**{LANGUAGE_CHOICES[st.session_state.target_language]}**."
)

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn.get("caption"):
            st.caption(turn["caption"])
        if turn.get("audio"):
            st.audio(turn["audio"], format="audio/mp3")
        if turn.get("trace") and show_trace:
            trace = turn["trace"]
            with st.expander("Pipeline", icon=":material/route:"):
                st.markdown(
                    f"**Detected** — {trace['detected_name']} (`{trace['detected']}`)\n\n"
                    f"**English pivot, in** — {trace['english_in']}\n\n"
                    f"**English pivot, out** — {trace['english_out']}"
                )

# Suggestion chips, shown only on an empty conversation.
if not st.session_state.history:
    picked = st.pills("Try one:", list(SUGGESTIONS), label_visibility="collapsed")
    if picked:
        st.session_state.pending = (SUGGESTIONS[picked], None)
        st.rerun()

# --------------------------------------------------------------------------
# Input: text, an uploaded audio file, or a live recording -- one widget.
# accept_audio records at 16 kHz, which is exactly what Whisper wants.
# --------------------------------------------------------------------------
prompt = st.chat_input(
    "Type a message, attach audio, or record…",
    accept_file=True,
    file_type=AUDIO_TYPES,
    accept_audio=True,
    submit_mode="disable",
)

if prompt:
    audio_file = prompt.audio or (prompt.files[0] if prompt.files else None)
    if audio_file is not None:
        with st.spinner("Transcribing…"):
            text, stt_error, stt_warning = transcribe_upload(audio_file)
        if stt_error:
            st.error(stt_error)
        else:
            caption = "transcribed from audio"
            if stt_warning:
                caption = f"{caption} — ⚠️ {stt_warning}"
            st.session_state.pending = (text, caption)
    elif prompt.text.strip():
        st.session_state.pending = (prompt.text, None)

# --------------------------------------------------------------------------
# Handle whichever input path produced a message.
# --------------------------------------------------------------------------
if st.session_state.pending:
    user_text, caption = st.session_state.pending
    st.session_state.pending = None

    st.session_state.history.append(
        {"role": "user", "content": user_text, "caption": caption}
    )
    with st.chat_message("user"):
        st.markdown(user_text)
        if caption:
            st.caption(caption)

    with st.chat_message("assistant"):
        with st.spinner("Translating…"):
            trace = run_pipeline(
                user_text, st.session_state.target_language, speak_replies
            )

        if trace["error"]:
            st.error(trace["error"], icon=":material/translate:")
            for warning in trace["warnings"]:
                st.caption(warning)
            st.session_state.history.append(
                {"role": "assistant", "content": f":red[{trace['error']}]"}
            )
        else:
            st.markdown(trace["reply"])
            for warning in trace["warnings"]:
                st.caption(f":orange[:material/warning:] {warning}")
            if trace["audio"]:
                st.audio(trace["audio"], format="audio/mp3")

            st.session_state.history.append(
                {
                    "role": "assistant",
                    "content": trace["reply"],
                    "audio": trace["audio"],
                    "trace": trace,
                }
            )
