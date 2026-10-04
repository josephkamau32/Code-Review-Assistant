"""
Redaction utility for scrubbing secrets and PII from code diffs before
sending them to external LLM / embedding APIs (PRIV-02).

Design decisions
────────────────
* Regex-only, no heavy dependencies (detect-secrets, etc.).  Catches the
  common high-confidence patterns listed below; will NOT catch everything
  (see PRIVACY.md for an honest limitations section).
* Replacements are same-line, same-line-count – the diff structure is
  preserved so downstream line-number validation (LLM-04) is unaffected.
* Never logs the actual secret value.  The returned ``RedactionReport``
  contains only counts and pattern labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

# ─── Placeholder tokens ──────────────────────────────────────────────────────
REDACTED_SECRET = "[REDACTED: real secret value removed]"
REDACTED_EMAIL = "[REDACTED: email address removed]"

# ─── Pattern registry ────────────────────────────────────────────────────────
# Each entry is (label, compiled regex).
# Ordering matters: more-specific patterns first, generic catch-all last.
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # ── Provider-specific API key prefixes ────────────────────────────────
    # AWS Access Key IDs (always 20-char, uppercase, starting AKIA)
    (
        "aws_access_key",
        re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    # Google / Gemini API keys (AIza… and AQ.Ab… forms)
    (
        "google_api_key",
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    ),
    (
        "google_api_key_alt",
        re.compile(r"AQ[0-9A-Za-z]{2}Ab[0-9A-Za-z\-_]{30,}"),
    ),
    # GitHub tokens: classic PAT, OAuth, fine-grained
    (
        "github_token",
        re.compile(r"(?:ghp_|gho_|github_pat_)[0-9A-Za-z_]{20,}"),
    ),
    # OpenAI-style "sk-" prefixed secret keys (at least 20 chars after prefix)
    (
        "openai_style_key",
        re.compile(r"sk-[0-9A-Za-z]{20,}"),
    ),
    # Slack tokens (xoxb-, xoxp-)
    (
        "slack_token",
        re.compile(r"xox[bp]-[0-9A-Za-z\-]{20,}"),
    ),
    # ── Generic assignment patterns ───────────────────────────────────────
    # Matches:  SOMETHING_KEY = "value"  /  password = 'value'  etc.
    # Case-insensitive variable name; value in single or double quotes.
    (
        "generic_secret_assignment",
        re.compile(
            r"""(?i)"""  # case-insensitive
            r"""(\b\w*(?:SECRET|TOKEN|KEY|PASSWORD|PASSWD|CREDENTIAL|AUTH)"""
            r"""\w*\b"""  # variable name
            r"""\s*[:=]\s*)"""  # assignment operator
            r"""(["'])"""  # opening quote (group 2)
            r"""([^"']{4,})"""  # value – at least 4 chars (group 3)
            r"""(\2)""",  # closing quote must match opener
        ),
    ),
    # ── Email addresses ───────────────────────────────────────────────────
    (
        "email_address",
        re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}"),
    ),
]


@dataclass
class RedactionReport:
    """Summary of what was redacted – never stores the actual secret."""

    total_redactions: int = 0
    redactions_by_label: dict = field(default_factory=dict)

    def record(self, label: str) -> None:
        self.total_redactions += 1
        self.redactions_by_label[label] = self.redactions_by_label.get(label, 0) + 1


def redact_text(text: str) -> Tuple[str, RedactionReport]:
    """Return *(redacted_text, report)*.

    Guarantees
    ──────────
    * Same number of ``\\n`` newlines  → same line count.
    * No lines deleted or inserted   → line numbers stay meaningful.
    * Placeholder tokens clearly mark where redaction happened.
    """
    report = RedactionReport()

    for label, pattern in _PATTERNS:
        if label == "generic_secret_assignment":
            # Special handling: only mask the quoted value, not the key name.
            def _replace_assignment(m: re.Match) -> str:
                report.record(label)
                # Keep prefix (variable + operator + opening quote), replace
                # value with placeholder, keep closing quote.
                return f"{m.group(1)}{m.group(2)}{REDACTED_SECRET}{m.group(4)}"

            text = pattern.sub(_replace_assignment, text)
        elif label == "email_address":

            def _replace_email(m: re.Match) -> str:
                report.record(label)
                return REDACTED_EMAIL

            text = pattern.sub(_replace_email, text)
        else:

            def _replace_secret(m: re.Match, _label: str = label) -> str:
                report.record(_label)
                return REDACTED_SECRET

            text = pattern.sub(_replace_secret, text)

    return text, report
