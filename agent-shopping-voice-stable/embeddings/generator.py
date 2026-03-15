"""
Embedding Generator using Google GenAI SDK (gemini-embedding-2-preview)

Best practices from https://ai.google.dev/gemini-api/docs/embeddings:
1. Use gemini-embedding-2-preview (latest model, multimodal, Matryoshka dimensions)
2. Use RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for search queries
3. L2-normalize embeddings when using non-3072 dimensions (768, 1536)
4. Batch processing for throughput
5. Retry with exponential backoff
"""
import os
import math
import logging
import threading
from typing import Dict, List, Optional, Tuple
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from config.settings import settings

logger = logging.getLogger(__name__)


def _is_retryable_error(exc: BaseException) -> bool:
    """
    Only retry on transient errors: rate limit (429) and server unavailable (503/5xx).
    Do NOT retry on 400 Bad Request or 415 Unsupported Media Type — those will never succeed.
    """
    msg = str(exc).lower()
    # Check HTTP status code hints in message
    for code in ('429', '503', '500', '502', '504'):
        if code in msg:
            return True
    # Check keywords
    for kw in ('rate limit', 'quota exceeded', 'resource exhausted', 'unavailable', 'too many requests'):
        if kw in msg:
            return True
    # grpc status codes
    try:
        import grpc
        if hasattr(exc, 'grpc_status_code') and exc.grpc_status_code in (
            grpc.StatusCode.RESOURCE_EXHAUSTED, grpc.StatusCode.UNAVAILABLE
        ):
            return True
    except ImportError:
        pass
    return False


def _l2_normalize(embedding: List[float]) -> List[float]:
    """
    L2-normalize an embedding vector.
    Required for gemini-embedding-001 when output_dimensionality < 3072,
    since only the default 3072-dim output is pre-normalized.
    """
    norm = math.sqrt(sum(x * x for x in embedding))
    if norm == 0:
        return embedding
    return [x / norm for x in embedding]


class EmbeddingGenerator:
    """
    Generate embeddings using Google GenAI SDK with gemini-embedding-2-preview.

    Key design choices:
    - RETRIEVAL_DOCUMENT task type for indexing product data
    - RETRIEVAL_QUERY task type for search queries
    - L2 normalization for reduced dimensions (768, 1536)
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY")

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Initialized GenAI Client (API Key)")
        else:
            self.client = genai.Client(
                vertexai=True,
                project=settings.PROJECT_ID,
                location=settings.LOCATION
            )
            logger.info(f"Initialized GenAI Client (Vertex AI: {settings.PROJECT_ID})")

        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self._needs_normalization = self.dimension < 3072

        # Query embedding cache — keyed by (text, task_type).
        # Search queries repeat across product types in the same campaign and across
        # similar campaigns. Caching eliminates redundant Embeddings API calls.
        # Max 512 entries (~4 MB at 512D float32) keeps memory bounded.
        # Dict insertion order (Python 3.7+) gives FIFO eviction which is fine here.
        self._query_cache: Dict[Tuple[str, str], List[float]] = {}
        self._cache_maxsize = 512
        self._cache_lock = threading.Lock()  # protects write path against races

    def _truncate_text(self, text: str, max_chars: int = 30000) -> str:
        """Truncate text to stay within the 8192-token input limit."""
        if text and len(text) > max_chars:
            return text[:max_chars]
        return text or ""

    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=2, min=5, max=60)
    )
    def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.
            task_type: One of RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY,
                       SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING,
                       QUESTION_ANSWERING, FACT_VERIFICATION, CODE_RETRIEVAL_QUERY.
        """
        if not texts:
            return []

        clean_texts = [self._truncate_text(t) for t in texts]

        try:
            logger.info(
                f"Generating {len(texts)} embeddings | model={self.model} "
                f"dim={self.dimension} task={task_type}"
            )

            result = self.client.models.embed_content(
                model=self.model,
                contents=clean_texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimension
                )
            )

            embeddings = [e.values for e in result.embeddings]

            # L2-normalize when using reduced dimensions (768, 1536)
            if self._needs_normalization:
                embeddings = [_l2_normalize(e) for e in embeddings]

            if embeddings:
                logger.info(
                    f"Generated {len(embeddings)} vectors (dim={len(embeddings[0])})"
                )
            return embeddings

        except Exception as e:
            # Log exact error type to help debugging ClientError vs other errors
            error_type = f"{type(e).__module__}.{type(e).__name__}"
            logger.error(f"Batch embedding failed ({error_type}): {e}", exc_info=True)
            raise

    def generate_embedding(
        self,
        text: str,
        image_url: Optional[str] = None,
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> Tuple[List[float], str]:
        """
        Generate a single embedding. Convenience wrapper around batch method.

        Text-only embeddings (image_url=None) are cached by (text, task_type) so that
        repeated queries within or across requests (e.g. same product-type search query
        re-used across similar campaigns) cost zero API calls after the first hit.

        Args:
            text: Text to embed.
            image_url: Ignored (text-only mode).
            task_type: Task type for the embedding.
        """
        # Cache only text-only calls — image embedding bytes are not cacheable this way
        if image_url is None:
            cache_key = (text or "", task_type)
            cached = self._query_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Embedding cache hit: '{text[:40]}' [{task_type}]")
                return cached, 'text'

        embeddings = self.generate_embeddings_batch([text], task_type=task_type)
        emb = embeddings[0] if embeddings else [0.0] * self.dimension
        modality = 'text' if embeddings else 'error'

        if image_url is None and modality == 'text':
            with self._cache_lock:
                if len(self._query_cache) >= self._cache_maxsize:
                    # FIFO eviction: remove the oldest inserted entry
                    self._query_cache.pop(next(iter(self._query_cache)))
                self._query_cache[cache_key] = emb

        return emb, modality

    # Inline size threshold: use Files API above this (10 MB)
    _FILES_API_THRESHOLD_BYTES = 10 * 1024 * 1024

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception(_is_retryable_error),
    )
    def generate_embedding_from_bytes(
        self,
        file_bytes: bytes,
        mime_type: str,
        task_type: str = "RETRIEVAL_QUERY"
    ) -> Tuple[List[float], str]:
        """
        Generate an embedding from raw file bytes using gemini-embedding-2-preview.

        All modalities embed into the same vector space so results are directly
        comparable to text embeddings in the product index.

        Supported MIME types (inline, <= Files API threshold):
          - image/jpeg, image/png, image/webp, image/gif
          - audio/mp3, audio/mpeg, audio/wav, audio/ogg
          - video/mp4, video/mov, video/webm
          - application/pdf  (<= 6 pages inline; larger files -> Files API)
          - text/*            (decoded UTF-8 -> text embedding)

        Large files (> _FILES_API_THRESHOLD_BYTES) are uploaded via the Files API
        and referenced by URI, which is the recommended approach for bigger payloads.

        Args:
            file_bytes: Raw file contents.
            mime_type: MIME type of the file.
            task_type: Embedding task type (default RETRIEVAL_QUERY for searches).

        Returns:
            (embedding vector, modality string)
        """
        modality_map = {
            'image/': 'image',
            'audio/': 'audio',
            'video/': 'video',
            'application/pdf': 'pdf',
            'text/': 'text',
        }
        modality = next((v for k, v in modality_map.items() if mime_type.startswith(k)), 'file')

        logger.info(f"Embedding from bytes: mime={mime_type}, size={len(file_bytes)}, modality={modality}")

        if modality == 'text':
            text = file_bytes.decode('utf-8', errors='ignore')
            embeddings = self.generate_embeddings_batch([self._truncate_text(text)], task_type=task_type)
            return (embeddings[0] if embeddings else [0.0] * self.dimension), 'text'

        # gemini-embedding-2-preview only supports text via batchEmbedContents.
        # For images / PDFs: use Gemini Vision to describe the product in Romanian,
        # then embed that description as text — compatible with the text-only index.
        description = self._describe_with_gemini_vision(file_bytes, mime_type, modality)
        logger.info(f"Vision description for embedding: '{description[:120]}'")
        embeddings = self.generate_embeddings_batch([description], task_type=task_type)
        return (embeddings[0] if embeddings else [0.0] * self.dimension), f'{modality}_described'

    def _describe_with_gemini_vision(self, file_bytes: bytes, mime_type: str, modality: str) -> str:
        """
        Use Gemini Vision (via self.client) to produce a Romanian product description
        that can be embedded as text for catalog search.
        """
        from config.settings import settings

        prompt_text = (
            "Descrie acest produs alimentar în română pentru un motor de căutare în catalog. "
            "Include: tipul produsului, marca (dacă e vizibilă), caracteristici cheie (gramaj, tip, aromă etc.). "
            "Răspunde cu 1-2 propoziții concise, fără introducere."
        )

        try:
            image_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            text_part = types.Part(text=prompt_text)
            response = self.client.models.generate_content(
                model=settings.GENERATION_MODEL,
                contents=[text_part, image_part],
            )
            description = response.text.strip()
            return description if description else "produs alimentar"
        except Exception as e:
            logger.warning(f"Gemini Vision description failed ({modality}): {e}")
            return "produs alimentar"


# Backwards-compatible alias
MultimodalEmbeddingGenerator = EmbeddingGenerator
