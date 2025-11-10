"""
Script to process and store coding style guides
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStoreManager
from src.models.schemas import HistoricalReview, CodeLanguage
from datetime import datetime
from loguru import logger
import argparse


def chunk_style_guide(text: str, chunk_size: int = 500) -> list[str]:
    """Split style guide into overlapping chunks"""
    chunks = []
    words = text.split()
    
    for i in range(0, len(words), chunk_size - 50):  # 50 word overlap
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Ingest style guide")
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to style guide file (markdown, text, etc.)"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        choices=["python", "javascript", "typescript", "java", "go", "rust"],
        help="Programming language for this style guide"
    )
    
    args = parser.parse_args()
    
    logger.info(f"Ingesting style guide from: {args.file}")
    
    # Read style guide
    with open(args.file, 'r') as f:
        content = f.read()
    
    # Chunk the content
    chunks = chunk_style_guide(content)
    logger.info(f"Split style guide into {len(chunks)} chunks")
    
    # Initialize services
    embedding_service = EmbeddingService()
    vector_store = VectorStoreManager()
    
    # Process each chunk
    reviews = []
    for idx, chunk in enumerate(chunks):
        review = HistoricalReview(
            pr_number=0,  # Style guide, not from PR
            repository="style-guide",
            file_path=f"style_guide_{args.language}",
            code_snippet="",
            review_comment=chunk,
            reviewer="style-guide",
            comment_type="suggestion",
            language=CodeLanguage[args.language.upper()],
            created_at=datetime.now(),
            was_resolved=True
        )
        reviews.append(review)
    
    # Generate embeddings
    documents = [r.review_comment for r in reviews]
    embeddings = embedding_service.embed_batch(documents)
    
    # Store in vector database
    vector_store.add_reviews_batch(reviews, embeddings)
    
    logger.info(f"Successfully ingested style guide with {len(chunks)} chunks")


if __name__ == "__main__":
    main()