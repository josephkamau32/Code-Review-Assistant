from typing import List, Dict, Any
from loguru import logger
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStoreManager
from src.rag.llm_service import LLMService
from src.models.schemas import (
    PullRequest, ReviewSuggestion, ReviewResponse, CodeChange, HistoricalReview
)
from src.config.settings import settings
import time


class RAGPipeline:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreManager()
        self.llm_service = LLMService()
    
    def ingest_historical_reviews(self, reviews: List[HistoricalReview]):
        """Ingest historical reviews into the vector database"""
        if not reviews:
            logger.warning("No reviews to ingest")
            return

        logger.info(f"Ingesting {len(reviews)} historical reviews...")

        try:
            # Validate reviews
            valid_reviews = []
            for idx, review in enumerate(reviews):
                try:
                    # Validate required fields
                    if not review.review_comment or not review.repository:
                        logger.warning(f"Skipping review {idx}: missing required fields")
                        continue
                    
                    # Validate field lengths
                    if len(review.review_comment) > 10000:
                        logger.warning(f"Skipping review {idx}: comment too long ({len(review.review_comment)} chars)")
                        continue
                    
                    if review.code_snippet and len(review.code_snippet) > 50000:
                        logger.warning(f"Skipping review {idx}: code snippet too long ({len(review.code_snippet)} chars)")
                        continue
                    
                    valid_reviews.append(review)
                    
                except Exception as e:
                    logger.error(f"Error validating review {idx}: {e}")
                    continue

            if not valid_reviews:
                logger.error("No valid reviews after validation")
                return

            logger.info(f"Validated {len(valid_reviews)}/{len(reviews)} reviews")

            # Prepare documents for embedding
            documents = []
            for review in valid_reviews:
                # Sanitize and format document
                code_part = review.code_snippet.strip() if review.code_snippet else ""
                comment_part = review.review_comment.strip()
                doc = f"Code:\n{code_part}\n\nReview Comment:\n{comment_part}"
                documents.append(doc)

            # Generate embeddings in batch with error handling
            logger.info("Generating embeddings...")
            try:
                embeddings = self.embedding_service.embed_batch(documents)
            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
                raise

            if len(embeddings) != len(valid_reviews):
                logger.error(f"Embedding count mismatch: got {len(embeddings)}, expected {len(valid_reviews)}")
                raise ValueError("Embedding count mismatch")

            # Store in vector database
            logger.info("Storing in vector database...")
            try:
                self.vector_store.add_reviews_batch(valid_reviews, embeddings)
            except Exception as e:
                logger.error(f"Failed to store in vector database: {e}")
                raise

            logger.info(f"Successfully ingested {len(valid_reviews)} reviews")

        except Exception as e:
            logger.error(f"Error during review ingestion: {type(e).__name__} - {e}")
            raise
    
    def review_pull_request(
        self,
        pull_request: PullRequest,
        style_guide: str = ""
    ) -> ReviewResponse:
        """Main pipeline: Review a pull request using RAG"""
        start_time = time.time()
        all_suggestions = []
        
        # Validate input
        if not pull_request:
            raise ValueError("pull_request cannot be None")
        if not pull_request.changes:
            logger.warning(f"PR #{pull_request.pr_number} has no changes to review")
            return ReviewResponse(
                pr_number=pull_request.pr_number,
                repository=pull_request.repository,
                suggestions=[],
                summary="No code changes found to review.",
                processing_time_seconds=0.0
            )
        
        logger.info(f"Starting review for PR #{pull_request.pr_number} in {pull_request.repository} ({len(pull_request.changes)} files)")
        
        for code_change in pull_request.changes:
            # Skip files with no meaningful changes or non-code files
            if not code_change.diff or code_change.language == "other":
                continue
            
            # Step 1: Generate embedding for the code change
            code_context = f"File: {code_change.file_path}\nLanguage: {code_change.language.value}"
            logger.debug(f"DEBUG: Generating embedding for {code_change.file_path}, diff_length: {len(code_change.diff)}")
            query_embedding = self.embedding_service.embed_code_change(
                code_change.diff,
                context=code_context
            )
            logger.debug(f"DEBUG: Generated query embedding, length: {len(query_embedding)}")

            # Step 2: Retrieve similar past reviews
            filter_dict = {
                "language": code_change.language.value
            }

            logger.debug(f"DEBUG: Searching for similar reviews with filter: {filter_dict}")
            search_results = self.vector_store.search_similar_reviews(
                query_embedding=query_embedding,
                n_results=settings.top_k_results,
                filter_dict=filter_dict
            )

            # Format similar reviews for LLM context
            similar_reviews = []
            if search_results['documents'] and len(search_results['documents'][0]) > 0:
                logger.debug(f"DEBUG: Found {len(search_results['documents'][0])} similar reviews")
                for i, doc in enumerate(search_results['documents'][0]):
                    similar_reviews.append({
                        'document': doc,
                        'metadata': search_results['metadatas'][0][i],
                        'distance': search_results['distances'][0][i] if 'distances' in search_results else None
                    })
            else:
                logger.debug("DEBUG: No similar reviews found")
            
            # Step 3: Generate review using LLM with RAG context
            review_result = self.llm_service.generate_review(
                code_change=code_change,
                similar_reviews=similar_reviews,
                style_guide_context=style_guide
            )
            
            # Step 4: Parse suggestions
            for suggestion_data in review_result.get('suggestions', []):
                suggestion = ReviewSuggestion(
                    file_path=code_change.file_path,
                    line_number=suggestion_data.get('line_number'),
                    suggestion=suggestion_data['suggestion'],
                    severity=suggestion_data['severity'],
                    category=suggestion_data['category'],
                    confidence=suggestion_data.get('confidence', 0.8),
                    similar_past_reviews=[
                        sr['document'] for sr in similar_reviews[:2]
                    ]
                )
                all_suggestions.append(suggestion)
        
        # Generate overall summary
        summary = self.llm_service.generate_summary(all_suggestions)
        
        processing_time = time.time() - start_time
        
        response = ReviewResponse(
            pr_number=pull_request.pr_number,
            repository=pull_request.repository,
            suggestions=all_suggestions,
            summary=summary,
            processing_time_seconds=round(processing_time, 2)
        )
        
        logger.info(
            f"Review complete for PR #{pull_request.pr_number}. "
            f"Found {len(all_suggestions)} suggestions in {processing_time:.2f}s"
        )
        
        return response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return self.vector_store.get_collection_stats()