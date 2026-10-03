"""
Evaluation Scorer and Metrics Engine for Code-Review-Assistant.

Calculates precision, recall, line accuracy (+/-1 line vs tolerance),
and clean-case false positive rates for LLM-02.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class GroundTruthIssue:
    line_number: int
    category: str
    keywords: List[str]
    description: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroundTruthIssue":
        return cls(
            line_number=int(data["line_number"]),
            category=str(data["category"]).strip().lower(),
            keywords=[str(kw).strip().lower() for kw in data.get("keywords", [])],
            description=str(data.get("description", "")),
        )


@dataclass
class HitMatch:
    ground_truth: GroundTruthIssue
    suggestion: Dict[str, Any]
    line_distance: int
    is_exact_line: bool  # True if abs(line_distance) <= 1
    keyword_matched: bool = False


@dataclass
class ScoredCase:
    case_id: str
    title: str
    difficulty: str  # obvious | clean | subtle
    ground_truth: List[GroundTruthIssue]
    hits: List[HitMatch] = field(default_factory=list)
    misses: List[GroundTruthIssue] = field(default_factory=list)
    extra_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    clean_false_positives: int = 0
    error: Optional[str] = None
    raw_suggestions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CategoryMetric:
    total_issues: int = 0
    hits: int = 0
    recall: float = 0.0


@dataclass
class DifficultyMetric:
    total_issues: int = 0
    hits: int = 0
    recall: float = 0.0


@dataclass
class EvalMetrics:
    total_cases: int = 0
    errored_cases: int = 0
    total_ground_truth_issues: int = 0
    total_hits: int = 0
    overall_recall: float = 0.0
    hits_within_one_line: int = 0
    line_accuracy_rate: float = 0.0  # hits within +/-1 line / total_hits
    clean_cases_count: int = 0
    clean_cases_with_fp: int = 0
    clean_false_positive_rate: float = (
        0.0  # clean cases with >=1 FP / total clean cases
    )
    total_clean_false_positives: int = 0
    total_extra_suggestions: int = 0
    total_suggestions: int = 0
    overall_precision: float = 0.0
    by_category: Dict[str, CategoryMetric] = field(default_factory=dict)
    by_difficulty: Dict[str, DifficultyMetric] = field(default_factory=dict)


def is_match(
    gt: GroundTruthIssue,
    suggestion: Dict[str, Any],
    line_tolerance: int = 3,
) -> Optional[int]:
    """Check if a suggestion matches a ground truth issue.

    Returns the absolute line distance if matched, or None if not matched.
    A hit requires category match and line number within tolerance.
    """
    sugg_cat = str(suggestion.get("category", "")).strip().lower()
    if sugg_cat != gt.category:
        return None

    raw_line = suggestion.get("line_number")
    if raw_line is None:
        return None

    try:
        sugg_line = int(raw_line)
    except (ValueError, TypeError):
        return None

    line_distance = abs(sugg_line - gt.line_number)
    if line_distance > line_tolerance:
        return None

    return line_distance


def _find_best_match(
    gt: GroundTruthIssue,
    suggestions: List[Dict[str, Any]],
    used_indices: set,
    line_tolerance: int,
) -> tuple[Optional[int], Optional[int]]:
    """Find the suggestion index and distance that best matches a ground-truth defect."""
    best_idx = None
    best_dist = None
    for idx, sugg in enumerate(suggestions):
        if idx in used_indices:
            continue
        dist = is_match(gt, sugg, line_tolerance=line_tolerance)
        if dist is not None and (best_dist is None or dist < best_dist):
            best_dist = dist
            best_idx = idx
    return best_idx, best_dist


def score_case(
    case_data: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
    line_tolerance: int = 3,
    error: Optional[str] = None,
) -> ScoredCase:
    """Score a single evaluation test case against model suggestions."""
    case_id = case_data.get("id", "unknown_case")
    title = case_data.get("title", "")
    difficulty = case_data.get("difficulty", "obvious")

    gt_list = [
        GroundTruthIssue.from_dict(item) for item in case_data.get("ground_truth", [])
    ]

    scored = ScoredCase(
        case_id=case_id,
        title=title,
        difficulty=difficulty,
        ground_truth=gt_list,
        error=error,
        raw_suggestions=suggestions,
    )

    if error:
        scored.misses = list(gt_list)
        return scored

    # For CLEAN cases: any suggestion is a false positive
    if difficulty == "clean" or not gt_list:
        scored.clean_false_positives = len(suggestions)
        scored.extra_suggestions = list(suggestions)
        return scored

    used_suggestion_indices = set()
    # Note: Greedy per-ground-truth-issue assignment. Guaranteed optimal when each
    # case contains at most one ground-truth issue (true for all current cases, max=1).
    # If the dataset is extended with multi-issue cases where suggestions compete,
    # consider upgrading to maximum-weight bipartite matching (e.g., Hungarian algorithm).
    for gt in gt_list:
        best_idx, best_dist = _find_best_match(
            gt, suggestions, used_suggestion_indices, line_tolerance
        )
        if best_idx is not None:
            used_suggestion_indices.add(best_idx)
            sugg = suggestions[best_idx]
            sugg_text = str(sugg.get("suggestion", "")).lower()
            kw_matched = bool(
                gt.keywords and any(kw in sugg_text for kw in gt.keywords)
            )
            scored.hits.append(
                HitMatch(
                    ground_truth=gt,
                    suggestion=sugg,
                    line_distance=best_dist,
                    is_exact_line=best_dist <= 1,
                    keyword_matched=kw_matched,
                )
            )
        else:
            scored.misses.append(gt)

    for idx, sugg in enumerate(suggestions):
        if idx not in used_suggestion_indices:
            scored.extra_suggestions.append(sugg)

    return scored


def _record_case_metrics(sc: ScoredCase, metrics: EvalMetrics):
    """Update metrics counters for a single scored case."""
    if sc.error:
        metrics.errored_cases += 1
        if sc.difficulty == "clean" or not sc.ground_truth:
            return

    if sc.difficulty == "clean":
        metrics.clean_cases_count += 1
        if sc.clean_false_positives > 0:
            metrics.clean_cases_with_fp += 1
        metrics.total_clean_false_positives += sc.clean_false_positives
        return

    metrics.total_extra_suggestions += len(sc.extra_suggestions)

    for hit in sc.hits:
        metrics.total_hits += 1
        if hit.is_exact_line:
            metrics.hits_within_one_line += 1

        cat = hit.ground_truth.category
        metrics.by_category.setdefault(cat, CategoryMetric()).hits += 1
        metrics.by_category[cat].total_issues += 1

        diff = sc.difficulty
        metrics.by_difficulty.setdefault(diff, DifficultyMetric()).hits += 1
        metrics.by_difficulty[diff].total_issues += 1

    for miss in sc.misses:
        cat = miss.category
        metrics.by_category.setdefault(cat, CategoryMetric()).total_issues += 1

        diff = sc.difficulty
        metrics.by_difficulty.setdefault(diff, DifficultyMetric()).total_issues += 1


def _compute_rates(metrics: EvalMetrics):
    """Calculate percentage rates across all aggregated categories."""
    metrics.total_suggestions = (
        metrics.total_hits
        + metrics.total_extra_suggestions
        + metrics.total_clean_false_positives
    )
    if metrics.total_suggestions > 0:
        metrics.overall_precision = round(
            metrics.total_hits / metrics.total_suggestions, 4
        )

    if metrics.total_ground_truth_issues > 0:
        metrics.overall_recall = round(
            metrics.total_hits / metrics.total_ground_truth_issues, 4
        )

    if metrics.total_hits > 0:
        metrics.line_accuracy_rate = round(
            metrics.hits_within_one_line / metrics.total_hits, 4
        )

    if metrics.clean_cases_count > 0:
        metrics.clean_false_positive_rate = round(
            metrics.clean_cases_with_fp / metrics.clean_cases_count, 4
        )

    for cm in metrics.by_category.values():
        if cm.total_issues > 0:
            cm.recall = round(cm.hits / cm.total_issues, 4)

    for dm in metrics.by_difficulty.values():
        if dm.total_issues > 0:
            dm.recall = round(dm.hits / dm.total_issues, 4)


def aggregate_scores(scored_cases: List[ScoredCase]) -> EvalMetrics:
    """Aggregate individual case results into overall evaluation metrics."""
    metrics = EvalMetrics(total_cases=len(scored_cases))

    for cat in ["security", "bug", "performance", "style", "best_practice"]:
        metrics.by_category[cat] = CategoryMetric()

    for diff in ["obvious", "subtle"]:
        metrics.by_difficulty[diff] = DifficultyMetric()

    for sc in scored_cases:
        _record_case_metrics(sc, metrics)

    non_clean_misses = sum(
        len(sc.misses) for sc in scored_cases if sc.difficulty != "clean"
    )
    metrics.total_ground_truth_issues = metrics.total_hits + non_clean_misses
    _compute_rates(metrics)
    return metrics


def _format_summary_table(metrics: EvalMetrics, lines: List[str]):
    """Append executive summary table lines."""
    lines.append("## Executive Summary\n")
    lines.append("| Metric | Value | Description |")
    lines.append("| :--- | :--- | :--- |")
    lines.append(
        f"| **Total Cases Evaluated** | {metrics.total_cases} | Total benchmark test cases executed |"
    )
    lines.append(
        f"| **Errored Cases** | {metrics.errored_cases} | Pipeline execution failures |"
    )

    prec_pct = f"{metrics.overall_precision * 100:.1f}%"
    prec_detail = f"({metrics.total_hits}/{metrics.total_suggestions})"
    lines.append(
        f"| **Overall Precision** | **{prec_pct}** {prec_detail} | Suggestions that matched true defects |"
    )

    rec_pct = f"{metrics.overall_recall * 100:.1f}%"
    rec_detail = f"({metrics.total_hits}/{metrics.total_ground_truth_issues})"
    lines.append(
        f"| **Overall Defect Recall** | **{rec_pct}** {rec_detail} | Planted defects successfully detected |"
    )

    acc_pct = f"{metrics.line_accuracy_rate * 100:.1f}%"
    denom = metrics.total_hits if metrics.total_hits else 1
    acc_detail = f"({metrics.hits_within_one_line}/{denom})"
    lines.append(
        f"| **Line Accuracy (+/-1 line)** | **{acc_pct}** {acc_detail} | Hits anchored within 1 line |"
    )

    fp_pct = f"{metrics.clean_false_positive_rate * 100:.1f}%"
    fp_detail = f"({metrics.clean_cases_with_fp}/{metrics.clean_cases_count})"
    lines.append(
        f"| **Clean False Positive Rate** | **{fp_pct}** {fp_detail} | Clean PRs incorrectly flagged |"
    )
    lines.append(
        f"| **Clean False Positive Count** | {metrics.total_clean_false_positives} | Spurious clean suggestions |\n"
    )


def _format_hits_and_misses(sc: ScoredCase, lines: List[str]):
    """Format hit, miss, and extra suggestion details for non-clean case."""
    lines.append(f"- **Hits ({len(sc.hits)}):**")
    for hit in sc.hits:
        dist_str = (
            "exact (+/-1)" if hit.is_exact_line else f"+/-{hit.line_distance} lines"
        )
        kw_str = f"keyword_matched: {str(hit.keyword_matched).lower()}"
        lines.append(
            f"  - Target L{hit.ground_truth.line_number} -> Suggested L{hit.suggestion.get('line_number')} "
            f"({dist_str}, {kw_str}) [{hit.ground_truth.category}]: {hit.suggestion.get('suggestion')}"
        )
    if not sc.hits:
        lines.append("  - None")

    lines.append(f"- **Misses ({len(sc.misses)}):**")
    for miss in sc.misses:
        lines.append(
            f"  - Target L{miss.line_number} [{miss.category}]: {miss.description} "
            f"(Keywords: {', '.join(miss.keywords)})"
        )
    if not sc.misses:
        lines.append("  - None")

    if sc.extra_suggestions:
        lines.append(
            f"- **Extra Suggestions ({len(sc.extra_suggestions)} for manual review):**"
        )
        for extra in sc.extra_suggestions:
            lines.append(
                f"  - [L{extra.get('line_number')}] ({extra.get('category')}): {extra.get('suggestion')}"
            )
    lines.append("")


def _format_case_drilldown(sc: ScoredCase, lines: List[str]):
    """Format details for an individual test case."""
    status_icon = (
        "PASS"
        if not sc.misses and sc.clean_false_positives == 0 and not sc.error
        else "FAIL"
    )
    if sc.error:
        status_icon = "ERROR"

    lines.append(f"### `{sc.case_id}` [{status_icon}]")
    lines.append(f"- **Title:** {sc.title}")
    lines.append(f"- **Difficulty:** `{sc.difficulty}`")
    if sc.error:
        lines.append(f"- **Error:** `{sc.error}`\n")
        return

    if sc.difficulty == "clean":
        lines.append(
            f"- **Clean Status:** {sc.clean_false_positives} false positives detected"
        )
        for sugg in sc.raw_suggestions:
            lines.append(
                f"  - [L{sugg.get('line_number')}] ({sugg.get('category')}): {sugg.get('suggestion')}"
            )
        lines.append("")
        return

    _format_hits_and_misses(sc, lines)


def format_markdown_report(
    metrics: EvalMetrics,
    scored_cases: List[ScoredCase],
    timestamp: Optional[str] = None,
    line_tolerance: int = 3,
) -> str:
    """Format evaluation results into a comprehensive Markdown report."""
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# Code-Review-Assistant Evaluation Report (LLM-02)")
    lines.append(f"**Execution Timestamp:** {timestamp}  ")
    lines.append(
        f"**Line Tolerance:** +/-{line_tolerance} lines (exact accuracy measured at +/-1 line)  \n"
    )

    _format_summary_table(metrics, lines)

    lines.append("### Recall by Defect Category\n")
    lines.append("| Category | Detected / Total | Recall Rate |")
    lines.append("| :--- | :--- | :--- |")
    for cat, cm in sorted(metrics.by_category.items()):
        pct = f"{cm.recall * 100:.1f}%" if cm.total_issues > 0 else "N/A"
        lines.append(f"| `{cat}` | {cm.hits} / {cm.total_issues} | {pct} |")
    lines.append("")

    lines.append("### Recall by Difficulty Tier\n")
    lines.append("| Difficulty Tier | Detected / Total | Recall Rate |")
    lines.append("| :--- | :--- | :--- |")
    for diff, dm in sorted(metrics.by_difficulty.items()):
        pct = f"{dm.recall * 100:.1f}%" if dm.total_issues > 0 else "N/A"
        lines.append(f"| `{diff}` | {dm.hits} / {dm.total_issues} | {pct} |")
    lines.append("")

    lines.append("## Detailed Per-Case Results\n")
    for sc in scored_cases:
        _format_case_drilldown(sc, lines)

    return "\n".join(lines)
