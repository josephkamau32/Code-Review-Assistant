import pytest
import warnings
from pydantic import ValidationError
from src.config.settings import Settings


def test_settings_load_with_dummy_env():
    """Verify settings can be loaded when dummy environment variables are present."""
    s = Settings(
        openai_api_key="sk-test-dummy-key-for-test-32charslong",
        llm_provider="openai",
    )
    assert s.openai_api_key == "sk-test-dummy-key-for-test-32charslong"
    assert s.llm_provider == "openai"
    assert s.api_port == 8000


def test_settings_missing_openai_key_raises():
    """Verify ValueError is raised if OPENAI_API_KEY is missing when provider is openai."""
    with pytest.raises((ValidationError, ValueError)) as exc_info:
        Settings(
            openai_api_key=None,
            llm_provider="openai",
        )
    assert "OPENAI_API_KEY must be set" in str(exc_info.value)


def test_settings_missing_gemini_key_raises():
    """Verify ValueError is raised if GEMINI_API_KEY is missing when provider is gemini."""
    with pytest.raises((ValidationError, ValueError)) as exc_info:
        Settings(
            gemini_api_key=None,
            llm_provider="gemini",
        )
    assert "GEMINI_API_KEY must be set" in str(exc_info.value)


def test_settings_invalid_provider_raises():
    """Verify ValueError is raised if an unsupported provider is configured."""
    with pytest.raises((ValidationError, ValueError)) as exc_info:
        Settings(
            openai_api_key="sk-dummy-key-test-32charslongdummy",
            llm_provider="unsupported_provider",
        )
    assert "Invalid LLM provider" in str(exc_info.value)


def test_settings_warns_on_weak_secret_in_production(monkeypatch):
    """Verify UserWarning is emitted when weak secret is provided in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.warns(UserWarning, match="is using a default or weak value"):
        Settings(
            openai_api_key="sk-dummy-key-test-32charslongdummy",
            secret_key="short",
        )
