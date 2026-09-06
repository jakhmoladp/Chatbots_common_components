# PII_Handling

Detects and redacts personally identifiable information (PII) in free text
using [Microsoft Presidio](https://microsoft.github.io/presidio/). Built as a
single importable function (`redact_pii`) so other scripts and services can
call it directly rather than shelling out or duplicating detection logic.

## Features

- Detects the full range of entity types supported by Presidio's default
  recognizers (e.g. `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`,
  `LOCATION`, `URL`, `IP_ADDRESS`, `IBAN_CODE`, and more).
- Redacts detected values using a configurable Presidio operator (defaults to
  replacing each match with `[REDACTED]`).
- Returns per-entity-type counts alongside the redacted text — never the
  original sensitive values — so results are always safe to log or store.
- Thread-safe, lazy-initialized Presidio engines: the (expensive) analyzer
  and anonymizer are built once per process and reused across calls.
- Input validation and a single custom exception (`PiiRedactionError`) so
  callers don't need to know Presidio's internal exception types.

## Requirements

- Python 3.9+
- [`presidio-analyzer`](https://pypi.org/project/presidio-analyzer/)
- [`presidio-anonymizer`](https://pypi.org/project/presidio-anonymizer/)
- A spaCy language model used by Presidio's NLP engine (default: `en_core_web_lg`)

Install:

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```

## Usage

### As a library

```python
from pii_handling import redact_pii, PiiRedactionError

try:
    result = redact_pii("Contact John Doe at john.doe@example.com.")
except PiiRedactionError as exc:
    # analysis/anonymization failed (e.g. Presidio internals raised)
    ...
else:
    print(result.text)            # "Contact [REDACTED] at [REDACTED]."
    print(result.entity_counts)   # {'PERSON': 1, 'EMAIL_ADDRESS': 1}
    print(result.entity_count)    # 2
```

### As a script

```bash
python pii_handling.py
```

Runs a built-in sample string through `redact_pii` and prints the redacted
text plus a summary of detected entity counts.

## API

### `redact_pii(text, *, entities=None, language="en", score_threshold=0.35, redaction_value="[REDACTED]", operators=None) -> RedactionResult`

| Parameter         | Type                              | Default          | Description |
|-------------------|------------------------------------|------------------|-------------|
| `text`            | `str`                              | required         | Text to scan. Must be non-empty and at most 100,000 characters. |
| `entities`        | `Sequence[str] \| None`            | `None` (all)     | Allow-list of entity types to detect, e.g. `["EMAIL_ADDRESS", "PHONE_NUMBER"]`. |
| `language`        | `str`                               | `"en"`           | ISO 639-1 language code passed to the analyzer. |
| `score_threshold` | `float`                             | `0.35`           | Minimum confidence score required for a detection to be redacted. |
| `redaction_value` | `str`                               | `"[REDACTED]"`   | Placeholder text used by the default replace operator. Ignored if `operators` is supplied. |
| `operators`       | `dict[str, OperatorConfig] \| None` | `None`           | Custom Presidio operator configuration keyed by entity type (use `"DEFAULT"` as a catch-all) — e.g. to mask or hash instead of replace. |

Returns a `RedactionResult`:

| Field           | Type            | Description |
|-----------------|-----------------|-------------|
| `text`          | `str`           | The redacted text. |
| `entity_counts` | `dict[str,int]` | Count of detections per entity type. Never contains the original values. |
| `entity_count`  | `int` (property)| Total number of entities redacted. |

Raises:

- `TypeError` — `text` is not a string.
- `ValueError` — `text` is empty/whitespace-only or exceeds the maximum length.
- `PiiRedactionError` — Presidio analysis, anonymization, or engine
  initialization failed.

## Custom redaction operators

Pass `operators` to control how each entity type is transformed, e.g. to
mask a credit card number instead of replacing it wholesale:

```python
from presidio_anonymizer.entities import OperatorConfig

result = redact_pii(
    text,
    operators={
        "CREDIT_CARD": OperatorConfig("mask", {
            "type": "mask", "masking_char": "*", "chars_to_mask": 12, "from_end": False,
        }),
        "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
    },
)
```

See the [Presidio anonymizer operator docs](https://microsoft.github.io/presidio/anonymizer/)
for the full list of supported operators (`replace`, `mask`, `hash`,
`redact`, `encrypt`, custom lambdas, etc.).

## Logging

The module logs via the standard `logging` module under the
`pii_handling` logger name. It never logs the original detected values —
only entity types and counts (e.g. `Redacted 3 PII entities:
{'EMAIL_ADDRESS': 1, 'PHONE_NUMBER': 2}`). As a library, it does not call
`logging.basicConfig()` on import; configure logging in your own
application. The `__main__` block does call `basicConfig()` for convenience
when running the file directly as a demo.

## Notes

- Presidio's default recognizers rely on pattern/context matching and a
  spaCy NER model; detection is best-effort and not guaranteed to catch
  every PII instance or avoid false positives. Tune `score_threshold` and
  `entities` for your use case, and treat this as a defense-in-depth layer
  rather than a sole compliance control.
- Engine initialization (loading the spaCy model and recognizer registry)
  happens on first call and can take a few seconds; subsequent calls reuse
  the same in-process engines.
