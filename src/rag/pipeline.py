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
        logger.info(f"Ingesting {len(reviews)} historical reviews...")
        
        # Prepare documents for embedding
        documents = []
        for review in reviews:
            doc = f"Code:\n{review.code_snippet}\n\nReview Comment:\n{review.review_comment}"
            documents.append(doc)
        
        # Generate embeddings in batch
        logger.info("Generating embeddings...")
        embeddings = self.embedding_service.embed_batch(documents)
        
        # Store in vector database
        logger.info("Storing in vector database...")
        self.vector_store.add_reviews_batch(reviews, embeddings)
        
        logger.info(f"Successfully ingested {len(reviews)} reviews")
    
    def review_pull_request(
        self,
        pull_request: PullRequest,
        style_guide: str = ""
    ) -> ReviewResponse:
        """Main pipeline: Review a pull request using RAG"""
        start_time = time.time()
        all_suggestions = []
        
        logger.info(f"Starting review for PR #{pull_request.pr_number} in {pull_request.repository}")
        
        for code_change in pull_request.changes:
            # Skip files with no meaningful changes or non-code files
            if not code_change.diff or code_change.language == "other":
                continue
            
            # Step 1: Generate embedding for the code change
            code_context = f"File: {code_change.file_path}\nLanguage: {code_change.language.value}"
            query_embedding = self.embedding_service.embed_code_change(
                code_change.diff,
                context=code_context
            )
            
            # Step 2: Retrieve similar past reviews
            filter_dict = {
                "language": code_change.language.value
            }
            
            search_results = self.vector_store.search_similar_reviews(
                query_embedding=query_embedding,
                n_results=settings.top_k_results,
                filter_dict=filter_dict
            )
            
            # Format similar reviews for LLM context
            similar_reviews = []
            if search_results['documents'] and len(search_results['documents'][0]) > 0:
                for i, doc in enumerate(search_results['documents'][0]):
                    similar_reviews.append({
                        'document': doc,
                        'metadata': search_results['metadatas'][0][i],
                        'distance': search_results['distances'][0][i] if 'distances' in search_results else None
                    })
            
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