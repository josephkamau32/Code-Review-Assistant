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


def test_full_workflow(monkeypatch):
    """Test complete workflow from ingestion to review hermetically (TEST-02)"""
    # Skip test if GitHub token not configured or placeholder
    if not settings.github_token or settings.github_token == "your_github_token_here":
        pytest.skip("GitHub token not configured - skipping integration test")

    sample_reviews = [
        HistoricalReview(
            pr_number=14999,
            repository="django/django",
            file_path="django/core/handlers/base.py",
            code_snippet="def load_middleware(self):\n    pass",
            review_comment="Ensure middleware exception handling is preserved.",
            reviewer="django_reviewer",
            comment_type="suggestion",
            language=CodeLanguage.PYTHON,
            created_at=datetime.now(),
            was_resolved=True,
        )
    ]
    sample_pr = PullRequest(
        pr_number=15000,
        title="Refactor middleware handling",
        description="Clean up middleware loading logic",
        author="contributor",
        repository="django/django",
        branch="feature/middleware",
        changes=[
            CodeChange(
                file_path="django/core/handlers/base.py",
                diff="+def load_middleware(self):\n+    self._middleware_chain = handler",
                language=CodeLanguage.PYTHON,
                added_lines=2,
                removed_lines=0,
            )
        ],
        created_at=datetime.now(),
    )

    if (
        settings.github_token.startswith("ghp_dummy")
        or settings.environment == "testing"
    ):
        monkeypatch.setattr(
            GitHubClient,
            "fetch_historical_reviews",
            lambda self, repo, max_prs=100: sample_reviews,
        )
        monkeypatch.setattr(
            GitHubClient,
            "get_pr_changes",
            lambda self, repo, pr_num: sample_pr,
        )

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


def test_webhook_signature_validation():
    """Test webhook signature validation using TestClient (TEST-03)"""
    if (
        not settings.github_webhook_secret
        or settings.github_webhook_secret == "your_webhook_secret_here"
    ):
        pytest.skip("GitHub webhook secret not configured - skipping webhook test")

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
