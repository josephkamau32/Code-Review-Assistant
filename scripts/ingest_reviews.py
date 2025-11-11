"""
Script to ingest historical code reviews from GitHub repositories
Run this once to populate your vector database with historical data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.github_client import GitHubClient
from src.rag.pipeline import RAGPipeline
from src.config.settings import settings
from loguru import logger
import argparse


def main():
    parser = argparse.ArgumentParser(description="Ingest historical code reviews")
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="Repository name (format: owner/repo)"
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        default=100,
        help="Maximum number of PRs to process"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for processing reviews"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually storing data"
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.repo or "/" not in args.repo:
        logger.error("Invalid repository format. Use: owner/repo")
        sys.exit(1)

    if args.max_prs <= 0 or args.max_prs > 1000:
        logger.error("max-prs must be between 1 and 1000")
        sys.exit(1)

    if args.batch_size <= 0 or args.batch_size > 200:
        logger.error("batch-size must be between 1 and 200")
        sys.exit(1)

    logger.info(f"Starting ingestion for repository: {args.repo} (max {args.max_prs} PRs, batch size {args.batch_size})")
    if args.dry_run:
        logger.info("DRY RUN MODE - No data will be stored")

    try:
        # Validate settings
        if not settings.github_token:
            logger.error("GitHub token not configured. Check your .env file")
            sys.exit(1)
        if not settings.openai_api_key:
            logger.error("OpenAI API key not configured. Check your .env file")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Initialize services
    github_client = GitHubClient()
    rag_pipeline = RAGPipeline()
    
    try:
        # Fetch historical reviews
        logger.info(f"Fetching historical reviews (max {args.max_prs} PRs)...")
        reviews = github_client.fetch_historical_reviews(
            repo_name=args.repo,
            max_prs=args.max_prs
        )

        if not reviews:
            logger.warning("No reviews found!")
            return

        logger.info(f"Found {len(reviews)} reviews")

        # Validate reviews before processing
        valid_reviews = []
        for review in reviews:
            try:
                # Basic validation
                if not review.review_comment or not review.repository:
                    logger.warning(f"Skipping invalid review: missing required fields")
                    continue
                if len(review.review_comment) > 10000:  # Reasonable limit
                    logger.warning(f"Skipping review with overly long comment ({len(review.review_comment)} chars)")
                    continue
                valid_reviews.append(review)
            except Exception as e:
                logger.warning(f"Error validating review: {e}")
                continue

        if not valid_reviews:
            logger.error("No valid reviews after validation!")
            return

        logger.info(f"Validated {len(valid_reviews)} reviews for ingestion")

        if args.dry_run:
            logger.info("DRY RUN: Would ingest reviews but skipping storage")
            return

        # Ingest into vector database in batches
        batch_size = args.batch_size
        total_processed = 0

        for i in range(0, len(valid_reviews), batch_size):
            batch = valid_reviews[i:i + batch_size]
            try:
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(valid_reviews) + batch_size - 1)//batch_size} ({len(batch)} reviews)")
                rag_pipeline.ingest_historical_reviews(batch)
                total_processed += len(batch)
                logger.info(f"Batch complete. Total processed: {total_processed}/{len(valid_reviews)}")
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                # Continue with next batch instead of failing completely
                continue

        # Show stats
        stats = rag_pipeline.get_stats()
        logger.info(f"Ingestion complete! Total reviews in DB: {stats['total_reviews']}")

    except KeyboardInterrupt:
        logger.info("Ingestion interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
