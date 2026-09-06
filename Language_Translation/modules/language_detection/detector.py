"""Module 3 -- Language detection.

Input:  text in any language.
Output: an ISO 639-1 code from SUPPORTED_LANGUAGES, or the error code
        'Language not in list'.

Detection runs in two stages: script first, then langdetect. See
docs/MODULE_3_LANGUAGE_DETECTION.md for why that order matters.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from .languages import (
    AMBIGUOUS_SCRIPTS,
    CODE_ALIASES,
    SUPPORTED_LANGUAGES,
    UNAMBIGUOUS_SCRIPTS,
    dominant_script,
    language_name,
)

#: Third-party packages this module needs at call time.
REQUIRED_PACKAGES = ("langdetect",)

#: The exact error code the spec requires. Compare against this constant rather
#: than typing the string literal at call sites.
ERROR_NOT_IN_LIST = "Language not in list"

#: Below this confidence we report the error code instead of guessing. Short
#: inputs ("ok", "123") are the usual cause.
MIN_CONFIDENCE = 0.60

#: A script has to account for at least this share of the letters before we
#: trust it. Mixed-script text (Hindi with English words) falls below it.
MIN_SCRIPT_SHARE = 0.60

#: Confidence reported when a unique script settles the question. Not 1.0,
#: because the script identifies the *writing system* with certainty and the
#: language only by strong convention.
SCRIPT_CONFIDENCE = 0.99


@dataclass(frozen=True)
class DetectionResult:
    """What detect_language returns. Never raises for an unsupported language."""

    ok: bool
    code: str | None = None
    name: str | None = None
    confidence: float = 0.0
    error: str | None = None
    #: What the underlying engine actually guessed, even when unsupported.
    # Useful for logging and for deciding whether to widen the supported list.
    detected_raw: str | None = None
    #: Which stage produced the answer: 'script' or 'langdetect'.
    method: str | None = None

    def __str__(self) -> str:
        if self.ok:
            return (
                f"{self.code} ({self.name}, confidence {self.confidence:.2f}, "
                f"via {self.method})"
            )
        return self.error or ERROR_NOT_IN_LIST


def is_available() -> tuple[bool, str | None]:
    """Report whether this module can actually run.

    Importing the module always succeeds -- the heavy dependency is loaded
    lazily -- so a caller that wants to know whether the module *works* has to
    ask. Uses find_spec rather than a real import so the check stays cheap.

    Returns (True, None) when ready, or (False, reason) when not.
    """
    missing = [p for p in REQUIRED_PACKAGES if importlib.util.find_spec(p) is None]
    if missing:
        return False, (
            f"missing {', '.join(missing)} -- "
            "pip install -r modules/language_detection/requirements.txt"
        )
    return True, None


def _load_detector():
    """Import langdetect lazily so importing this module stays cheap."""
    try:
        from langdetect import DetectorFactory, detect_langs
    except ImportError as exc:  # pragma: no cover - environment problem
        raise RuntimeError(
            "Module 3 needs 'langdetect'. Install it with:\n"
            "    pip install -r modules/language_detection/requirements.txt"
        ) from exc

    # langdetect is non-deterministic unless seeded; the same text would
    # otherwise give different answers across runs.
    DetectorFactory.seed = 0
    return detect_langs


def _by_langdetect(
    text: str, candidates: tuple[str, ...] | None, min_confidence: float
) -> DetectionResult:
    """Second stage. ``candidates`` restricts the answer when the script is known."""
    detect_langs = _load_detector()

    try:
        ranked = detect_langs(text)
    except Exception:
        # langdetect raises LangDetectException on input with no usable
        # features (digits, punctuation, emoji only).
        return DetectionResult(ok=False, error=ERROR_NOT_IN_LIST, method="langdetect")

    if not ranked:
        return DetectionResult(ok=False, error=ERROR_NOT_IN_LIST, method="langdetect")

    if candidates:
        # The script says the answer should be one of these. Take the
        # best-ranked candidate rather than langdetect's global winner, which
        # may be a language written in a completely different script.
        for entry in ranked:
            code = CODE_ALIASES.get(entry.lang.lower(), entry.lang.lower())
            if code in candidates:
                return DetectionResult(
                    ok=True,
                    code=code,
                    name=language_name(code),
                    confidence=float(entry.prob),
                    detected_raw=entry.lang.lower(),
                    method="script+langdetect",
                )

        # No candidate appeared at all: the text is in a script one of our
        # languages uses, but is some *other* language that shares it --
        # Arabic or Persian in the Arabic script, say. Rejecting is the whole
        # point. Forcing it to the single candidate here would silently
        # mistranslate Arabic as Urdu.
        return DetectionResult(
            ok=False,
            error=ERROR_NOT_IN_LIST,
            confidence=float(ranked[0].prob),
            detected_raw=ranked[0].lang.lower(),
            method="script+langdetect",
        )

    best = ranked[0]
    raw_code = best.lang.lower()
    code = CODE_ALIASES.get(raw_code, raw_code)
    confidence = float(best.prob)

    if code not in SUPPORTED_LANGUAGES or confidence < min_confidence:
        return DetectionResult(
            ok=False,
            error=ERROR_NOT_IN_LIST,
            confidence=confidence,
            detected_raw=raw_code,
            method="langdetect",
        )

    return DetectionResult(
        ok=True,
        code=code,
        name=language_name(code),
        confidence=confidence,
        detected_raw=raw_code,
        method="langdetect",
    )


def detect_language(text: str, min_confidence: float = MIN_CONFIDENCE) -> DetectionResult:
    """Detect the language of ``text``.

    Returns a DetectionResult. When the language is recognised but is not in
    SUPPORTED_LANGUAGES, ``ok`` is False and ``error`` is 'Language not in list'.

    >>> detect_language("வணக்கம், எப்படி இருக்கிறீர்கள்?").code
    'ta'
    """
    if not text or not text.strip():
        return DetectionResult(ok=False, error="Empty input")

    # --- Stage 1: script ---------------------------------------------------
    script, share = dominant_script(text)

    if script and share >= MIN_SCRIPT_SHARE:
        # A script only one supported language uses settles it outright.
        if script in UNAMBIGUOUS_SCRIPTS:
            code = UNAMBIGUOUS_SCRIPTS[script]
            return DetectionResult(
                ok=True,
                code=code,
                name=language_name(code),
                confidence=SCRIPT_CONFIDENCE,
                detected_raw=script,
                method="script",
            )

        # A shared script narrows the field; langdetect must still confirm.
        # This branch is taken even when there is only one candidate, because
        # "the only language we support in this script" is not the same claim
        # as "the language this text is written in".
        if script in AMBIGUOUS_SCRIPTS:
            return _by_langdetect(text, AMBIGUOUS_SCRIPTS[script], min_confidence)

    # --- Stage 2: langdetect, unconstrained --------------------------------
    return _by_langdetect(text, None, min_confidence)
