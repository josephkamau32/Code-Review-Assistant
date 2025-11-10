"""
Script to ingest historical code reviews from GitHub repositories
Run this once to populate your vector database with historical data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.github_client import GitHubClient
from src.rag.pipeline import RAGPipeline
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
    
    args = parser.parse_args()
    
    logger.info(f"Starting ingestion for repository: {args.repo}")
    
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
        
        # Ingest into vector database
        rag_pipeline.ingest_historical_reviews(reviews)
        
        # Show stats
        stats = rag_pipeline.get_stats()
        logger.info(f"Ingestion complete! Total reviews in DB: {stats['total_reviews']}")
        
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
