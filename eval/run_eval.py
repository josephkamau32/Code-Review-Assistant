#!/usr/bin/env python3
"""
Evaluation Runner for Code-Review-Assistant (LLM-02).

Executes benchmark test cases through the production RAG review pipeline,
scores precision, recall, line accuracy, and clean false-positive rates,
and outputs an evaluation report.

Usage:
    python eval/run_eval.py [--mock] [--tolerance 3] [--cases-dir eval/cases]
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock

# Allow imports from repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# If mock mode is requested, configure dummy credentials before src import
if "--mock" in sys.argv or "--dry-run" in sys.argv:
    os.environ.setdefault("ENVIRONMENT", "testing")
    os.environ.setdefault("GEMINI_API_KEY", "dummy-gemini-key-for-mock-eval")
    os.environ.setdefault("OPENAI_API_KEY", "dummy-openai-key-for-mock-eval-32chars")
    os.environ.setdefault("LLM_PROVIDER", "gemini")
    os.environ.setdefault("EMBEDDING_PROVIDER", "gemini")

try:
    from loguru import logger
    from src.models.schemas import CodeChange, CodeLanguage, PullRequest
    from src.rag.pipeline import RAGPipeline
    from eval.scorer import (
        ScoredCase,
        aggregate_scores,
        format_markdown_report,
        score_case,
    )
except ImportError as e:
    print(f"Error importing modules: {e}", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run RAG pipeline evaluation benchmark (LLM-02)."
    )
    parser.add_argument(
        "--cases-dir",
        default="eval/cases",
        help="Directory containing JSON test cases (default: eval/cases)",
    )
    parser.add_argument(
        "--output-dir",
        default="eval/results",
        help="Directory where evaluation reports are saved (default: eval/results)",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=3,
        help="Line number tolerance for hit matching (+/- lines, default: 3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=4.0,
        help="Sleep delay in seconds between cases in real API mode (default: 4.0)",
    )
    parser.add_argument(
        "--mock",
        "--dry-run",
        dest="mock_mode",
        action="store_true",
        help="Execute simulated dry run with mocked LLM output (no real API calls)",
    )
    return parser.parse_args()


def load_cases(cases_dir: str) -> List[Dict[str, Any]]:
    case_files = sorted(glob.glob(os.path.join(cases_dir, "*.json")))
    if not case_files:
        raise FileNotFoundError(f"No JSON test cases found in {cases_dir}")

    cases = []
    for cf in case_files:
        with open(cf, "r", encoding="utf-8") as f:
            cases.append(json.load(f))
    return cases


def build_mock_llm_service(pipeline: RAGPipeline, cases: List[Dict[str, Any]]):
    """Patch pipeline.llm_service to produce realistic simulated responses for dry-run."""
    case_map = {(c["file_path"], c["diff"]): c for c in cases}

    def mock_generate_review(code_change, similar_reviews=None, style_guide_context=""):
        c = case_map.get((code_change.file_path, code_change.diff))
        if not c:
            return {"suggestions": []}

        diff = c.get("difficulty", "obvious")
        gt_list = c.get("ground_truth", [])

        if diff == "clean" or not gt_list:
            return {"suggestions": []}

        if diff == "obvious":
            suggestions = []
            for gt in gt_list:
                suggestions.append(
                    {
                        "line_number": gt["line_number"],
                        "category": gt["category"],
                        "suggestion": f"Planted defect identified ({gt['keywords'][0]}): {gt['description']}",
                        "severity": (
                            "error"
                            if gt["category"] in ("security", "bug")
                            else "warning"
                        ),
                        "confidence": 0.95,
                    }
                )
            return {"suggestions": suggestions}

        if diff == "subtle":
            if "naive_datetime" in c["id"] or "mutate_iterating" in c["id"]:
                gt = gt_list[0]
                return {
                    "suggestions": [
                        {
                            "line_number": gt["line_number"],
                            "category": gt["category"],
                            "suggestion": f"Subtle issue detected ({gt['keywords'][0]}): {gt['description']}",
                            "severity": "warning",
                            "confidence": 0.85,
                        }
                    ]
                }
            return {"suggestions": []}

        return {"suggestions": []}

    pipeline.llm_service.generate_review = mock_generate_review
    pipeline.llm_service.generate_summary = MagicMock(
        return_value="Simulated evaluation run completed successfully."
    )
    pipeline.embedding_service.embed_code_change = MagicMock(return_value=[0.0] * 768)
    pipeline.vector_store.search_similar_reviews = MagicMock(
        return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]}
    )


def _evaluate_case(
    pipeline: RAGPipeline,
    case_data: Dict[str, Any],
    pr_num: int,
    tolerance: int,
) -> ScoredCase:
    """Run a single test case through the pipeline and score it."""
    code_change = CodeChange(
        file_path=case_data["file_path"],
        diff=case_data["diff"],
        language=CodeLanguage(case_data["language"]),
        added_lines=case_data["diff"].count("\n+"),
        removed_lines=case_data["diff"].count("\n-"),
    )
    pull_request = PullRequest(
        pr_number=pr_num,
        title=f"Eval PR: {case_data.get('title', '')}",
        description="Automated evaluation run for LLM-02",
        author="eval-bot",
        repository="eval/benchmark",
        branch="main",
        changes=[code_change],
        created_at=datetime.now(timezone.utc),
    )

    review_response = pipeline.review_pull_request(pull_request)
    raw_suggestions = [s.model_dump() for s in review_response.suggestions]
    return score_case(case_data, raw_suggestions, line_tolerance=tolerance)


def _print_case_status(scored: ScoredCase):
    """Print one-line result summary for a case."""
    if scored.difficulty == "clean":
        if scored.clean_false_positives == 0:
            print("PASS (clean, 0 FP)")
        else:
            print(f"FAIL ({scored.clean_false_positives} FP)")
    elif scored.hits:
        print(f"HIT ({len(scored.hits)}/{len(scored.ground_truth)})")
    else:
        print(f"MISS (0/{len(scored.ground_truth)})")


def _save_report(
    output_dir: str,
    metrics: Any,
    scored_cases: List[ScoredCase],
    tolerance: int,
    is_mock: bool,
) -> str:
    """Write markdown evaluation report and return path."""
    os.makedirs(output_dir, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    slug = now_utc.strftime("%Y%m%d_%H%M%S_%f")
    report_path = os.path.join(output_dir, f"run_{slug}.md")
    timestamp_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    report_content = format_markdown_report(
        metrics=metrics,
        scored_cases=scored_cases,
        timestamp=timestamp_str,
        line_tolerance=tolerance,
    )

    if is_mock:
        notice = (
            "> [!NOTE]\n"
            "> **PLUMBING DRY-RUN SMOKE TEST**: Executed with mocked LLM responses.\n"
            "> Validates harness mechanics, NOT real-world Gemini model accuracy.\n\n"
        )
        report_content = notice + report_content

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return report_path


def main():
    args = parse_args()
    print("=" * 70)
    print("Code-Review-Assistant Evaluation Benchmark (LLM-02)")
    print("=" * 70)

    if args.mock_mode:
        print("[MOCK DRY-RUN MODE: Zero real API calls]")
    else:
        print("[REAL EVALUATION MODE: Making real calls to Gemini API]")
        if not os.environ.get("GEMINI_API_KEY"):
            print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
            sys.exit(1)

    cases = load_cases(args.cases_dir)
    print(f"Loaded {len(cases)} test cases from {args.cases_dir}")

    pipeline = RAGPipeline()
    if args.mock_mode:
        build_mock_llm_service(pipeline, cases)

    scored_cases: List[ScoredCase] = []
    for idx, case_data in enumerate(cases):
        cid = case_data["id"]
        print(
            f"[{idx + 1:02d}/{len(cases):02d}] Evaluating {cid}...", end=" ", flush=True
        )

        try:
            scored = _evaluate_case(pipeline, case_data, idx + 1, args.tolerance)
            scored_cases.append(scored)
            _print_case_status(scored)
        except Exception as exc:
            logger.error(f"Failed evaluating {cid}: {exc}")
            print(f"ERROR: {exc}")
            scored_cases.append(
                score_case(case_data, [], line_tolerance=args.tolerance, error=str(exc))
            )

        # In real API mode, pause between cases to respect free-tier rate limits (15 RPM)
        if not args.mock_mode and args.delay > 0 and idx < len(cases) - 1:
            time.sleep(args.delay)

    metrics = aggregate_scores(scored_cases)
    report_path = _save_report(
        args.output_dir, metrics, scored_cases, args.tolerance, args.mock_mode
    )

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total Cases:                 {metrics.total_cases}")
    print(f"Errored Cases:               {metrics.errored_cases}")

    precision_stat = f"{metrics.overall_precision * 100:.1f}% ({metrics.total_hits}/{metrics.total_suggestions})"
    recall_stat = f"{metrics.overall_recall * 100:.1f}% ({metrics.total_hits}/{metrics.total_ground_truth_issues})"
    accuracy_stat = f"{metrics.line_accuracy_rate * 100:.1f}% ({metrics.hits_within_one_line}/{metrics.total_hits or 1})"
    clean_fp_pct = f"{metrics.clean_false_positive_rate * 100:.1f}%"
    clean_fp_stat = (
        f"{clean_fp_pct} ({metrics.clean_cases_with_fp}/{metrics.clean_cases_count})"
    )

    print(f"Overall Precision:           {precision_stat}")
    print(f"Overall Defect Recall:       {recall_stat}")
    print(f"Line Accuracy (+/-1 line):   {accuracy_stat}")
    print(f"Clean False Positive Rate:   {clean_fp_stat}")
    print(f"Clean False Positive Count:  {metrics.total_clean_false_positives}")
    print(f"\nReport saved to: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
