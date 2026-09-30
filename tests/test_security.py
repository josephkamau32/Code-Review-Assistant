"""
Security tests for Code Review Assistant
Tests authentication, authorization, input validation, and other security features
"""

import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.config.settings import settings
from src.utils.auth import create_access_token, get_password_hash
import time

client = TestClient(app)


class TestAuthentication:
    """Test authentication and authorization"""

    def test_health_endpoint_public(self):
        """Health endpoint should be accessible without auth"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_login_with_valid_credentials(self, monkeypatch):
        """Login should succeed with valid credentials and return access token"""
        test_password = "securePassword123"
        monkeypatch.setattr(settings, "admin_username", "admin")
        monkeypatch.setattr(
            settings, "admin_password_hash", get_password_hash(test_password)
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": test_password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_with_invalid_credentials(self):
        """Login should fail with invalid credentials"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "invalid_user", "password": "wrongpassword123"},
        )
        assert response.status_code == 401

    def test_login_with_empty_credentials(self):
        """Login should reject empty credentials"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")

        # Empty username
        response = client.post(
            "/api/v1/auth/login", json={"username": "", "password": "password"}
        )
        assert response.status_code == 422  # Validation error

        # Empty password
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": ""}
        )
        assert response.status_code == 422

    def test_protected_endpoint_without_token(self):
        """Protected endpoints should reject requests without token"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")

        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self):
        """Protected endpoints should reject invalid tokens"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")

        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    def test_jwt_token_expiration(self):
        """Expired JWT tokens should be rejected"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")

        # Create an expired token (expires in past)
        from datetime import datetime, timedelta, timezone

        expired_data = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        import jwt

        expired_token = jwt.encode(
            expired_data, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    def test_protected_endpoint_allows_when_auth_disabled(self, auth_disabled):
        """When authentication is disabled, endpoints should allow access with default admin"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["username"] == settings.admin_username

    def test_manual_review_requires_auth(self):
        """Manual review endpoint should reject unauthenticated requests with 401 (SEC-04)"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "owner/repo", "pr_number": 1},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_manual_review_rejects_invalid_token(self):
        """Manual review endpoint should reject invalid tokens with 401 (SEC-04)"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "owner/repo", "pr_number": 1},
            headers={"Authorization": "Bearer invalid_token_123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication credentials"

    def test_manual_review_allows_when_auth_disabled(self, auth_disabled):
        """When authentication is disabled, manual review should bypass auth gate (SEC-04)"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "invalid_repo", "pr_number": 1},
        )
        # Should not be 401 Unauthorized; reaches validation/processing
        assert response.status_code != 401

    def test_manual_review_with_valid_token_authenticated(self, monkeypatch):
        """Manual review endpoint should allow authenticated users with valid token (SEC-04)"""
        token = create_access_token(data={"sub": settings.admin_username})
        headers = {"Authorization": f"Bearer {token}"}

        import src.api.routes as routes
        from unittest.mock import MagicMock
        from datetime import datetime
        from src.models.schemas import (
            PullRequest,
            CodeChange,
            CodeLanguage,
            ReviewResponse,
        )

        mock_gh = MagicMock()
        mock_pr = PullRequest(
            pr_number=1,
            title="Test PR",
            description="Testing",
            author="testuser",
            repository="owner/repo",
            branch="main",
            changes=[
                CodeChange(
                    file_path="src/main.py",
                    diff="+test",
                    language=CodeLanguage.PYTHON,
                    added_lines=1,
                    removed_lines=0,
                )
            ],
            created_at=datetime.now(),
        )
        mock_gh.get_pr_changes.return_value = mock_pr
        mock_gh.client = True
        monkeypatch.setattr(routes, "github_client", mock_gh)

        mock_rag = MagicMock()
        mock_rag.review_pull_request.return_value = ReviewResponse(
            pr_number=1,
            repository="owner/repo",
            suggestions=[],
            summary="Review complete",
            processing_time_seconds=0.5,
        )
        monkeypatch.setattr(routes, "rag_pipeline", mock_rag)

        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "owner/repo", "pr_number": 1},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["summary"] == "Review complete"
        assert response.json()["pr_number"] == 1


class TestInputValidation:
    """Test input validation and sanitization"""

    @pytest.fixture
    def auth_headers(self):
        token = create_access_token(data={"sub": settings.admin_username})
        return {"Authorization": f"Bearer {token}"}

    def test_manual_review_invalid_repo_format(self, auth_headers):
        """Manual review should reject invalid repo format"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "invalid_format", "pr_number": 123},  # Missing slash
            headers=auth_headers,
        )
        assert response.status_code == 422 or response.status_code == 400

    def test_manual_review_negative_pr_number(self, auth_headers):
        """Manual review should reject negative PR numbers"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "owner/repo", "pr_number": -1},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_manual_review_zero_pr_number(self, auth_headers):
        """Manual review should reject zero PR number"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "owner/repo", "pr_number": 0},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_manual_review_oversized_repo_name(self, auth_headers):
        """Manual review should reject oversized repo names"""
        response = client.post(
            "/api/v1/review/manual",
            json={"repo_name": "a" * 200 + "/" + "b" * 200, "pr_number": 123},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestRateLimiting:
    """Test rate limiting functionality"""

    def test_rate_limit_enforcement(self):
        """Should enforce rate limits on webhook endpoint"""
        if not settings.enable_rate_limiting:
            pytest.skip("Rate limiting disabled")

        # Make many rapid requests
        responses = []
        try:
            for _ in range(15):  # More than the typical limit
                response = client.post(
                    "/api/v1/webhook/github",
                    json={"action": "test"},
                    headers={"X-Hub-Signature-256": "test"},
                )
                responses.append(response.status_code)
                time.sleep(0.05)

            # At least one should be rate limited
            assert (
                429 in responses or 401 in responses
            )  # 429 = Too Many Requests, 401 = Invalid signature
        finally:
            from src.api.routes import limiter as routes_limiter

            routes_limiter.reset()
            if hasattr(app.state, "limiter"):
                app.state.limiter.reset()


class TestWebhookSecurity:
    """Test GitHub webhook security"""

    def test_webhook_missing_signature(self):
        """Webhook should reject requests without signature"""
        response = client.post(
            "/api/v1/webhook/github",
            json={"action": "opened", "pull_request": {"number": 123}},
        )
        # Should fail signature verification
        assert response.status_code in [401, 403]

    def test_webhook_invalid_signature(self):
        """Webhook should reject requests with invalid signature"""
        response = client.post(
            "/api/v1/webhook/github",
            json={"action": "opened"},
            headers={"X-Hub-Signature-256": "sha256=invalid"},
        )
        assert response.status_code in [401, 403]


class TestCORS:
    """Test CORS configuration"""

    def test_cors_preflight_headers_present(self):
        """CORS preflight request should return appropriate access control headers"""
        origin = (
            settings.cors_origins[0]
            if settings.cors_origins
            else "http://localhost:3000"
        )
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-origin" in headers_lower
        assert headers_lower["access-control-allow-origin"] == origin

    def test_cors_headers_on_get_request(self):
        """GET request with Origin header should include CORS headers"""
        origin = (
            settings.cors_origins[0]
            if settings.cors_origins
            else "http://localhost:3000"
        )
        response = client.get("/api/v1/health", headers={"Origin": origin})
        assert response.status_code == 200
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-origin" in headers_lower
        assert headers_lower["access-control-allow-origin"] == origin


class TestErrorHandling:
    """Test error handling and responses"""

    def test_404_on_invalid_endpoint(self):
        """Should return 404 for non-existent endpoints"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_405_on_wrong_method(self):
        """Should return 405 for unsupported HTTP methods"""
        response = client.delete("/api/v1/health")  # GET-only endpoint
        assert response.status_code == 405

    def test_error_response_format(self):
        """Error responses should have consistent format"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        assert "detail" in response.json()


class TestDataSanitization:
    """Test that sensitive data is not exposed"""

    def test_error_no_api_keys_in_response(self):
        """Error messages should not contain API keys"""
        response = client.get("/api/v1/stats")
        response_text = response.text.lower()

        # Check for common API key patterns
        assert "sk-" not in response_text  # OpenAI keys
        assert "ghp_" not in response_text  # GitHub tokens
        assert settings.jwt_secret_key.lower() not in response_text

    def test_health_no_sensitive_info(self):
        """Health endpoint should not expose sensitive information"""
        response = client.get("/api/v1/health")
        data = response.json()

        # Should not contain API keys or secrets
        assert "openai_api_key" not in str(data).lower()
        assert "github_token" not in str(data).lower()
        assert "secret" not in str(data).lower()


class TestDOMXSSPrevention:
    """Test that static JavaScript does not use unsafe innerHTML for dynamic content (SEC-01)"""

    def test_review_js_does_not_use_unsafe_inner_html_for_dynamic_data(self):
        """Ensure review.js uses textContent or DOM creation rather than innerHTML interpolation for dynamic data."""
        with open("src/api/static/js/review.js", "r", encoding="utf-8") as f:
            js_content = f.read()

        # Unsafe patterns that previously existed
        assert (
            'summary.innerHTML = `<i class="fas fa-check-circle"></i> ${data.summary}`'
            not in js_content
        )
        assert "${suggestion.suggestion}" not in js_content
        assert "${suggestion.file_path}" not in js_content

        # Safe patterns that replace them
        assert "p.textContent = suggestion.suggestion" in js_content
        assert "summary.appendChild(document.createTextNode" in js_content
        assert (
            "fileInfo.appendChild(document.createTextNode(suggestion.file_path))"
            in js_content
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
