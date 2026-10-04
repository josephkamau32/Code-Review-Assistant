# Privacy & Data Flow

> **Last updated:** October 2026
> **Status:** Factual description of current behaviour — not legal advice.

## What data leaves this system

When a pull request is reviewed, the following data is sent to **external cloud APIs**:

| Data                      | Destination                          | Purpose                         |
|---------------------------|--------------------------------------|---------------------------------|
| Code diff (redacted)      | Embedding API (Gemini or OpenAI)     | Generate vector for similarity search |
| Code diff (redacted) + historical review context | LLM API (Gemini or OpenAI) | Generate code review suggestions |

**Default provider:** Google Gemini (`generativelanguage.googleapis.com`).
If configured, OpenAI (`api.openai.com`) can be used instead.

Both providers are US-based cloud services.  Data in transit is TLS-encrypted, but once received it is subject to the provider's own data handling and retention policies.

### What stays local

- The **ChromaDB vector database** storing historical review embeddings runs locally (on disk, not a cloud service).
- **GitHub metadata** (PR numbers, file paths, branch names) is processed locally and posted back to GitHub via the GitHub API.

## Secret & PII redaction

A regex-based redaction layer (`src/utils/redaction.py`) scrubs the following from code diffs **before** they are sent to any external API:

- **Provider-specific API keys:** AWS (`AKIA…`), Google/Gemini (`AIza…`), GitHub tokens (`ghp_`, `gho_`, `github_pat_`), OpenAI-style (`sk-…`), Slack (`xoxb-`, `xoxp-`)
- **Generic secret assignments:** Variables containing `KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `CREDENTIAL`, or `AUTH` in their name, with a quoted string value
- **Email addresses** (simple regex match)

Matches are replaced with `[REDACTED: real secret value removed]` or `[REDACTED: email address removed]`.  Line structure (line count, line boundaries) is preserved so that line-number validation still works correctly.

### What redaction does NOT do

Be clear about this — the redaction layer is **not** a complete data-loss-prevention system:

- **Regex-only.** It matches known patterns. Creatively formatted, obfuscated, or non-standard secrets will be missed.
- **No entropy analysis.** High-entropy random strings that don't match a known prefix pattern won't be caught.
- **No historical scanning.** Reviews already ingested into the vector database (before this redaction layer existed) are not retroactively scrubbed.
- **Not a substitute for secret hygiene.** The best defence is not committing secrets to version control in the first place.  Use `.gitignore`, secret managers, and pre-commit hooks (e.g. `detect-secrets`).
- **Code structure is still sent.** Even after redaction, the code diff itself — variable names, logic, architecture — is transmitted to the LLM provider.  If the code itself is confidential intellectual property, external API calls may be unacceptable regardless of secret redaction.

## Local / EU-hosted inference

**This does not exist yet.**  There is currently no option to run the LLM or embedding models locally (e.g. via Ollama, vLLM, or a self-hosted API).  All inference requires calls to US-based cloud providers.

Adding a local/EU-hosted inference option is a planned roadmap item, but it is not implemented.  Until then, teams with strict data-sovereignty requirements should evaluate whether sending code diffs to US cloud APIs is acceptable under their policies.

## Summary

This tool sends code diffs to cloud LLM APIs for review generation.  It redacts common secret patterns before doing so, but regex-based redaction has inherent limitations.  No local inference option exists yet.  This document describes what the system actually does — not what we wish it did.
