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
        
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata]
        )
        
        logger.debug(f"Added review to vector store: {doc_id}")
        return doc_id
    
    def add_reviews_batch(self, reviews: List[HistoricalReview], embeddings: List[List[float]]):
        """Add multiple reviews in batch (more efficient)"""
        if len(reviews) != len(embeddings):
            raise ValueError("Number of reviews must match number of embeddings")
        
        ids = []
        documents = []
        metadatas = []
        
        for review in reviews:
            doc_id = f"{review.repository}_{review.pr_number}_{review.file_path}_{review.created_at.timestamp()}"
            ids.append(doc_id)
            
            document = f"Code:\n{review.code_snippet}\n\nReview Comment:\n{review.review_comment}"
            documents.append(document)
            
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
            metadatas.append(metadata)
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(reviews)} reviews to vector store")
    
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