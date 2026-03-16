import logging
import sys
import asyncio
import json
from pathlib import Path
from typing import List, Dict
import pandas as pd
from tqdm.asyncio import tqdm

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from data.bigquery_client import BigQueryClient
from enrichment.enricher import ProductEnricher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Output table
ENRICHED_TABLE = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}.bringo_products_enriched"

async def process_batch(enricher: ProductEnricher, products: List[Dict]):
    # Not used in sequential loop but good structure
    pass

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="Number of products to process")
    args = parser.parse_args()
    
    logger.info(f"🚀 Starting Product Enrichment (Limit: {args.limit})")
    
    # 1. Fetch Products
    bq = BigQueryClient()
    all_products = bq.fetch_products(limit=args.limit)
    if all_products.empty:
        logger.info("No products found.")
        return

    # Prepare for enrichment (convert to list of dicts)
    products_list = all_products.to_dict('records')
    
    # 2. Enrich
    enricher = ProductEnricher()
    enriched_records = []
    
    pbar = tqdm(products_list, desc="Enriching")
    for product in pbar:
        try:
            # Clean up product dict to match expected logic (handle NaNs)
            clean_product = {k: (None if pd.isna(v) else v) for k, v in product.items()}
            
            # Enricher returns the full fixed record now
            enriched = await enricher.enrich_product_async(clean_product)
            if enriched:
                # Ensure product_id is int as per schema
                if 'product_id' in enriched:
                    enriched['product_id'] = int(enriched['product_id'])
                enriched_records.append(enriched)

        except Exception as e:
            logger.error(f"Failed to enrich {product.get('product_id')}: {e}")
            
    # 3. Save to BigQuery
    if enriched_records:
        df_enriched = pd.DataFrame(enriched_records)
        logger.info(f"Saving {len(df_enriched)} enriched records to {ENRICHED_TABLE}...")
        
        # Using pandas-gbq or client
        from google.cloud import bigquery
        
        job_config = bq.client.load_table_from_dataframe(
            df_enriched, 
            ENRICHED_TABLE, 
            job_config=bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=["ALLOW_FIELD_ADDITION"],
                autodetect=True
            )
        )
        job_config.result()
        logger.info("✅ Enrichment saved.")
    else:
        logger.warning("No records were enriched.")


if __name__ == "__main__":
    asyncio.run(main())
