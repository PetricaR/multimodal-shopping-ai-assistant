"""
Fire-and-forget BigQuery logging for search queries.
Every call to log_search_event is non-blocking — wrapped in run_in_executor
so the BQ network call never delays the search response.

BigQuery table DDL (run once):
  CREATE TABLE IF NOT EXISTS `formare-ai.bringo_similarity_search_multimodal.search_query_logs` (
    logged_at            TIMESTAMP NOT NULL,
    query_text           STRING,
    enriched_query       STRING,
    result_count         INT64,
    candidates_retrieved INT64,
    latency_ms           FLOAT64,
    price_min            FLOAT64,
    price_max            FLOAT64,
    in_stock_only        BOOL,
    use_ranking          BOOL,
    use_query_enrichment BOOL,
    search_method        STRING
  )
  PARTITION BY DATE(logged_at)
  OPTIONS (require_partition_filter = false);
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


def _sync_insert(bq_client, table_ref: str, row: dict) -> None:
    errors = bq_client.insert_rows_json(table_ref, [row])
    if errors:
        logger.warning(f"BQ search log insert errors: {errors}")


async def log_search_event(
    bq_client,
    query_text: str,
    enriched_query: Optional[str],
    result_count: int,
    candidates_retrieved: int,
    latency_ms: float,
    filters: dict,
    search_method: str,
) -> None:
    """Log a search event to BigQuery. Swallows all exceptions."""
    if not settings.BQ_SEARCH_LOG_ENABLED:
        return
    try:
        table_ref = (
            f"{settings.PROJECT_ID}."
            f"{settings.BQ_OUTPUT_DATASET}."
            f"{settings.BQ_SEARCH_LOG_TABLE}"
        )
        row = {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "query_text": query_text or None,
            "enriched_query": enriched_query or None,
            "result_count": result_count,
            "candidates_retrieved": candidates_retrieved,
            "latency_ms": round(latency_ms, 1),
            "price_min": filters.get("price_min"),
            "price_max": filters.get("price_max"),
            "in_stock_only": bool(filters.get("in_stock_only", False)),
            "use_ranking": True,
            "use_query_enrichment": enriched_query is not None,
            "search_method": search_method,
        }
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _sync_insert, bq_client, table_ref, row)
    except Exception as e:
        logger.warning(f"Search log failed (non-critical): {e}")
