import pytest
from src.rag.pipeline import RAGPipeline
from src.models.schemas import (
    HistoricalReview, PullRequest, CodeChange, CodeLanguage
)
from datetime import datetime


@pytest.fixture
def sample_reviews():
    """Create sample historical reviews for testing"""
    return [
        HistoricalReview(
            pr_number=1,
            repository="test/repo",
            file_path="main.py",
            code_snippet="def process_data(data):\n    return data",
            review_comment="Missing input validation. Should check if data is None.",
            reviewer="reviewer1",
            comment_type="issue",
            language=CodeLanguage.PYTHON,
            created_at=datetime.now(),
            was_resolved=True
        ),
        HistoricalReview(
            pr_number=2,
            repository="test/repo",
            file_path="utils.py",
            code_snippet="def calculate(x, y):\n    return x / y",
            review_comment="Potential division by zero. Add error handling.",
            reviewer="reviewer2",
            comment_type="issue",
            language=CodeLanguage.PYTHON,
            created_at=datetime.now(),
            was_resolved=True
        )
    ]


@pytest.fixture
def sample_pr():
    """Create sample pull request"""
    return PullRequest(
        pr_number=100,
        title="Add new feature",
        description="This PR adds validation",
        author="developer1",
        repository="test/repo",
        branch="feature/validation",
        changes=[
            CodeChange(
                file_path="api.py",
                diff="+def validate_input(data):\n+    if data is None:\n+        raise ValueError('Data cannot be None')",
                language=CodeLanguage.PYTHON,
                added_lines=3,
                removed_lines=0
            )
        ],
        created_at=datetime.now()
    )


def test_full_pipeline(sample_reviews, sample_pr):
    """Test complete RAG pipeline"""
    pipeline = RAGPipeline()
    
    # Ingest historical reviews
    pipeline.ingest_historical_reviews(sample_reviews)
    
    # Review new PR
    response = pipeline.review_pull_request(sample_pr)
    
    assert response.pr_number == 100
    assert response.repository == "test/repo"
    assert isinstance(response.suggestions, list)
    assert response.processing_time_seconds > 0