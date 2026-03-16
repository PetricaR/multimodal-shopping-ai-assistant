"""
Configuration management for Bringo Product Similarity Search
Using gemini-embedding-2-preview for embeddings (text + multimodal via Vision description)
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path


def _fetch_secret(project_id: str, secret_name: str) -> Optional[str]:
    """Fetch latest version of a secret from GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        return client.access_secret_version(request={"name": name}).payload.data.decode("utf-8")
    except Exception:
        return None

class Settings(BaseSettings):
    """
    Settings synchronized with gke-deployment/config.env
    """

    # GCP Settings (mapped from config.env)
    PROJECT_ID: str = Field(default="formare-ai", alias="GCP_PROJECT_ID")
    LOCATION: str = Field(default="europe-west1", alias="AI_LOCATION")
    STAGING_BUCKET: str = "formare-ai-vector-search"
    GCS_BUCKET: str = "formare-ai-vector-search"  # Alias for setup scripts

    # BigQuery Settings
    BQ_DATASET: str = "bringo_products_data"
    BQ_TABLE: str = "bringo_products_native"  # Native table (faster than Google Sheets external table)
    BQ_OUTPUT_DATASET: str = "bringo_similarity_search_multimodal"
    BQ_SEARCH_LOG_TABLE: str = "search_query_logs"
    BQ_SEARCH_LOG_ENABLED: bool = True

    # AI Model Settings
    # Gemini preview models are only available in us-central1 (not europe-west1).
    # GENERATION_LOCATION is used for Gemini generation calls only.
    # All other services (embeddings, Vector Search, Feature Store) use LOCATION (europe-west1).
    GENERATION_LOCATION: str = "us-central1"
    EMBEDDING_MODEL: str = "gemini-embedding-2-preview"  # Multimodal embeddings with Matryoshka dimensions
    EMBEDDING_DIMENSION: int = 768  # Recommended: 768, 1536, or 3072 (768 is optimal cost/quality)
    RANKING_MODEL: str = "semantic-ranker-default@latest"
    GENERATION_MODEL: str = "gemini-3-flash-preview"  # Fast text-only reasoning model

    # Vector Search Settings
    VS_INDEX_NAME: str = "bringo-product-index-multimodal"
    VS_ENDPOINT_NAME: str = "bringo-product-endpoint-multimodal"
    VS_DEPLOYED_INDEX_ID: str = "bringo_products_multimodal_deployed"
    VS_MACHINE_TYPE: str = "e2-standard-2"
    VS_MIN_REPLICAS: int = 1
    VS_MAX_REPLICAS: int = 2
    VS_SHARD_SIZE: str = "SHARD_SIZE_SMALL"

    # Security
    API_AUTH_KEY: str = "no-key-set"

    # Feature Store Endpoint (Optimized)
    FS_PUBLIC_ENDPOINT: str = "527765581332480.europe-west1-845266575866.featurestore.vertexai.goog"
    # Make the metadata view configurable via FEATURE_VIEW_ID env var. Default to the bringo view.
    FS_METADATA_VIEW: str = Field(default="bringo_product_data", alias="FEATURE_VIEW_ID")

    # API Port
    API_PORT: int = Field(default=8080, alias="PORT")
    API_HOST: str = "0.0.0.0"

    # Internal Consts
    USE_RANKING: bool = True
    USE_MULTIMODAL: bool = False  # Text-only embeddings via gemini-embedding-2-preview
    RANKING_TOP_N: int = 20
    VS_APPROXIMATE_NEIGHBORS: int = 150
    VS_DISTANCE_MEASURE: str = "COSINE_DISTANCE"
    IMAGE_MAX_RETRIES: int = 3  # Max retries for image download/processing
    IMAGE_CACHE_DIR: str = "/tmp/image_cache"  # Helper for image processing
    IMAGE_TIMEOUT: int = 10
    IMAGE_RESIZE_WIDTH: int = 512
    IMAGE_RESIZE_HEIGHT: int = 512
    IMAGE_QUALITY: int = 85
    FALLBACK_TO_TEXT: bool = True

    # Embedding Generation
    BATCH_SIZE: int = 100  # Increased batch size
    EMBEDDING_RATE_LIMIT: int = 500  # req/min — stays under 20k quota with parallel workers

    # Bringo Configuration
    BRINGO_BASE_URL: str = Field(default="https://www.bringo.ro", alias="BRINGO_URL")
    BRINGO_STORE: str = Field(default="carrefour_park_lake", alias="BRINGO_STORE")
    BRINGO_USERNAME: Optional[str] = Field(default=None, alias="BRINGO_USERNAME")
    BRINGO_PASSWORD: Optional[str] = Field(default=None, alias="BRINGO_PASSWORD")
    BRINGO_ADDRESS: Optional[str] = Field(default=None, alias="BRINGO_ADDRESS")

    # Session Keep-Alive Worker Configuration
    SESSION_REFRESH_BUFFER_MINUTES: Optional[int] = Field(
        default=30,
        description="Refresh session this many minutes before expiration"
    )
    SESSION_POLL_INTERVAL_SECONDS: Optional[int] = Field(
        default=60,
        description="How often to check for sessions needing refresh"
    )
    SESSION_VALIDATE_INTERVAL_MINUTES: Optional[int] = Field(
        default=15,
        description="How often to validate session with Bringo server"
    )
    ENABLE_SESSION_VALIDATION_ON_REQUEST: bool = Field(
        default=False,
        description="If True, validate session on every API request (adds latency). Set to False if using worker pool."
    )

    # API Keys
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    
    class Config:
        # Check both root .env and gke-deployment config.env
        env_file = [
            str(Path(__file__).parent.parent / ".env"),
            str(Path(__file__).parent.parent / "gke-deployment" / "config.env")
        ]
        case_sensitive = True
        extra = "ignore"


def _resolve_settings() -> "Settings":
    s = Settings()
    # Secret Manager takes priority over .env so rotating the secret is sufficient
    secret_key = _fetch_secret(s.PROJECT_ID, "gemini-api-key")
    if secret_key:
        s.GOOGLE_API_KEY = secret_key
        
    maps_key = _fetch_secret(s.PROJECT_ID, "GOOGLE_MAPS_API_KEY")
    if maps_key:
        s.GOOGLE_MAPS_API_KEY = maps_key
        
    return s


settings = _resolve_settings()
