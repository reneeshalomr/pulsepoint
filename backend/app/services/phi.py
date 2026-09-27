"""Regex-based PHI redaction performed before question text is persisted."""

import re

_PATTERNS = [
    # Honorific followed by a likely personal name (including hyphenated names).
    re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]+)?", re.IGNORECASE),
    re.compile(r"\b(?:date of birth|dob)\s*[:#-]?\s*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    re.compile(r"\bMRN\s*[:#-]?\s*[A-Z0-9-]{4,}\b", re.IGNORECASE),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
]


def scrub_phi(text: str) -> tuple[str, bool]:
    """Replace recognized PHI patterns with [REDACTED] and report whether found."""
    scrubbed = text
    detected = False
    for pattern in _PATTERNS:
        scrubbed, count = pattern.subn("[REDACTED]", scrubbed)
        detected = detected or count > 0
    return scrubbed, detected
