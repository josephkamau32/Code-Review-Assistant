from datetime import datetime
from unittest.mock import MagicMock
import httpx
from openai import RateLimitError
import pytest
import tenacity
from github import GithubException

from src.models.schemas import CodeChange, CodeLanguage, HistoricalReview
from src.rag.embeddings import EmbeddingService
from src.rag.llm_service import LLMService
from src.utils.github_client import GitHubClient


def test_embedding_service(monkeypatch):
    """Test embedding generation with mocked OpenAI client at the boundary (task 2c)"""
    service = EmbeddingService()

    # Boundary mock on OpenAI embeddings client
    mock_item = MagicMock(embedding=[0.05] * 1536)
    mock_response = MagicMock(data=[mock_item])
    mock_create = MagicMock(return_value=mock_response)
    monkeypatch.setattr(service.client.embeddings, "create", mock_create)

    text = "def hello_world(): print('Hello, World!')"
    embedding = service.embed_text(text)

    mock_create.assert_called_once_with(model=service.model, input=text)
    assert isinstance(embedding, list)
    assert len(embedding) == 1536
    assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_batch_embedding(monkeypatch):
    """Test batch embedding generation with mocked OpenAI client at boundary (task 2c)"""
    service = EmbeddingService()

    texts = ["First code snippet", "Second code snippet", "Third code snippet"]

    # Boundary mock on OpenAI batch embeddings
    mock_data = [MagicMock(embedding=[0.1] * 1536) for _ in texts]
    mock_response = MagicMock(data=mock_data)
    mock_create = MagicMock(return_value=mock_response)
    monkeypatch.setattr(service.client.embeddings, "create", mock_create)

    embeddings = service.embed_batch(texts)

    mock_create.assert_called_once_with(model=service.model, input=texts)
    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)


def test_embedding_service_api_error(monkeypatch):
    """Test error handling when OpenAI embedding API fails at the boundary (task 2c)"""
    service = EmbeddingService()

    # Fast-forward retry wait to keep test fast
    monkeypatch.setattr(service.embed_text.retry, "wait", tenacity.wait_none())

    mock_create = MagicMock(side_effect=Exception("API connection timeout"))
    monkeypatch.setattr(service.client.embeddings, "create", mock_create)

    with pytest.raises(Exception):
        service.embed_text("test error snippet")

    assert mock_create.call_count == 3


def test_code_change_model():
    """Test CodeChange model validation"""
    code_change = CodeChange(
        file_path="src/main.py",
        diff="+    print('new line')\n-    print('old line')",
        language=CodeLanguage.PYTHON,
        added_lines=1,
        removed_lines=1,
    )

    assert code_change.file_path == "src/main.py"
    assert code_change.language == CodeLanguage.PYTHON


def test_historical_review_model():
    """Test HistoricalReview model"""
    review = HistoricalReview(
        pr_number=123,
        repository="test/repo",
        file_path="main.py",
        code_snippet="def test(): pass",
        review_comment="Consider adding docstring",
        reviewer="john_doe",
        comment_type="suggestion",
        language=CodeLanguage.PYTHON,
        created_at=datetime.now(),
        was_resolved=True,
    )

    assert review.pr_number == 123
    assert review.comment_type == "suggestion"


@pytest.mark.xfail(reason="BUG-05: retry logic broken, fix in Step 3")
def test_llm_service_retry_on_rate_limit(monkeypatch):
    """Test that transient RateLimitError triggers Tenacity retries on LLM chat completion (task 2c).

    Currently fails because BUG-05 catches RateLimitError inside generate_review and
    wraps it into LLMProviderError before Tenacity's retry decorator can catch and retry it.
    """
    service = LLMService()
    monkeypatch.setattr(service.generate_review.retry, "wait", tenacity.wait_none())

    code_change = CodeChange(
        file_path="src/main.py",
        diff="+def test(): pass",
        language=CodeLanguage.PYTHON,
        added_lines=1,
        removed_lines=0,
    )

    dummy_response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    rate_limit_err = RateLimitError(
        message="Rate limit exceeded", response=dummy_response, body=None
    )

    mock_choice = MagicMock()
    mock_choice.message.content = '{"suggestions": [], "summary": "Review complete"}'
    mock_success = MagicMock(choices=[mock_choice])

    mock_create = MagicMock(side_effect=[rate_limit_err, mock_success])
    monkeypatch.setattr(service.client.chat.completions, "create", mock_create)

    # Under working retries, call_count should be 2 and result returned.
    # Under BUG-05, LLMProviderError is raised on attempt 1 without retry.
    result = service.generate_review(code_change, [])
    assert mock_create.call_count == 2
    assert result["summary"] == "Review complete"


def test_github_client_api_error(monkeypatch):
    """Test error handling when GitHub API fails at the boundary (task 2c)"""
    client = GitHubClient()
    mock_gh = MagicMock()
    mock_gh.get_rate_limit.return_value.core.remaining = 5000
    mock_gh.get_repo.side_effect = GithubException(404, {"message": "Not Found"}, None)
    monkeypatch.setattr(client, "client", mock_gh)

    with pytest.raises(GithubException) as exc_info:
        client.fetch_historical_reviews("nonexistent/repo")
    assert exc_info.value.status == 404
