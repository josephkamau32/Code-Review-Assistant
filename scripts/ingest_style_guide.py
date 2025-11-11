"""
Script to process and store coding style guides
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStoreManager
from src.models.schemas import HistoricalReview, CodeLanguage
from src.config.settings import settings
from datetime import datetime
from loguru import logger
import argparse
import hashlib


def chunk_style_guide(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split style guide into overlapping chunks"""
    if not text or not isinstance(text, str):
        return []

    chunks = []
    words = text.split()

    if len(words) <= chunk_size:
        return [text]  # Return as-is if smaller than chunk size

    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk = ' '.join(chunk_words)
        if chunk:  # Only add non-empty chunks
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
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk size in words"
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Overlap between chunks in words"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually storing data"
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.file):
        logger.error(f"Style guide file does not exist: {args.file}")
        sys.exit(1)

    if args.chunk_size <= 0 or args.chunk_size > 2000:
        logger.error("chunk-size must be between 1 and 2000")
        sys.exit(1)

    if args.overlap < 0 or args.overlap >= args.chunk_size:
        logger.error("overlap must be >= 0 and < chunk-size")
        sys.exit(1)

    # Validate language
    try:
        language_enum = CodeLanguage[args.language.upper()]
    except KeyError:
        logger.error(f"Unsupported language: {args.language}")
        sys.exit(1)

    logger.info(f"Ingesting style guide from: {args.file} (language: {args.language})")
    if args.dry_run:
        logger.info("DRY RUN MODE - No data will be stored")

    try:
        # Validate settings
        if not settings.openai_api_key:
            logger.error("OpenAI API key not configured. Check your .env file")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    try:
        # Read style guide with encoding detection
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1 for files with unknown encoding
            with open(args.file, 'r', encoding='latin-1') as f:
                content = f.read()
            logger.warning(f"File {args.file} has non-UTF-8 encoding, using latin-1")

        if not content.strip():
            logger.error("Style guide file is empty")
            sys.exit(1)

        # Generate content hash for deduplication
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        logger.info(f"Content hash: {content_hash[:8]}...")

        # Chunk the content
        chunks = chunk_style_guide(content, chunk_size=args.chunk_size, overlap=args.overlap)
        logger.info(f"Split style guide into {len(chunks)} chunks")

        if not chunks:
            logger.error("No valid chunks generated from style guide")
            sys.exit(1)

        # Initialize services
        embedding_service = EmbeddingService()
        vector_store = VectorStoreManager()

        # Process each chunk
        reviews = []
        for idx, chunk in enumerate(chunks):
            if len(chunk.strip()) < 10:  # Skip very short chunks
                continue

            review = HistoricalReview(
                pr_number=0,  # Style guide, not from PR
                repository="style-guide",
                file_path=f"style_guide_{args.language}_{content_hash[:8]}",
                code_snippet="",
                review_comment=chunk,
                reviewer="style-guide",
                comment_type="suggestion",
                language=language_enum,
                created_at=datetime.now(),
                was_resolved=True
            )
            reviews.append(review)

        if not reviews:
            logger.error("No valid reviews generated after filtering")
            sys.exit(1)

        logger.info(f"Generated {len(reviews)} review objects")

        if args.dry_run:
            logger.info("DRY RUN: Would store reviews but skipping storage")
            return

        # Generate embeddings in batches
        documents = [r.review_comment for r in reviews]
        embeddings = embedding_service.embed_batch(documents)

        # Store in vector database
        vector_store.add_reviews_batch(reviews, embeddings)

        logger.info(f"Successfully ingested style guide with {len(chunks)} chunks")

    except KeyboardInterrupt:
        logger.info("Ingestion interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during style guide ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()