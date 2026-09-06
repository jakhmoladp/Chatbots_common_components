"""PII detection and redaction utility built on Microsoft Presidio.

Exposes `redact_pii` as the single entry point for other scripts/services to
import and call. Presidio engines are initialized once per process (lazy,
thread-safe singletons) since construction is expensive. Raw PII values are
never logged — only entity types and counts.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, Sequence

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

__all__ = [
    "PiiRedactionError",
    "RedactionResult",
    "redact_pii",
]

logger = logging.getLogger(__name__)

_DEFAULT_LANGUAGE = "en"
_DEFAULT_SCORE_THRESHOLD = 0.35
_MAX_TEXT_LENGTH = 100_000  # guard against pathological/oversized inputs

# Module-level singletons: Presidio engine construction loads NLP models and
# recognizer registries, so we build each engine at most once per process.
_engine_lock = threading.Lock()
_analyzer_engine: Optional[AnalyzerEngine] = None
_anonymizer_engine: Optional[AnonymizerEngine] = None


class PiiRedactionError(Exception):
    """Raised when PII detection or anonymization fails."""


@dataclass(frozen=True)
class RedactionResult:
    """Outcome of a redaction call.

    `entity_counts` intentionally holds only entity types and counts, never
    the original sensitive values, so it is always safe to log or store.
    """

    text: str
    entity_counts: dict[str, int] = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return sum(self.entity_counts.values())


def _get_analyzer() -> AnalyzerEngine:
    """Return the process-wide AnalyzerEngine, creating it on first use.

    Uses double-checked locking: the first (lock-free) check avoids taking
    the lock on the common path once the engine already exists, and the
    second check (inside the lock) prevents two threads from racing to
    build it simultaneously.
    """
    global _analyzer_engine
    if _analyzer_engine is None:
        with _engine_lock:
            if _analyzer_engine is None:
                logger.info("Initializing Presidio AnalyzerEngine")
                try:
                    _analyzer_engine = AnalyzerEngine()
                except Exception as exc:
                    logger.exception("Failed to initialize Presidio AnalyzerEngine")
                    raise PiiRedactionError("Failed to initialize PII analyzer") from exc
    return _analyzer_engine


def _get_anonymizer() -> AnonymizerEngine:
    """Return the process-wide AnonymizerEngine, creating it on first use.

    Same double-checked locking pattern as `_get_analyzer`.
    """
    global _anonymizer_engine
    if _anonymizer_engine is None:
        with _engine_lock:
            if _anonymizer_engine is None:
                logger.info("Initializing Presidio AnonymizerEngine")
                try:
                    _anonymizer_engine = AnonymizerEngine()
                except Exception as exc:
                    logger.exception("Failed to initialize Presidio AnonymizerEngine")
                    raise PiiRedactionError("Failed to initialize PII anonymizer") from exc
    return _anonymizer_engine


def redact_pii(
    text: str,
    *,
    entities: Optional[Sequence[str]] = None,
    language: str = _DEFAULT_LANGUAGE,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
    redaction_value: str = "[REDACTED]",
    operators: Optional[dict[str, OperatorConfig]] = None,
) -> RedactionResult:
    """Detect and redact PII in `text` using Microsoft Presidio.

    Thread-safe and safe to call repeatedly from other applications: the
    underlying Presidio engines are created once per process and reused.

    Args:
        text: Text to scan. Must be a non-empty string, at most
            `_MAX_TEXT_LENGTH` characters.
        entities: Optional allow-list of entity types to detect (e.g.
            ["EMAIL_ADDRESS", "PHONE_NUMBER"]). Defaults to all entities
            supported by the active recognizers.
        language: ISO 639-1 language code for analysis.
        score_threshold: Minimum confidence score required for a detection
            to be redacted.
        redaction_value: Placeholder used by the default "replace" operator.
            Ignored if `operators` is supplied.
        operators: Optional custom Presidio operator configuration keyed by
            entity type (use "DEFAULT" as a catch-all).

    Returns:
        RedactionResult with the redacted text and per-entity-type counts.
        The original sensitive values are never included in the result's
        metadata.

    Raises:
        TypeError: If `text` is not a string.
        ValueError: If `text` is empty/whitespace-only or too long.
        PiiRedactionError: If Presidio analysis or anonymization fails.
    """
    # Defensive runtime checks: the type hint is `str`, but callers from
    # untyped code (or values deserialized from JSON/CLI args) can still
    # pass the wrong type or an unusable value, so we validate explicitly
    # rather than trusting the annotation.
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    if not text.strip():
        raise ValueError("text must not be empty or whitespace-only")
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(
            f"text length {len(text)} exceeds maximum supported length {_MAX_TEXT_LENGTH}"
        )

    analyzer = _get_analyzer()

    # Step 1: detect PII spans. `entities=None` tells Presidio to check
    # against every recognizer it has registered rather than a subset.
    try:
        results: list[RecognizerResult] = analyzer.analyze(
            text=text,
            entities=list(entities) if entities else None,
            language=language,
            score_threshold=score_threshold,
        )
    except Exception as exc:
        # Wrap in PiiRedactionError so callers only need to handle one
        # exception type regardless of which Presidio internals failed.
        logger.exception(
            "PII analysis failed (language=%s, entities=%s)",
            language,
            list(entities) if entities else "ALL",
        )
        raise PiiRedactionError("PII analysis failed") from exc

    if not results:
        # Nothing detected: skip anonymizer setup/call entirely and return
        # the original text untouched.
        logger.debug("No PII entities detected (language=%s)", language)
        return RedactionResult(text=text, entity_counts={})

    # Tally detections per entity type for safe-to-log metadata; never
    # capture the matched substrings themselves.
    entity_counts: dict[str, int] = {}
    for result in results:
        entity_counts[result.entity_type] = entity_counts.get(result.entity_type, 0) + 1

    # Fall back to a single catch-all "replace" operator unless the caller
    # supplied its own per-entity-type operator configuration.
    resolved_operators = operators or {
        "DEFAULT": OperatorConfig("replace", {"new_value": redaction_value})
    }

    anonymizer = _get_anonymizer()
    # Step 2: replace each detected span using the resolved operators.
    try:
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=resolved_operators,
        )
    except Exception as exc:
        logger.exception("PII anonymization failed")
        raise PiiRedactionError("PII anonymization failed") from exc

    logger.info("Redacted %d PII entities: %s", sum(entity_counts.values()), entity_counts)

    return RedactionResult(text=anonymized.text, entity_counts=entity_counts)


if __name__ == "__main__":
    # Only configure logging when run as a script; a library should never
    # call basicConfig() on import, since that would override the log
    # configuration of whatever application imports this module.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sample_input = (
        "Hello, my name is John Doe. My email is john.doe@example.com. "
        "You can call me at +1-202-555-0173. "
        "My credit card number is 4111 1111 1111 1111. "
        "I live at 123 Main Street, Springfield."
    )

    outcome = redact_pii(sample_input)
    print(outcome.text)
    print(f"Redacted entities: {outcome.entity_counts}")
