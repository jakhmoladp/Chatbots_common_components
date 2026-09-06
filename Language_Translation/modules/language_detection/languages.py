"""The authoritative list of language codes this module is allowed to return.

Scope: English plus the Indian languages the whole pipeline can handle.

This list is owned by the language-detection module. Other modules keep their
own copies on purpose -- see docs/MODULE_3_LANGUAGE_DETECTION.md, section
"Why the language list is duplicated".

Codes are ISO 639-1.
"""

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "bn": "Bengali",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "ne": "Nepali",
    "or": "Odia",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
}

# langdetect emits a few codes that are really regional variants of a code we
# already support. Fold them in rather than rejecting them.
CODE_ALIASES: dict[str, str] = {
    "zh-cn": "zh",
    "zh-tw": "zh",
    "pt-br": "pt",
}

# --------------------------------------------------------------------------
# Script detection
#
# Most Indian languages are written in a script used by exactly one of them.
# Where that holds, the script *is* the answer, and it is far more reliable
# than langdetect's character n-grams -- especially on short input, which is
# where langdetect falls apart.
#
# Ranges are the Unicode blocks for each script.
# --------------------------------------------------------------------------

SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "Devanagari": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "Bengali": ((0x0980, 0x09FF),),
    "Gurmukhi": ((0x0A00, 0x0A7F),),
    "Gujarati": ((0x0A80, 0x0AFF),),
    "Odia": ((0x0B00, 0x0B7F),),
    "Tamil": ((0x0B80, 0x0BFF),),
    "Telugu": ((0x0C00, 0x0C7F),),
    "Kannada": ((0x0C80, 0x0CFF),),
    "Malayalam": ((0x0D00, 0x0D7F),),
    "Arabic": ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)),
    "Latin": ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)),
}

#: Scripts used by exactly one language we support. Detecting the script is
#: then a complete answer, with no need to consult langdetect at all.
UNAMBIGUOUS_SCRIPTS: dict[str, str] = {
    "Gujarati": "gu",
    "Gurmukhi": "pa",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Odia": "or",
    "Tamil": "ta",
    "Telugu": "te",
}

#: Scripts shared by more than one language, where at least one of the sharers
#: is a language we do NOT support. The script narrows the field, but langdetect
#: still has to confirm -- otherwise Arabic text would be reported as Urdu, and
#: French as English, purely because they happen to share a writing system.
#:
#: Devanagari carries Hindi, Marathi and Nepali (and Sanskrit, unsupported).
#: Bengali script carries Bengali and Assamese (unsupported). Arabic script
#: carries Urdu plus Arabic, Persian and Sindhi, none of which we support.
#:
#: Latin is deliberately absent. Latin-script text must go through the
#: unconstrained langdetect path so that French, Spanish and the rest are
#: correctly rejected with 'Language not in list' rather than being forced
#: into the only Latin-script language we support.
AMBIGUOUS_SCRIPTS: dict[str, tuple[str, ...]] = {
    "Devanagari": ("hi", "mr", "ne"),
    "Bengali": ("bn",),
    "Arabic": ("ur",),
}


def is_supported(code: str) -> bool:
    """True if ``code`` is in the supported list."""
    return code in SUPPORTED_LANGUAGES


def language_name(code: str) -> str:
    """Human-readable name for a supported code, or the code itself."""
    return SUPPORTED_LANGUAGES.get(code, code)


def supported_codes() -> list[str]:
    """Sorted list of every code this module can return."""
    return sorted(SUPPORTED_LANGUAGES)


def dominant_script(text: str) -> tuple[str | None, float]:
    """Return the script most of ``text`` is written in, and its share.

    Only letters are counted -- digits, spaces and punctuation are shared
    across scripts and would dilute the signal. Returns (None, 0.0) when the
    text has no letters from any script we know.
    """
    counts: dict[str, int] = {}
    total = 0

    for char in text:
        point = ord(char)
        for script, ranges in SCRIPT_RANGES.items():
            if any(low <= point <= high for low, high in ranges):
                counts[script] = counts.get(script, 0) + 1
                total += 1
                break

    if not total:
        return None, 0.0

    best = max(counts, key=counts.__getitem__)
    return best, counts[best] / total
