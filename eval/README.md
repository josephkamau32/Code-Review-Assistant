# Code-Review-Assistant Evaluation Harness (LLM-02)

This directory contains the automated evaluation harness for the RAG code review pipeline. It benchmarks review quality against a golden dataset of 20 realistic code changes, measuring defect recall, line-number accuracy, and clean-case false positive rates.

> [!WARNING]
> **API USAGE NOTICE**: When executed without `--mock`, this runner makes **real calls to the Gemini API** (approximately 20 LLM review invocations per run). It operates on free-tier or pay-as-you-go Gemini API keys.
>
> This harness is **strictly opt-in** and completely excluded from default CI and hermetic `pytest` suites.

---

## Benchmark Dataset (`eval/cases/`)

The evaluation suite consists of 20 curated single-file pull request diffs:

| Difficulty Tier | Cases | Purpose & Composition |
| :--- | :--- | :--- |
| **Obvious** | 12 | One planted, unambiguous bug per case across 5 categories: Security (3), Bug (3), Performance (2), Style (2), Best Practice (2). Measures primary recall. |
| **Clean** | 4 | Genuinely clean, non-trivial code (binary search, memoized prime sieve, strict Pydantic model, thread-safe counter). Measures false positive rate. |
| **Subtle** | 4 | Hard-to-detect edge cases (naive vs aware datetime comparison, list mutation during iteration, float equality comparison, TOCTOU directory creation race). Measures model reasoning depth. |

### Case File Format (JSON)

Test cases are stored as individual `.json` files in `eval/cases/`.

**Format Decision (JSON vs YAML):**
JSON was selected over YAML because:
1. **Zero External Dependencies:** Python parses JSON via the standard library (`import json`), avoiding third-party packages like `PyYAML`.
2. **Strict Schema Determinism:** JSON prevents indentation-related parsing ambiguities in multi-line unified diff strings.

Each case defines:
- `id`: Unique identifier (e.g., `case_01_sql_injection`)
- `title`: Human-readable summary
- `difficulty`: `obvious`, `clean`, or `subtle`
- `file_path`: Path of the modified file
- `language`: Target programming language (`python`)
- `diff`: Standard unified diff with verified hunk headers parseable by `extract_valid_lines`
- `ground_truth`: List of planted defect annotations (`line_number`, `category`, `keywords`, `description`). For clean cases, `ground_truth` is `[]`.

---

## Scoring Methodology

### 1. Defect Hit Matching
A ground-truth defect counts as a **HIT** if and only if an LLM suggestion meets all three conditions:
1. **Category Match:** Case-insensitive match on the schema enum (`security`, `bug`, `performance`, `style`, `best_practice`).
2. **Line Tolerance (+/-3 lines):** The suggested line is within +/-3 lines of the intended ground truth line.
   - *Rationale:* Git diff hunks standardly provide 3 lines of context (`-U 3`). LLMs frequently anchor comments to the enclosing function header, `try/except` block, or return line rather than the exact interior statement. A 3-line tolerance captures valid semantic reviews without misclassifying anchoring variance as a failure.
3. **Keyword Substring Match:** The suggestion text contains at least one keyword from the ground truth annotation (case-insensitive substring).

### 2. Line Accuracy Metric (+/-1 line)
Among detected hits, the harness tracks how many suggestions landed within **+/-1 line** of the target line. This isolates exact line precision from loose context anchoring.

### 3. Clean-Case False Positive Rate
For the 4 clean cases, **any** returned suggestion is scored as a false positive. The clean false-positive rate is:
$$\text{Clean FP Rate} = \frac{\text{Clean Cases with } \ge 1 \text{ suggestion}}{\text{Total Clean Cases (4)}}$$

### 4. Extra Suggestions Handling
If the model flags additional observations in a non-clean case that do not match the planted defect, they are **not** automatically penalized as false positives (the model may have identified a valid secondary style or design point). Instead, they are collected and listed under "Extra Suggestions" in the report for manual human inspection.

---

## How to Run

### Option 1: Plumbing Smoke-Test (Mocked, 0 API Calls)
Validate that the evaluation runner, pipeline mechanics, and report generator work end-to-end without spending API credits:

```bash
python eval/run_eval.py --mock
```

### Option 2: Real Gemini Evaluation Run
Run the full benchmark against the real Gemini API:

```bash
# Ensure your Gemini API key is configured
set GEMINI_API_KEY=your-api-key-here   # Windows CMD
$env:GEMINI_API_KEY="your-api-key"    # Windows PowerShell
export GEMINI_API_KEY="your-api-key"  # Linux / macOS

python eval/run_eval.py
```

### CLI Arguments
- `--cases-dir <dir>`: Custom test cases directory (default: `eval/cases`)
- `--output-dir <dir>`: Custom report output directory (default: `eval/results`)
- `--tolerance <int>`: Hit line tolerance window (default: `3`)
- `--delay <float>`: Sleep delay in seconds between cases in real API mode to respect free-tier rate limits (default: `4.0`)
- `--mock` / `--dry-run`: Enable simulated offline mode

---

## Output Reports

Every run writes a Markdown evaluation report to `eval/results/run_<timestamp>.md`, formatted with:
- Top-level executive summary table
- Recall breakdown by category (`security`, `bug`, `performance`, `style`, `best_practice`)
- Recall breakdown by difficulty tier (`obvious`, `subtle`)
- Clean case false positive count and rate
- Per-case drilldown showing hit/miss status, line distances, and extra suggestions

---

## Hermetic Unit Testing

Unit tests for the scoring engine, line matching, and aggregation logic reside in `tests/test_eval_scoring.py`:

```bash
pytest tests/test_eval_scoring.py -v
```

These tests are fully mocked, fast (<1s), require zero credentials, and form part of the standard hermetic test suite.
