import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config.settings import settings
from src.models.schemas import HistoricalReview
import json


class VectorStoreManager:
    def __init__(self):
        self.client = chromadb.Client(
            ChromaSettings(
                persist_directory=settings.chroma_persist_directory,
                anonymized_telemetry=False
            )
        )
        self.collection = self._get_or_create_collection()
        
    def _get_or_create_collection(self):
        """Get existing collection or create new one"""
        try:
            collection = self.client.get_collection(
                name=settings.chroma_collection_name
            )
            logger.info(f"Loaded existing collection: {settings.chroma_collection_name}")
        except Exception:
            collection = self.client.create_collection(
                name=settings.chroma_collection_name,
                metadata={"description": "Historical code reviews for RAG"}
            )
            logger.info(f"Created new collection: {settings.chroma_collection_name}")
        return collection
    
    def add_review(self, review: HistoricalReview, embedding: List[float]) -> str:
        """Add a single review to the vector store"""
        doc_id = f"{review.repository}_{review.pr_number}_{review.file_path}_{review.created_at.timestamp()}"

        metadata = {
            "pr_number": review.pr_number,
            "repository": review.repository,
            "file_path": review.file_path,
            "reviewer": review.reviewer,
            "comment_type": review.comment_type,
            "language": review.language.value,
            "was_resolved": review.was_resolved,
            "created_at": review.created_at.isoformat()
        }

        # Combine code snippet and review for better context
        document = f"Code:\n{review.code_snippet}\n\nReview Comment:\n{review.review_comment}"

        logger.debug(f"DEBUG: Adding review to vector store - doc_id: {doc_id}, embedding_len: {len(embedding)}")
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata]
        )

        logger.debug(f"DEBUG: Successfully added review to vector store: {doc_id}")
        return doc_id
    
    def add_reviews_batch(self, reviews: List[HistoricalReview], embeddings: List[List[float]]):
        """Add multiple reviews in batch (more efficient)"""
        if len(reviews) != len(embeddings):
            raise ValueError(f"Number of reviews ({len(reviews)}) must match number of embeddings ({len(embeddings)})")

        if not reviews:
            logger.warning("No reviews to add")
            return

        ids = []
        documents = []
        metadatas = []

        for review in reviews:
            # Create unique ID with collision resistance
            timestamp_str = str(int(review.created_at.timestamp()))
            doc_id = f"{review.repository}_{review.pr_number}_{review.file_path}_{timestamp_str}"

            # Ensure ID uniqueness by checking existing
            if doc_id in ids:
                # Add millisecond precision if collision
                import time
                doc_id = f"{doc_id}_{int(time.time()*1000)}"

            ids.append(doc_id)

            # Sanitize document content
            code_part = review.code_snippet.strip() if review.code_snippet else ""
            comment_part = review.review_comment.strip()
            document = f"Code:\n{code_part}\n\nReview Comment:\n{comment_part}"
            documents.append(document)

            # Validate and sanitize metadata
            metadata = {
                "pr_number": review.pr_number,
                "repository": review.repository,
                "file_path": review.file_path,
                "reviewer": review.reviewer,
                "comment_type": review.comment_type,
                "language": review.language.value if review.language else "other",
                "was_resolved": review.was_resolved,
                "created_at": review.created_at.isoformat()
            }
            metadatas.append(metadata)

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Added {len(reviews)} reviews to vector store")
        except Exception as e:
            logger.error(f"Error adding reviews to vector store: {e}")
            raise
    
    def search_similar_reviews(
        self,
        query_embedding: List[float],
        n_results: int = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for similar code reviews"""
        n_results = n_results or settings.top_k_results
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict
        )
        
        return results
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        count = self.collection.count()
        return {
            "total_reviews": count,
            "collection_name": settings.chroma_collection_name
        }
    
    def delete_collection(self):
        """Delete the entire collection (use with caution!)"""
        self.client.delete_collection(name=settings.chroma_collection_name)
        logger.warning(f"Deleted collection: {settings.chroma_collection_name}")