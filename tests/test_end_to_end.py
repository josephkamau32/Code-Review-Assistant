"""
End-to-end test that validates the entire pipeline
Run this before deploying to production
"""

import pytest
import requests
from src.utils.github_client import GitHubClient
from src.rag.pipeline import RAGPipeline


def test_full_workflow():
    """Test complete workflow from ingestion to review"""
    from src.config.settings import settings

    # Skip test if GitHub token not configured
    if not settings.github_token or settings.github_token == "your_github_token_here":
        pytest.skip("GitHub token not configured - skipping integration test")

    # 1. Ingest sample data
    github_client = GitHubClient()
    pipeline = RAGPipeline()

    # Use a public repo for testing
    reviews = github_client.fetch_historical_reviews("django/django", max_prs=5)
    assert len(reviews) > 0, "Should fetch some reviews"

    pipeline.ingest_historical_reviews(reviews)

    # 2. Get a test PR
    pr = github_client.get_pr_changes("django/django", 15000)  # Known PR
    assert pr.pr_number == 15000

    # 3. Review it
    response = pipeline.review_pull_request(pr)

    # 4. Validate response
    assert response.pr_number == 15000
    assert isinstance(response.suggestions, list)
    assert response.processing_time_seconds > 0

    print(f"✅ Generated {len(response.suggestions)} suggestions")
    print(f"⏱️  Processing time: {response.processing_time_seconds}s")


def test_api_health():
    """Test that API is healthy"""
    response = requests.get("http://localhost:8000/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_webhook_signature_validation():
    """Test webhook signature validation"""
    from src.config.settings import settings

    # Skip test if webhook secret not configured
    if not settings.github_webhook_secret or settings.github_webhook_secret == "your_webhook_secret_here":
        pytest.skip("GitHub webhook secret not configured - skipping webhook test")

    import hmac
    import hashlib

    payload = b'{"action": "opened", "pull_request": {"number": 1}}'
    signature = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    response = requests.post(
        "http://localhost:8000/api/v1/webhook/github",
        data=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json"
        }
    )

    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
