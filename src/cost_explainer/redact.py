"""Strip account IDs and secret-looking text before anything is sent to an LLM."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # ARNs (contain account IDs and resource names)
    (re.compile(r"arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:\d{12}:[^\s\"',]+"), "[REDACTED_ARN]"),
    # AWS access key IDs
    (re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{16}\b"), "[REDACTED_KEY]"),
    # Authorization headers: redact the whole value (e.g. "Bearer xyz", "Basic xyz")
    (re.compile(r"(?i)\bauthorization\b(\s*[:=]\s*)[^\r\n]+"), r"Authorization\1[REDACTED]"),
    # "Bearer <token>"
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    # key=value / key: value style secrets
    (
        re.compile(
            r"(?i)\b(secret|token|password|passwd|api[_-]?key)\b"
            r"(\s*[:=]\s*|\s+)[^\s\"',;]+"
        ),
        r"\1\2[REDACTED]",
    ),
    # Google / Anthropic / OpenAI / Slack / GitHub style keys
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_KEY]"),
    # Slack webhook URLs
    (re.compile(r"https://hooks\.slack\.com/\S+"), "[REDACTED_WEBHOOK]"),
    # 12-digit account IDs (optionally dashed 4-4-4)
    (re.compile(r"(?<!\d)\d{4}-\d{4}-\d{4}(?!\d)"), "[REDACTED_ACCOUNT]"),
    (re.compile(r"(?<![\d.])\d{12}(?![\d.])"), "[REDACTED_ACCOUNT]"),
    # Long high-entropy-looking strings (40+ chars of base64/hex-ish)
    (re.compile(r"\b[A-Za-z0-9/+=_-]{40,}\b"), "[REDACTED_SECRET]"),
]


def redact(text: str) -> str:
    """Return ``text`` with account IDs and secret-looking strings replaced by placeholders."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
