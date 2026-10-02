"""Tests for CodeRabbit review follow-up fixes (PR #4).

Each test class corresponds to one of the 6 CodeRabbit comments.
"""

import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError
from src.config.settings import Settings


# -- Fix 1: Settings validation covers embedding_provider independently ------


class TestEmbeddingProviderKeyValidation:
    """CodeRabbit: settings.py - validate embedding_provider key independently."""

    def test_openai_llm_missing_gemini_embed_key_raises_outside_testing(
        self, monkeypatch
    ):
        """LLM_PROVIDER=openai + real OPENAI key + EMBEDDING_PROVIDER=gemini + no GEMINI key
        + ENVIRONMENT != testing -> must raise."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings(
                openai_api_key="sk-test-dummy-key-for-test-32charslong",
                gemini_api_key=None,
                llm_provider="openai",
                embedding_provider="gemini",
                _env_file=None,
            )
        assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_default_gemini_embedding_missing_key_raises_outside_testing(
        self, monkeypatch
    ):
        """When embedding_provider is omitted (defaults to 'gemini') and llm_provider='openai',
        missing GEMINI_API_KEY outside testing must raise (the exact default-config case CodeRabbit flagged).
        """
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings(
                openai_api_key="sk-test-dummy-key-for-test-32charslong",
                gemini_api_key=None,
                llm_provider="openai",
                _env_file=None,
            )
        assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_full_default_config_missing_gemini_key_raises_outside_testing(
        self, monkeypatch
    ):
        """When both llm_provider and embedding_provider take their production defaults ('gemini'),
        missing GEMINI_API_KEY outside testing must raise."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings(
                gemini_api_key=None,
                _env_file=None,
            )
        assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_same_config_with_environment_testing_does_not_raise(self, monkeypatch):
        """Same config but ENVIRONMENT=testing -> settings loads without error."""
        monkeypatch.setenv("ENVIRONMENT", "testing")

        s = Settings(
            openai_api_key="sk-test-dummy-key-for-test-32charslong",
            gemini_api_key=None,
            llm_provider="openai",
            embedding_provider="gemini",
            _env_file=None,
        )
        assert s.embedding_provider == "gemini"

    def test_invalid_embedding_provider_raises_at_load_time(self, monkeypatch):
        """embedding_provider must be 'openai' or 'gemini' - reject others at load."""
        monkeypatch.setenv("ENVIRONMENT", "testing")

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            Settings(
                openai_api_key="sk-test-dummy-key-for-test-32charslong",
                llm_provider="openai",
                embedding_provider="huggingface",
                _env_file=None,
            )
        assert (
            "embedding_provider" in str(exc_info.value).lower()
            or "huggingface" in str(exc_info.value).lower()
        )

    def test_existing_settings_test_still_passes(self, monkeypatch):
        """Existing test: openai provider with openai key loads fine."""
        monkeypatch.setenv("ENVIRONMENT", "testing")

        s = Settings(
            openai_api_key="sk-test-dummy-key-for-test-32charslong",
            llm_provider="openai",
            embedding_provider="openai",
            _env_file=None,
        )
        assert s.llm_provider == "openai"


# -- Fix 2: Collection name includes embedding_dimensions --------------------


class TestCollectionNameIncludesDimensions:
    """CodeRabbit: vector_store.py - include dimensions in collection name."""

    def test_different_dimensions_produce_different_names(self, monkeypatch):
        """Changing embedding_dimensions must produce a different collection name."""
        from src.config.settings import settings
        from src.rag.vector_store import _namespaced_collection_name

        monkeypatch.setattr(settings, "embedding_provider", "gemini")
        monkeypatch.setattr(settings, "gemini_embedding_model", "gemini-embedding-001")

        monkeypatch.setattr(settings, "embedding_dimensions", 768)
        name_768 = _namespaced_collection_name()

        monkeypatch.setattr(settings, "embedding_dimensions", 256)
        name_256 = _namespaced_collection_name()

        assert name_768 != name_256
        assert "768d" in name_768
        assert "256d" in name_256

    def test_collection_name_within_63_chars(self, monkeypatch):
        """Name must stay within ChromaDB's 63-char limit even with long model tags."""
        from src.config.settings import settings
        from src.rag.vector_store import _namespaced_collection_name

        monkeypatch.setattr(settings, "embedding_provider", "openai")
        monkeypatch.setattr(
            settings,
            "embedding_model",
            "a-very-long-model-name-that-could-exceed-limits-easily",
        )
        monkeypatch.setattr(settings, "embedding_dimensions", 3072)
        monkeypatch.setattr(settings, "chroma_collection_name", "code_reviews")

        name = _namespaced_collection_name()
        assert len(name) <= 63
        assert "3072d" in name


# -- Fix 3: 5xx Gemini errors trigger retry ----------------------------------


class TestGemini5xxRetry:
    """CodeRabbit: llm_service.py - re-raise 5xx so Tenacity retries them."""

    def _make_gemini_llm_service(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "llm_provider", "gemini")
        monkeypatch.setattr(settings, "gemini_api_key", "real-looking-key-for-test")
        monkeypatch.setattr(settings, "gemini_llm_model", "gemini-3.5-flash-lite")

        from src.rag.llm_service import LLMService

        service = LLMService()
        assert service.provider == "gemini"
        return service

    def _make_code_change(self):
        from src.models.schemas import CodeChange, CodeLanguage

        return CodeChange(
            file_path="src/main.py",
            diff="+def test(): pass",
            language=CodeLanguage.PYTHON,
            added_lines=1,
            removed_lines=0,
        )

    def test_503_triggers_retry_then_succeeds(self, monkeypatch):
        """A 503 APIError followed by success should retry and return the result."""
        import tenacity
        from google.genai import errors as genai_errors

        service = self._make_gemini_llm_service(monkeypatch)
        monkeypatch.setattr(service.generate_review.retry, "wait", tenacity.wait_none())

        err_503 = genai_errors.APIError(
            code=503, response_json={"error": {"message": "Service Unavailable"}}
        )

        valid_json = '{"suggestions": [], "summary": "OK after retry"}'
        mock_success = MagicMock()
        mock_success.text = valid_json

        mock_generate = MagicMock(side_effect=[err_503, mock_success])
        monkeypatch.setattr(service.client.models, "generate_content", mock_generate)

        result = service.generate_review(self._make_code_change(), [])

        assert mock_generate.call_count == 2
        assert result["summary"] == "OK after retry"

    def test_400_fails_fast_no_retry(self, monkeypatch):
        """A 400 APIError (non-retryable client error) must fail immediately."""
        import tenacity
        from google.genai import errors as genai_errors
        from src.rag.llm_service import LLMServiceError

        service = self._make_gemini_llm_service(monkeypatch)
        monkeypatch.setattr(service.generate_review.retry, "wait", tenacity.wait_none())

        err_400 = genai_errors.APIError(
            code=400, response_json={"error": {"message": "Invalid model"}}
        )

        mock_generate = MagicMock(side_effect=err_400)
        monkeypatch.setattr(service.client.models, "generate_content", mock_generate)

        with pytest.raises(LLMServiceError) as exc_info:
            service.generate_review(self._make_code_change(), [])

        assert "Gemini API failed" in str(exc_info.value)
        assert mock_generate.call_count == 1


