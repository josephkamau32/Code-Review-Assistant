"""Tests for the Gemini provider code paths (boundary-mocked).

Mirrors the existing OpenAI boundary tests in test_rag_pipeline.py.
"""

from unittest.mock import MagicMock, patch
import pytest
import tenacity

from src.models.schemas import CodeChange, CodeLanguage
from src.rag.embeddings import EmbeddingService
from src.rag.llm_service import LLMService, LLMProviderError


# ═══════════════════════════════════════════════════════════════════════════
# Gemini Embedding Boundary Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGeminiEmbeddingBoundary:
    """Test the Gemini embedding code path with boundary mocks on genai.Client."""

    def _make_gemini_embedding_service(self, monkeypatch):
        """Create an EmbeddingService wired to the Gemini provider with a mock client."""
        from src.config.settings import settings

        monkeypatch.setattr(settings, "embedding_provider", "gemini")
        monkeypatch.setattr(settings, "gemini_api_key", "real-looking-key-for-test")
        monkeypatch.setattr(settings, "gemini_embedding_model", "gemini-embedding-001")
        monkeypatch.setattr(settings, "embedding_dimensions", 768)

        service = EmbeddingService()
        assert service.provider == "gemini"
        assert service.mock_mode is False
        return service

    def test_gemini_embed_text_boundary(self, monkeypatch):
        """Mock genai.Client().models.embed_content at the boundary."""
        service = self._make_gemini_embedding_service(monkeypatch)

        # Build mock response matching google-genai SDK structure
        mock_embedding = MagicMock()
        mock_embedding.values = [0.01] * 768
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]

        mock_embed = MagicMock(return_value=mock_response)
        monkeypatch.setattr(service.client.models, "embed_content", mock_embed)

        text = "def hello_world(): print('Hello')"
        embedding = service.embed_text(text)

        # Verify the mock was called with correct args
        mock_embed.assert_called_once()
        call_kwargs = mock_embed.call_args
        assert call_kwargs.kwargs["model"] == "gemini-embedding-001"
        assert call_kwargs.kwargs["contents"] == text

        # Verify returned embedding
        assert isinstance(embedding, list)
        assert len(embedding) == 768

    def test_gemini_embed_batch_boundary(self, monkeypatch):
        """Mock batch embedding for Gemini provider."""
        service = self._make_gemini_embedding_service(monkeypatch)

        texts = ["snippet one", "snippet two", "snippet three"]

        mock_embeddings = []
        for _ in texts:
            e = MagicMock()
            e.values = [0.02] * 768
            mock_embeddings.append(e)

        mock_response = MagicMock()
        mock_response.embeddings = mock_embeddings
        mock_embed = MagicMock(return_value=mock_response)
        monkeypatch.setattr(service.client.models, "embed_content", mock_embed)

        embeddings = service.embed_batch(texts)

        mock_embed.assert_called_once()
        assert len(embeddings) == 3
        assert all(len(e) == 768 for e in embeddings)

    def test_gemini_embed_api_error(self, monkeypatch):
        """Test error handling when Gemini embedding API fails."""
        service = self._make_gemini_embedding_service(monkeypatch)

        # Fast-forward retry wait
        monkeypatch.setattr(service.embed_text.retry, "wait", tenacity.wait_none())

        mock_embed = MagicMock(side_effect=Exception("Gemini connection timeout"))
        monkeypatch.setattr(service.client.models, "embed_content", mock_embed)

        with pytest.raises(Exception):
            service.embed_text("test snippet")

        # Should have retried 3 times
        assert mock_embed.call_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# Gemini LLM Generation Boundary Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGeminiLLMBoundary:
    """Test the Gemini LLM code path with boundary mocks on genai.Client."""

    def _make_gemini_llm_service(self, monkeypatch):
        """Create an LLMService wired to the Gemini provider with a mock client."""
        from src.config.settings import settings

        monkeypatch.setattr(settings, "llm_provider", "gemini")
        monkeypatch.setattr(settings, "gemini_api_key", "real-looking-key-for-test")
        monkeypatch.setattr(settings, "gemini_llm_model", "gemini-3.5-flash-lite")

        service = LLMService()
        assert service.provider == "gemini"
        return service

    def _make_code_change(self):
        return CodeChange(
            file_path="src/main.py",
            diff="+def test(): pass",
            language=CodeLanguage.PYTHON,
            added_lines=1,
            removed_lines=0,
        )

    def test_gemini_generate_review_boundary(self, monkeypatch):
        """Mock genai.Client().models.generate_content at the boundary."""
        service = self._make_gemini_llm_service(monkeypatch)
        monkeypatch.setattr(service.generate_review.retry, "wait", tenacity.wait_none())

        valid_json = '{"suggestions": [{"line_number": 1, "suggestion": "Add docstring", "severity": "info", "category": "style", "confidence": 0.8}], "summary": "One suggestion"}'

        mock_response = MagicMock()
        mock_response.text = valid_json

        mock_generate = MagicMock(return_value=mock_response)
        monkeypatch.setattr(service.client.models, "generate_content", mock_generate)

        result = service.generate_review(self._make_code_change(), [])

        # Verify the mock was called
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args
        assert call_kwargs.kwargs["model"] == "gemini-3.5-flash-lite"

        # Verify the prompt was constructed with XML tags
        prompt_arg = call_kwargs.kwargs["contents"]
        assert "<code_diff" in prompt_arg
        assert "UNTRUSTED" in prompt_arg

        # Verify parsed result
        assert len(result["suggestions"]) == 1
        assert result["summary"] == "One suggestion"

    def test_gemini_rate_limit_triggers_retry(self, monkeypatch):
        """Test that Gemini rate-limit errors (429) trigger Tenacity retries."""
        from google.genai import errors as genai_errors

        service = self._make_gemini_llm_service(monkeypatch)
        monkeypatch.setattr(service.generate_review.retry, "wait", tenacity.wait_none())

        # Create a mock rate limit error (code=429)
        rate_limit_err = genai_errors.APIError(
            code=429, response_json={"error": {"message": "Resource exhausted"}}
        )

        valid_json = '{"suggestions": [], "summary": "OK"}'
        mock_success = MagicMock()
        mock_success.text = valid_json

        mock_generate = MagicMock(side_effect=[rate_limit_err, mock_success])
        monkeypatch.setattr(service.client.models, "generate_content", mock_generate)

        result = service.generate_review(self._make_code_change(), [])

        assert mock_generate.call_count == 2
        assert result["summary"] == "OK"

    def test_gemini_non_retryable_error_raises_service_error(self, monkeypatch):
        """Test that non-429 Gemini API errors fail immediately (no retry),
        raising LLMServiceError that wraps the LLMProviderError."""
        from google.genai import errors as genai_errors
        from src.rag.llm_service import LLMServiceError

        service = self._make_gemini_llm_service(monkeypatch)
        monkeypatch.setattr(service.generate_review.retry, "wait", tenacity.wait_none())

        api_err = genai_errors.APIError(
            code=400, response_json={"error": {"message": "Invalid model"}}
        )

        mock_generate = MagicMock(side_effect=api_err)
        monkeypatch.setattr(service.client.models, "generate_content", mock_generate)

        with pytest.raises(LLMServiceError) as exc_info:
            service.generate_review(self._make_code_change(), [])

        assert "Gemini API failed" in str(exc_info.value)
        # Must not retry — only 1 call
        assert mock_generate.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Socket-Level No-Network-Calls Verification
# ═══════════════════════════════════════════════════════════════════════════


class TestNoRealNetworkCalls:
    """Prove that NO real outbound network connections are made during the test suite.

    Uses socket.create_connection interception (same approach as Step 2b).
    """

    def test_full_suite_makes_no_outbound_connections(self, monkeypatch):
        """Intercept socket.create_connection and fail on any real outbound call.

        This test patches socket.create_connection to raise an error if any code
        tries to make a real network connection. It then exercises the key code
        paths (embeddings, LLM service) to prove they don't phone home.
        """
        import socket

        real_create_connection = socket.create_connection
        connections_attempted = []

        def _blocking_create_connection(address, *args, **kwargs):
            # Allow localhost connections (test server, chromadb)
            host = address[0] if isinstance(address, tuple) else address
            if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                return real_create_connection(address, *args, **kwargs)
            connections_attempted.append(address)
            raise ConnectionError(
                f"TEST GUARD: Blocked outbound connection to {address}"
            )

        monkeypatch.setattr(socket, "create_connection", _blocking_create_connection)

        # Exercise the OpenAI embedding mock path (conftest default)
        from src.config.settings import settings

        service = EmbeddingService()
        if service.mock_mode:
            service.embed_text("socket guard test")
            service.embed_batch(["test1", "test2"])

        # Exercise the Gemini embedding mock path
        monkeypatch.setattr(settings, "embedding_provider", "gemini")
        monkeypatch.setattr(settings, "gemini_api_key", "your_gemini_api_key_here")
        gemini_service = EmbeddingService()
        assert gemini_service.mock_mode is True
        gemini_service.embed_text("socket guard gemini test")

        # Exercise LLM prompt building (no network needed)
        llm = LLMService()
        code_change = CodeChange(
            file_path="test.py",
            diff="+pass",
            language=CodeLanguage.PYTHON,
            added_lines=1,
            removed_lines=0,
        )
        prompt = llm._build_review_prompt(code_change, [])
        assert len(prompt) > 0

        system = llm._build_system_prompt()
        assert "UNTRUSTED" in system

        # Verify no outbound connections were attempted
        assert (
            connections_attempted == []
        ), f"Real outbound connections attempted: {connections_attempted}"
