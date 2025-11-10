import pytest
from src.models.schemas import CodeChange, CodeLanguage, HistoricalReview
from src.rag.embeddings import EmbeddingService
from datetime import datetime


def test_embedding_service():
    """Test embedding generation"""
    service = EmbeddingService()
    
    text = "def hello_world(): print('Hello, World!')"
    embedding = service.embed_text(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)


def test_code_change_model():
    """Test CodeChange model validation"""
    code_change = CodeChange(
        file_path="src/main.py",
        diff="+    print('new line')\n-    print('old line')",
        language=CodeLanguage.PYTHON,
        added_lines=1,
        removed_lines=1
    )
    
    assert code_change.file_path == "src/main.py"
    assert code_change.language == CodeLanguage.PYTHON


def test_historical_review_model():
    """Test HistoricalReview model"""
    review = HistoricalReview(
        pr_number=123,
        repository="test/repo",
        file_path="main.py",
        code_snippet="def test(): pass",
        review_comment="Consider adding docstring",
        reviewer="john_doe",
        comment_type="suggestion",
        language=CodeLanguage.PYTHON,
        created_at=datetime.now(),
        was_resolved=True
    )
    
    assert review.pr_number == 123
    assert review.comment_type == "suggestion"


@pytest.mark.asyncio
async def test_batch_embedding():
    """Test batch embedding generation"""
    service = EmbeddingService()
    
    texts = [
        "First code snippet",
        "Second code snippet",
        "Third code snippet"
    ]
    
    embeddings = service.embed_batch(texts)
    
    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)