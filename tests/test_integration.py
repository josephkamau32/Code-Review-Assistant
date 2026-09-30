from unittest.mock import MagicMock
import pytest
from src.rag.pipeline import RAGPipeline
from src.models.schemas import HistoricalReview, PullRequest, CodeChange, CodeLanguage
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
            was_resolved=True,
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
            was_resolved=True,
        ),
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
                removed_lines=0,
            )
        ],
        created_at=datetime.now(),
    )


@pytest.mark.integration
def test_full_pipeline(sample_reviews, sample_pr, monkeypatch):
    """Test complete RAG pipeline with boundary mocks (task 2c, 2f)"""
    pipeline = RAGPipeline()

    # Mock embedding creation at the client boundary
    def fake_embed(model, input):
        count = len(input) if isinstance(input, list) else 1
        return MagicMock(
            data=[MagicMock(embedding=[0.05] * 1536) for _ in range(count)]
        )

    mock_emb_create = MagicMock(side_effect=fake_embed)
    monkeypatch.setattr(
        pipeline.embedding_service.client.embeddings, "create", mock_emb_create
    )

    # Mock chat completion at the client boundary
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"suggestions": [{"line_number": 1, "suggestion": "Ensure proper null checks", '
        '"severity": "warning", "category": "best_practice", "confidence": 0.9}], '
        '"summary": "Validation review complete"}'
    )
    mock_chat_create = MagicMock(return_value=MagicMock(choices=[mock_choice]))
    monkeypatch.setattr(
        pipeline.llm_service.client.chat.completions, "create", mock_chat_create
    )

    # Ingest historical reviews into real ChromaDB vector store
    pipeline.ingest_historical_reviews(sample_reviews)

    # Review new PR using real vector store retrieval and prompt assembly
    response = pipeline.review_pull_request(sample_pr)

    assert response.pr_number == 100
    assert response.repository == "test/repo"
    assert len(response.suggestions) == 1
    assert response.suggestions[0].suggestion == "Ensure proper null checks"
    assert response.suggestions[0].category == "best_practice"
    assert "Found 1 warning" in response.summary
    assert response.processing_time_seconds > 0
    assert mock_emb_create.called
    assert mock_chat_create.called
