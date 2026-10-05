# Code Review Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![CI](https://github.com/josephkamau32/Code-Review-Assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/josephkamau32/Code-Review-Assistant/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/josephkamau32/Code-Review-Assistant/branch/main/graph/badge.svg)](https://codecov.io/gh/josephkamau32/Code-Review-Assistant)

A context-aware code review assistant that uses Retrieval-Augmented Generation (RAG) to provide consistent code reviews based on historical review patterns and customizable style guides. It integrates seamlessly with GitHub webhooks to automate pull request reviews.

![Demo Placeholder - Add a 10s GIF here](docs/assets/demo.gif)

[View Live Demo](https://demo.your-domain.com) *(Request access via issues)*

## Key Features

- **Contextual Reviews**: Uses RAG to analyze code changes and provide suggestions based on past reviews.
- **Continuous Learning**: Ingests historical PRs to maintain consistency across your team's specific coding standards.
- **Customizable Guidelines**: Supports custom style guides and rules across multiple programming languages (Python, TS, Go, etc.).
- **GitHub Integration**: Handles PR fetching, webhook verification, and automatic comment posting.
- **Container Deployment**: Includes Docker support with a FastAPI backend and ChromaDB vector store.

## Documentation

- [Architecture & Design](docs/architecture.md)
- [Quick Start & Configuration](docs/configuration.md)
- [API Documentation](docs/api.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Privacy & Data Flow](PRIVACY.md)
- [Testing](docs/testing.md)
- [Troubleshooting](docs/troubleshooting.md)

## Quick Start

```bash
git clone https://github.com/your-username/code-review-assistant.git
cd code-review-assistant
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GITHUB_TOKEN and OPENAI_API_KEY
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

> [!NOTE]
> **Vector Store Collections & Re-Ingestion:** ChromaDB collections are namespaced by embedding model and vector dimension (e.g. `code_reviews_gemini_embedding_001_768d`) to ensure embedding compatibility. Changing `EMBEDDING_PROVIDER`, embedding models, or `EMBEDDING_DIMENSIONS` creates a new distinct collection and requires re-ingesting historical reviews.

## Running Tests

All unit tests are hermetic: they run completely offline without external network calls, external service dependencies, or real API keys.

```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Run hermetic test suite (default - safe for CI without secrets):
pytest

# Run hermetic tests with coverage report:
pytest --cov=src --cov-report=term-missing

# Run integration tests (tests vector DB, pipeline integration, and schemas):
pytest -m integration

# Run end-to-end tests (requires live external services and credentials):
pytest -m e2e
```

## Evaluation Results (LLM-02)

The RAG pipeline was benchmarked against a 20-case golden dataset (12 single-bug
cases across 5 categories, 4 clean-code cases, 4 deliberately subtle bugs) using
the real Gemini API (`gemini-3.5-flash-lite`). Full methodology: [eval/README.md](eval/README.md).

| Metric | Run 1 | Run 2 |
|---|---|---|
| Overall defect recall | 93.8% (15/16) | 93.8% (15/16) |
| Recall on obvious bugs | 100% (12/12) | 100% (12/12) |
| Recall on subtle bugs | 75% (3/4) | 75% (3/4) |
| Line accuracy (±1 line) | 86.7% | 86.7% |
| Clean-code false positive rate | 75% (3/4 cases) | 75% (3/4 cases) |
| Overall precision | 62.5% | 57.7% |

**Two things worth noting from manual review of the raw output, not just the scored metrics:**

- The one consistent "miss" (`case_20`, a TOCTOU race condition) was actually
  caught correctly by the model in both runs — it diagnosed the exact bug with
  the exact fix, but categorized it as `best_practice` rather than our ground
  truth's `bug`. Since the harness requires an exact category match, this
  surfaced as a miss. Real-world recall on this dataset is closer to 16/16;
  this is a known limitation of strict category-matching in the scorer, not a
  model failure — see `eval/scorer.py`'s documented matching rules.
- The "false positives" on clean code are not hallucinated bugs — they're
  legitimate, if minor, observations (unbounded cache growth, a missing
  `min_length` constraint, a non-reentrant lock choice). The model behaves
  like a thorough, somewhat nitpicky reviewer rather than one that invents
  problems. This is a real trade-off worth being aware of when tuning
  prompts or deciding how noisy you want review output to be.

Recall was stable across two independent runs; false-positive counts and
exact suggestion wording varied slightly, consistent with normal LLM
non-determinism at low temperature rather than a flaky harness.

## Engineering Decisions & Trade-offs

- **Gemini as Default LLM:** We chose Google Gemini (`gemini-3.5-flash-lite`) as the out-of-the-box default to leverage its generous free-tier API quotas, ensuring portfolio reviewers and contributors can run the service and evaluation suite at zero cost without entering billing details, while retaining OpenAI as a hot-swappable alternative via our provider interface.
- **Strict Category-Matching in Evaluation:** The eval harness requires exact defect category matches (`bug`, `security`, `performance`, `style`, `best_practice`) alongside line proximity to prevent vague or speculative observations from inflating recall. The trade-off is false-negative rigidity: in benchmark runs, `case_20` (a TOCTOU race condition) was diagnosed with the exact code fix by Gemini, but scored as a miss purely because the model labeled it `best_practice` rather than `bug`.
- **Regex-Based Redaction Pre-filter:** Secret and PII redaction runs as an inline pre-filter using bounded regular expressions rather than heavier scanners like `detect-secrets`. This avoids heavy native dependencies and guarantees sub-millisecond synchronous execution on incoming webhook diffs, but trades away entropy-based detection of unstructured, unpatterned high-entropy strings.
- **Current Architectural Limitation:** Code reviews analyze incoming diffs file-by-file without whole-repository AST indexing or cross-file call graphs. A change that renames an exported symbol, alters type contracts, or modifies function arity across file boundaries appears syntactically sound in isolation, leaving cross-module breakage undetected.

## Contributing

We welcome contributions! Please refer to the guidelines in our issues and discussions. Follow PEP 8 and ensure tests pass (`pytest --cov`).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
