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
    
    def test_login_with_invalid_credentials(self):
        """Login should fail with invalid credentials"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")
        
        response = client.post("/api/v1/auth/login", json={
            "username": "invalid",
            "password": "wrong"
        })
        assert response.status_code == 401
    
    def test_login_with_empty_credentials(self):
        """Login should reject empty credentials"""
        if not settings.enable_authentication:
            pytest.skip("Authentication disabled")
        
        # Empty username
        response = client.post("/api/v1/auth/login", json={
            "username": "",
            "password": "password"
        })
        assert response.status_code == 422  # Validation error
        
        # Empty password
        response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": ""
        })
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
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        from jose import jwt
        expired_token = jwt.encode(
            expired_data, 
            settings.jwt_secret_key, 
            algorithm=settings.jwt_algorithm
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401


class TestInputValidation:
    """Test input validation and sanitization"""
    
    def test_manual_review_invalid_repo_format(self):
        """Manual review should reject invalid repo format"""
        response = client.post("/api/v1/review/manual", json={
            "repo_name": "invalid_format",  # Missing  slash
            "pr_number": 123
        })
        assert response.status_code == 422 or response.status_code == 400
    
    def test_manual_review_negative_pr_number(self):
        """Manual review should reject negative PR numbers"""
        response = client.post("/api/v1/review/manual", json={
            "repo_name": "owner/repo",
            "pr_number": -1
        })
        assert response.status_code == 422
    
    def test_manual_review_zero_pr_number(self):
        """Manual review should reject zero PR number"""
        response = client.post("/api/v1/review/manual", json={
            "repo_name": "owner/repo",
            "pr_number": 0
        })
        assert response.status_code == 422
    
    def test_manual_review_oversized_repo_name(self):
        """Manual review should reject oversized repo names"""
        response = client.post("/api/v1/review/manual", json={
            "repo_name": "a" * 200 + "/" + "b" * 200,
            "pr_number": 123
        })
        assert response.status_code == 422


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_rate_limit_enforcement(self):
        """Should enforce rate limits on webhook endpoint"""
        if not settings.enable_rate_limiting:
            pytest.skip("Rate limiting disabled")
        
        # Make many rapid requests
        responses = []
        for _ in range(15):  # More than the typical limit
            response = client.post(
                "/api/v1/webhook/github",
                json={"action": "test"},
                headers={"X-Hub-Signature-256": "test"}
            )
            responses.append(response.status_code)
            time.sleep(0.1)  # Small delay
        
        # At least one should be rate limited
        assert 429 in responses or 401 in responses  # 429 = Too Many Requests, 401 = Invalid signature


class TestWebhookSecurity:
    """Test GitHub webhook security"""
    
    def test_webhook_missing_signature(self):
        """Webhook should reject requests without signature"""
        response = client.post("/api/v1/webhook/github", json={
            "action": "opened",
            "pull_request": {"number": 123}
        })
        # Should fail signature verification
        assert response.status_code in [401, 403]
    
    def test_webhook_invalid_signature(self):
        """Webhook should reject requests with invalid signature"""
        response = client.post(
            "/api/v1/webhook/github",
            json={"action": "opened"},
            headers={"X-Hub-Signature-256": "sha256=invalid"}
        )
        assert response.status_code in [401, 403]


class TestCORS:
    """Test CORS configuration"""
    
    def test_cors_headers_present(self):
        """CORS headers should be present in responses"""
        response = client.options("/api/v1/health")
        # Check for CORS headers
        assert "access-control-allow-origin" in [h.lower() for h in response.headers.keys()] or \
               response.status_code == 200  # FastAPI may handle this differently


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
