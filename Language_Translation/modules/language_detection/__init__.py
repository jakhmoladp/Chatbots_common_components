"""Module 3 -- Language detection. Public surface."""

from .detector import ERROR_NOT_IN_LIST, DetectionResult, detect_language, is_available
from .languages import SUPPORTED_LANGUAGES, is_supported, language_name, supported_codes

__all__ = [
    "detect_language",
    "is_available",
    "DetectionResult",
    "ERROR_NOT_IN_LIST",
    "SUPPORTED_LANGUAGES",
    "supported_codes",
    "is_supported",
    "language_name",
]
