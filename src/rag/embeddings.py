from openai import OpenAI
from typing import List, Union
from loguru import logger
from src.config.settings import settings
from tenacity import retry, stop_after_attempt, wait_exponential


class EmbeddingService:
    def __init__(self):
        # Use a mock API key for testing if the real one is not available
        api_key = settings.openai_api_key
        if api_key == "your_openai_api_key_here" or not api_key:
            logger.warning("Using mock embedding service - no real API key provided")
            self.mock_mode = True
            self.model = settings.embedding_model
        else:
            self.client = OpenAI(api_key=api_key)
            self.mock_mode = False
            self.model = settings.embedding_model
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if self.mock_mode:
            # Return a mock embedding for testing
            import hashlib
            import numpy as np
            # Generate deterministic mock embedding based on text hash
            hash_obj = hashlib.md5(text.encode())
            np.random.seed(int(hash_obj.hexdigest()[:8], 16))
            embedding = np.random.normal(0, 1, 1536).tolist()  # OpenAI embedding dimension
            logger.debug(f"DEBUG: Generated mock embedding, length: {len(embedding)}")
            return embedding

        try:
            logger.debug(f"DEBUG: Starting embedding generation for text length: {len(text)}")
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding
            logger.debug(f"DEBUG: Generated embedding, length: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"DEBUG: Error generating embedding: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (batch processing)"""
        if self.mock_mode:
            # Return mock embeddings for testing
            import hashlib
            import numpy as np
            all_embeddings = []
            for text in texts:
                hash_obj = hashlib.md5(text.encode())
                np.random.seed(int(hash_obj.hexdigest()[:8], 16))
                embedding = np.random.normal(0, 1, 1536).tolist()
                all_embeddings.append(embedding)
            logger.debug(f"Generated {len(all_embeddings)} mock embeddings")
            return all_embeddings

        try:
            # OpenAI API has a limit on batch size, so chunk if needed
            batch_size = 100
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(embeddings)
                logger.debug(f"Generated embeddings for batch {i//batch_size + 1}")

            return all_embeddings
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
    
    def embed_code_change(self, code_snippet: str, context: str = "") -> List[float]:
        """Generate embedding specifically for code changes with context"""
        # Combine code and context for better semantic representation
        full_text = f"Context: {context}\n\nCode:\n{code_snippet}" if context else code_snippet
        return self.embed_text(full_text)