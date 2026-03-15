#!/usr/bin/env python3
"""
End-to-End Data Sync Pipeline
=============================
Orchestrates the entire flow from Scraping -> BigQuery -> Vector Search & Feature Store.

Steps:
0.  Scrape Data (bringo_products_v2.py) -> CSV
1.  Ingest Data (CSV -> BigQuery)
2.  Fetch & Prepare Data (BigQuery -> Formatted Dicts)
3.  Generate Multimodal Embeddings (Vertex AI) -> Save to GCS
4.  Update Vector Search Index (Vertex AI) with new embeddings
5.  Sync Feature Store (Vertex AI) for online serving

Usage:
    python pipeline/run_pipeline.py
"""

import sys
import os
import asyncio
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import Custom Modules
from pipeline.utils import setup_pipeline_logging, timer
from data import BigQueryClient
from embeddings import BatchEmbeddingProcessor
from vector_search.index_manager import IndexManager
from features.sync_feature_store import trigger_sync
from config.settings import settings

logger = setup_pipeline_logging("master_pipeline")

class BringoPipeline:
    def __init__(self):
        # Initialize clients
        self.bq_client = BigQueryClient()
        self.processor = BatchEmbeddingProcessor()
        self.index_manager = IndexManager()
        
    @timer
    def step_0_scrape_and_sync_data(self, category_filter=None, limit=None, max_categories=None):
        """Scrape fresh data using bringo_products_v2.py (Direct BQ Sync)"""
        logger.info("Starting Product Scraper & Sync (Module)...")
        
        # Import module directly
        try:
            from bringo_catalog import bringo_products_v2
        except ImportError as e:
            logger.error(f"Failed to import scraper module: {e}")
            raise

        store = "carrefour_park_lake" 
        
        try:
            # Run async main directly
            asyncio.run(bringo_products_v2.main(
                store=store,
                output_file="dummy.csv", # Output arg ignored by updated script logic but required by signature
                fetch_details=True,      # Enable details for better data quality (ingredients, etc.)
                max_categories=max_categories,     # Use limit
                max_products_per_category=limit, # Use provided limit
                category_filter=category_filter
            ))
            logger.info("Scraping & Sync completed.")
        except Exception as e:
            logger.error(f"Scraper module execution failed: {e}")
            raise

    # ... (Step 2 and onwards remain same) ...

    @timer
    def step_2_fetch_data(self):
        """Fetch latest product data from BigQuery"""
        logger.info("Fetching products from BigQuery...")
        df = self.bq_client.fetch_products()
        logger.info(f"Fetched {len(df)} products.")
        return df

    @timer
    def step_3_generate_embeddings(self, df):
        """Generate multimodal embeddings and save to GCS"""
        logger.info("Preparing data for embedding...")
        products = self.bq_client.prepare_for_embedding(df)
        
        logger.info(f"Generating embeddings for {len(products)} products...")
        # Process and save returns the GCS URI of the output file
        gcs_uri = self.processor.process_and_save(
            products=products,
            filename="bringo_products_embeddings.json"
        )
        logger.info(f"Embeddings saved to: {gcs_uri}")
        return gcs_uri

    @timer
    def step_4_update_vector_index(self, gcs_uri):
        """Update Vector Search Index with new embeddings"""
        index_name = settings.VS_INDEX_NAME
        logger.info(f"Updating Vector Search Index '{index_name}' from {gcs_uri}...")
        
        # Trigger update - this is a long running operation
        try:
            # Vertex AI expects a directory, not a file
            if gcs_uri.endswith('.json') or gcs_uri.endswith('.jsonl'):
                # Strip filename to get directory
                # gs://bucket/folder/file.json -> gs://bucket/folder/
                gcs_dir = gcs_uri.rsplit('/', 1)[0] + '/'
                logger.info(f"Converted file path '{gcs_uri}' to directory '{gcs_dir}' for Vertex AI")
            else:
                gcs_dir = gcs_uri

            operation = self.index_manager.update_index(
                index_name=index_name,
                embeddings_gcs_uri=gcs_dir
            )
            # Wait for completion
            logger.info("Waiting for index update to complete (this may take 20+ mins)...")
            self.index_manager.wait_for_completion(operation, "Index Update")
            logger.info("Vector Index updated successfully.")
        except Exception as e:
             logger.warning(f"Index update failed: {e}")
             # In some cases (e.g. index doesn't exist yet), we might want to create it.
             # but for update pipeline, we assume existence.
             raise

    @timer
    def step_5_sync_feature_store(self):
        """Trigger Feature Store Sync"""
        logger.info("Triggering Feature Store Sync...")
        trigger_sync()
        logger.info("Feature Store sync initiated (running in background).")

    def run(self, category_filter=None, limit=None, max_categories=None):
        """Run the full pipeline"""
        logger.info("🚀 STARTING BRINGO DATA PIPELINE")
        
        try:
            # 0. Scrape & Sync (Direct to BQ)
            self.step_0_scrape_and_sync_data(category_filter=category_filter, limit=limit, max_categories=max_categories)
            
            # Step 1 removed
            
            # 2. Fetch (Verification/Prep)
            df = self.step_2_fetch_data()
            
            if df.empty:
                logger.warning("No data found in BigQuery after syncing. Aborting.")
                return

            # 3. Embed
            gcs_uri = self.step_3_generate_embeddings(df)
            
            # 4. Update Index
            self.step_4_update_vector_index(gcs_uri)
            
            # 5. Sync Feature Store
            self.step_5_sync_feature_store()
            
            logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
            
        except Exception as e:
            logger.error(f"💥 PIPELINE FAILED: {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run End-to-End Pipeline')
    parser.add_argument('--category', type=str, help='Filter scraping to specific category')
    parser.add_argument('--limit', type=int, default=None, help='Limit products per category (for testing)')
    parser.add_argument('--max-categories', type=int, default=None, help='Limit number of categories to scrape')
    args = parser.parse_args()

    pipeline = BringoPipeline()
    pipeline.run(category_filter=args.category, limit=args.limit, max_categories=args.max_categories)
