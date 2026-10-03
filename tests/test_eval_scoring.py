"""
Hermetic unit tests for evaluation harness scoring and metrics engine (LLM-02).
Tests matching rules, tolerance boundaries, clean false-positive accounting, and aggregation.
Uses pure mock/synthetic inputs with zero network or database calls.
"""

import pytest
from eval.scorer import (
    GroundTruthIssue,
    aggregate_scores,
    format_markdown_report,
    is_match,
    score_case,
)


@pytest.fixture
def sample_ground_truth():
    return GroundTruthIssue(
        line_number=10,
        category="security",
        keywords=["sql", "injection"],
        description="SQL injection vulnerability in query builder",
    )


def test_clean_hit_exact_line(sample_ground_truth):
    """Confirm a suggestion with matching category, keyword, and exact line number is a hit."""
    suggestion = {
        "line_number": 10,
        "category": "security",
        "suggestion": "Critical: Possible SQL injection vulnerability in f-string query.",
    }
    dist = is_match(sample_ground_truth, suggestion, line_tolerance=3)
    assert dist == 0


def test_hit_within_line_tolerance(sample_ground_truth):
    """Confirm a suggestion within tolerance (+2 lines) counts as a hit."""
    suggestion = {
        "line_number": 12,
        "category": "security",
        "suggestion": "SQL injection detected here.",
    }
    dist = is_match(sample_ground_truth, suggestion, line_tolerance=3)
    assert dist == 2


def test_miss_outside_line_tolerance(sample_ground_truth):
    """Confirm a suggestion outside tolerance (+4 lines > 3) does not match."""
    suggestion = {
        "line_number": 14,
        "category": "security",
        "suggestion": "SQL injection vulnerability detected.",
    }
    dist = is_match(sample_ground_truth, suggestion, line_tolerance=3)
    assert dist is None


def test_category_mismatch(sample_ground_truth):
    """Confirm a suggestion with differing category does not match even if line and keywords match."""
    suggestion = {
        "line_number": 10,
        "category": "style",  # Mismatch: expected security
        "suggestion": "SQL injection pattern should follow style guide.",
    }
    dist = is_match(sample_ground_truth, suggestion, line_tolerance=3)
    assert dist is None


def test_keyword_mismatch(sample_ground_truth):
    """Confirm a suggestion without any expected keyword does not match."""
    suggestion = {
        "line_number": 10,
        "category": "security",
        "suggestion": "Use parameterized statements instead of direct concatenation.",
    }
    # Expected keywords are ["sql", "injection"], neither is in suggestion text
    dist = is_match(sample_ground_truth, suggestion, line_tolerance=3)
    assert dist is None


def test_score_case_hit_and_extra_suggestion():
    """Confirm valid hit is recorded and extraneous suggestion is preserved in extra_suggestions."""
    case_data = {
        "id": "case_test_sql",
        "title": "SQL Injection Test",
        "difficulty": "obvious",
        "ground_truth": [
            {
                "line_number": 15,
                "category": "security",
                "keywords": ["sql", "injection"],
                "description": "SQL injection vulnerability",
            }
        ],
    }
    suggestions = [
        {
            "line_number": 16,  # delta = 1, within tolerance
            "category": "security",
            "suggestion": "Fix SQL injection using parameterized query",
        },
        {
            "line_number": 5,
            "category": "style",
            "suggestion": "Consider adding docstrings to this function",
        },
    ]

    scored = score_case(case_data, suggestions, line_tolerance=3)
    assert len(scored.hits) == 1
    assert scored.hits[0].line_distance == 1
    assert scored.hits[0].is_exact_line is True
    assert len(scored.misses) == 0
    assert len(scored.extra_suggestions) == 1
    assert scored.extra_suggestions[0]["category"] == "style"
    assert scored.clean_false_positives == 0


def test_clean_case_zero_false_positives():
    """Confirm clean cases with no suggestions score 0 false positives."""
    case_data = {
        "id": "case_clean_test",
        "title": "Clean Code Case",
        "difficulty": "clean",
        "ground_truth": [],
    }
    scored = score_case(case_data, suggestions=[], line_tolerance=3)
    assert scored.clean_false_positives == 0
    assert len(scored.hits) == 0
    assert len(scored.misses) == 0
    assert len(scored.extra_suggestions) == 0


def test_clean_case_with_false_positives():
    """Confirm clean cases penalize any returned suggestion as a false positive."""
    case_data = {
        "id": "case_clean_test",
        "title": "Clean Code Case",
        "difficulty": "clean",
        "ground_truth": [],
    }
    suggestions = [
        {
            "line_number": 8,
            "category": "bug",
            "suggestion": "Spurious hallucinated bug suggestion",
        }
    ]
    scored = score_case(case_data, suggestions=suggestions, line_tolerance=3)
    assert scored.clean_false_positives == 1
    assert len(scored.extra_suggestions) == 1


def test_aggregate_scores_math():
    """Confirm mathematical aggregation across obvious, subtle, and clean cases."""
    case_1 = {
        "id": "c1",
        "title": "Obvious Bug",
        "difficulty": "obvious",
        "ground_truth": [
            {
                "line_number": 10,
                "category": "bug",
                "keywords": ["off-by-one"],
                "description": "Loop boundary issue",
            }
        ],
    }
    case_2 = {
        "id": "c2",
        "title": "Subtle Bug",
        "difficulty": "subtle",
        "ground_truth": [
            {
                "line_number": 20,
                "category": "security",
                "keywords": ["race", "toctou"],
                "description": "Race condition",
            }
        ],
    }
    case_3 = {
        "id": "c3",
        "title": "Clean Code",
        "difficulty": "clean",
        "ground_truth": [],
    }

    # Case 1 hits at exact line
    sc1 = score_case(
        case_1,
        [
            {
                "line_number": 10,
                "category": "bug",
                "suggestion": "Fix off-by-one index error",
            }
        ],
    )
    # Case 2 misses (model hallucinated style instead)
    sc2 = score_case(
        case_2,
        [{"line_number": 20, "category": "style", "suggestion": "Bad formatting"}],
    )
    # Case 3 clean with 0 false positives
    sc3 = score_case(case_3, [])

    metrics = aggregate_scores([sc1, sc2, sc3])

    assert metrics.total_cases == 3
    assert metrics.errored_cases == 0
    assert metrics.total_ground_truth_issues == 2
    assert metrics.total_hits == 1
    assert metrics.overall_recall == 0.5  # 1 hit / 2 issues
    assert metrics.hits_within_one_line == 1
    assert metrics.line_accuracy_rate == 1.0  # 1 exact hit / 1 total hit
    assert metrics.clean_cases_count == 1
    assert metrics.clean_false_positive_rate == 0.0
    assert metrics.total_clean_false_positives == 0

    # Difficulty breakdown
    assert metrics.by_difficulty["obvious"].hits == 1
    assert metrics.by_difficulty["obvious"].recall == 1.0
    assert metrics.by_difficulty["subtle"].hits == 0
    assert metrics.by_difficulty["subtle"].recall == 0.0

    # Category breakdown
    assert metrics.by_category["bug"].hits == 1
    assert metrics.by_category["bug"].recall == 1.0
    assert metrics.by_category["security"].hits == 0
    assert metrics.by_category["security"].recall == 0.0


def test_format_markdown_report():
    """Confirm report generation produces expected markdown structure."""
    case_data = {
        "id": "case_01",
        "title": "Test Case",
        "difficulty": "obvious",
        "ground_truth": [
            {
                "line_number": 10,
                "category": "security",
                "keywords": ["sql"],
                "description": "SQL injection",
            }
        ],
    }
    scored = score_case(
        case_data,
        [
            {
                "line_number": 10,
                "category": "security",
                "suggestion": "Potential sql issue",
            }
        ],
    )
    metrics = aggregate_scores([scored])
    report = format_markdown_report(metrics, [scored])

    assert "# Code-Review-Assistant Evaluation Report (LLM-02)" in report
    assert "Overall Defect Recall" in report
    assert "case_01" in report
    assert "PASS" in report
