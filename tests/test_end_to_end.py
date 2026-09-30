"""
End-to-end test that validates the entire pipeline
Run this before deploying to production
"""

from datetime import datetime
import hashlib
import hmac
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import settings
from src.models.schemas import CodeChange, CodeLanguage, HistoricalReview, PullRequest
from src.rag.pipeline import RAGPipeline
from src.utils.github_client import GitHubClient


@pytest.mark.e2e
def test_full_workflow():
    """Test complete workflow from ingestion to review against live GitHub (task 2f)"""
    # Skip test if GitHub token not configured or placeholder
    if (
        not settings.github_token
        or settings.github_token == "your_github_token_here"
        or settings.github_token.startswith("ghp_dummy")
    ):
        pytest.skip("Live GitHub token not configured - skipping e2e test")

    # 1. Ingest sample data
    github_client = GitHubClient()
    pipeline = RAGPipeline()

    reviews = github_client.fetch_historical_reviews("django/django", max_prs=5)
    assert len(reviews) > 0, "Should fetch some reviews"

    pipeline.ingest_historical_reviews(reviews)

    # 2. Get a test PR
    pr = github_client.get_pr_changes("django/django", 15000)
    assert pr.pr_number == 15000

    # 3. Review it
    response = pipeline.review_pull_request(pr)

    # 4. Validate response
    assert response.pr_number == 15000
    assert isinstance(response.suggestions, list)
    assert response.processing_time_seconds > 0


def test_api_health():
    """Test that API is healthy using TestClient (TEST-03)"""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_webhook_signature_validation(monkeypatch):
    """Test webhook signature validation using TestClient with mocked GitHub boundary (TEST-03)"""
    if (
        not settings.github_webhook_secret
        or settings.github_webhook_secret == "your_webhook_secret_here"
    ):
        pytest.skip("GitHub webhook secret not configured - skipping webhook test")

    from unittest.mock import MagicMock
    import src.api.routes as routes

    # Mock GitHubClient boundary to ensure hermetic execution and prevent outbound network calls
    mock_github_client = MagicMock()
    mock_github_client.get_pr_changes.return_value = None
    monkeypatch.setattr(routes, "github_client", mock_github_client)

    client = TestClient(app)
    payload = b'{"action": "opened", "pull_request": {"number": 1}, "repository": {"full_name": "test/repo"}}'
    signature = (
        "sha256="
        + hmac.new(
            settings.github_webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
    )

    response = client.post(
        "/api/v1/webhook/github",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    mock_github_client.get_pr_changes.assert_called_once_with("test/repo", 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
