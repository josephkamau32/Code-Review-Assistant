from typing import List
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# Import providers conditionally
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from src.config.settings import settings


class EmbeddingService:
    def __init__(self):
        self.provider = settings.embedding_provider.lower()
        self.dimensions = settings.embedding_dimensions

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def _init_gemini(self):
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-genai not installed. Install with: pip install google-genai"
            )

        api_key = settings.gemini_api_key
        if not api_key or api_key == "your_gemini_api_key_here":
            logger.warning("Using mock embedding service - no Gemini API key provided")
            self.mock_mode = True
            self.model = settings.gemini_embedding_model
        else:
            self.client = genai.Client(api_key=api_key)
            self.mock_mode = False
            self.model = settings.gemini_embedding_model
            logger.info(
                f"Initialized Gemini embedding service with model: {self.model}"
            )

    def _init_openai(self):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai not installed. Install with: pip install openai")

        api_key = settings.openai_api_key
        if api_key == "your_openai_api_key_here" or not api_key:
            logger.warning("Using mock embedding service - no OpenAI API key provided")
            self.mock_mode = True
            self.model = settings.embedding_model
        else:
            self.client = OpenAI(api_key=api_key)
            self.mock_mode = False
            self.model = settings.embedding_model
            logger.info(
                f"Initialized OpenAI embedding service with model: {self.model}"
            )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
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
            embedding = np.random.normal(0, 1, self.dimensions).tolist()
            logger.debug(f"DEBUG: Generated mock embedding, length: {len(embedding)}")
            return embedding

        try:
            if self.provider == "gemini":
                return self._embed_text_gemini(text)
            else:  # openai
                return self._embed_text_openai(text)
        except Exception as e:
            logger.error(f"DEBUG: Error generating embedding: {e}")
            raise

    def _embed_text_openai(self, text: str) -> List[float]:
        logger.debug(
            f"DEBUG: Starting OpenAI embedding generation for text length: {len(text)}"
        )
        response = self.client.embeddings.create(model=self.model, input=text)
        embedding = response.data[0].embedding
        logger.debug(f"DEBUG: Generated OpenAI embedding, length: {len(embedding)}")
        return embedding

    def _embed_text_gemini(self, text: str) -> List[float]:
        logger.debug(
            f"DEBUG: Starting Gemini embedding generation for text length: {len(text)}"
        )

        response = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=genai_types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dimensions,
            ),
        )

        embedding = response.embeddings[0].values
        logger.debug(f"DEBUG: Generated Gemini embedding, length: {len(embedding)}")
        return embedding

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
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
                embedding = np.random.normal(0, 1, self.dimensions).tolist()
                all_embeddings.append(embedding)
            logger.debug(f"Generated {len(all_embeddings)} mock embeddings")
            return all_embeddings

        try:
            if self.provider == "gemini":
                return self._embed_batch_gemini(texts)
            else:  # openai
                return self._embed_batch_openai(texts)
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise

    def _embed_batch_openai(self, texts: List[str]) -> List[List[float]]:
        # OpenAI API has a limit on batch size, so chunk if needed
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(embeddings)
            logger.debug(f"Generated embeddings for batch {i//batch_size + 1}")

        return all_embeddings

    def _embed_batch_gemini(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []

        # Gemini supports batch embedding via list of contents
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            response = self.client.models.embed_content(
                model=self.model,
                contents=batch,
                config=genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.dimensions,
                ),
            )

            for emb in response.embeddings:
                all_embeddings.append(emb.values)

            logger.debug(f"Generated Gemini embeddings for batch {i//batch_size + 1}")

        return all_embeddings

    def embed_code_change(self, code_snippet: str, context: str = "") -> List[float]:
        """Generate embedding specifically for code changes with context"""
        # Combine code and context for better semantic representation
        full_text = (
            f"Context: {context}\n\nCode:\n{code_snippet}" if context else code_snippet
        )
        return self.embed_text(full_text)
