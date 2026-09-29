"""
Pytest configuration and global fixtures.
Sets safe dummy environment variables before any application module is imported.
"""
import os

# Safe dummy environment variables for hermetic testing - must be set BEFORE any src import
os.environ.setdefault(
    "OPENAI_API_KEY", "sk-test-dummy-key-for-testing-purposes-only-32chars"
)
os.environ.setdefault("GEMINI_API_KEY", "dummy-gemini-key-for-testing")
os.environ.setdefault("GITHUB_TOKEN", "ghp_dummytokenfortesting12345678901234")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret-for-testing")
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing"
)
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-chars-for-testing"
)
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("ENABLE_AUTHENTICATION", "true")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$vCIXi9XBkX8dMyw2zYQCou4nh7dHOdoOC2XvQMl6kuGCoQFqVsIsm",
)

import pytest  # noqa: E402


@pytest.fixture
def auth_disabled(monkeypatch):
    """Fixture to temporarily disable authentication for tests checking unauthenticated bypass."""
    from src.config.settings import settings

    monkeypatch.setattr(settings, "enable_authentication", False)
