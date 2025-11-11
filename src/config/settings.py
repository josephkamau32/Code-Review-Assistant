from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Keys
    openai_api_key: Optional[str] = None
    github_token: Optional[str] = None
    github_webhook_secret: Optional[str] = None
    
    # Database
    chroma_persist_directory: str = "./data/vector_db"
    chroma_collection_name: str = "code_reviews"
    
    # Model Settings
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4-turbo-preview"
    temperature: float = 0.3
    max_tokens: int = 1000
    
    # Retrieval
    top_k_results: int = 5
    similarity_threshold: float = 0.7
    
    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()