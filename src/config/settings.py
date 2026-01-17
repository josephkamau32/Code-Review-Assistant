from pydantic_settings import BaseSettings
from pydantic import validator, field_validator, model_validator
from typing import Optional, List
import secrets
import os


class Settings(BaseSettings):
    # API Keys
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    github_token: Optional[str] = None
    github_webhook_secret: Optional[str] = None

    # Provider Selection
    llm_provider: str = "openai"  # "openai" or "gemini"

    # Database
    chroma_persist_directory: str = "./data/vector_db"
    chroma_collection_name: str = "code_reviews"

    # Model Settings
    embedding_model: str = "text-embedding-3-small"
    gemini_embedding_model: str = "models/embedding-001"
    llm_model: str = "gpt-4-turbo-preview"
    gemini_llm_model: str = "gemini-1.5-flash"
    temperature: float = 0.3
    max_tokens: int = 1000

    # Retrieval
    top_k_results: int = 5
    similarity_threshold: float = 0.7

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Security Settings
    secret_key: str = secrets.token_urlsafe(32)
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # Redis (for caching and rate limiting)
    redis_url: str = "redis://localhost:6379"

    # Database (for user management and feedback)
    database_url: str = "sqlite:///./data/app.db"

    # Feature Flags
    enable_authentication: bool = False  # Disabled until admin password is set
    enable_rate_limiting: bool = True
    enable_caching: bool = True
    enable_monitoring: bool = True

    # Admin Settings
    admin_username: str = "admin"
    admin_password_hash: Optional[str] = None  # Will be set during setup

    # Monitoring
    enable_prometheus: bool = True
    log_level: str = "INFO"

    @model_validator(mode='after')
    def validate_api_keys(self):
        """Validate that required API keys are set based on provider"""
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set when using OpenAI provider")
        elif self.llm_provider == "gemini":
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY must be set when using Gemini provider")
        else:
            raise ValueError(f"Invalid LLM provider: {self.llm_provider}. Must be 'openai' or 'gemini'")
        
        return self

    @validator('secret_key', 'jwt_secret_key', pre=True, always=True)
    def warn_default_secrets(cls, v, field):
        """Warn if using default/random secrets in production"""
        if os.getenv('ENVIRONMENT') == 'production' and (not v or len(v) < 32):
            import warnings
            warnings.warn(
                f"{field.name} is using a default or weak value. "
                "Please set a strong secret in production!",
                UserWarning
            )
        return v or secrets.token_urlsafe(32)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()