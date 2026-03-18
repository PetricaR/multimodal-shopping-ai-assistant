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
    def step_0_scrape_and_sync_data(self, category_filter=None, category_slug=None, limit=None, max_categories=None, no_details=False):
        """Scrape fresh data using bringo_products_v3.py (Direct BQ Sync)
        
        Args:
            category_filter: Partial match filter for categories (multi-category mode)
            category_slug: Exact category slug for single-category mode (e.g., 'mezeluri-110')
            limit: Max products per category
            max_categories: Max categories to scrape (multi-category mode)
            no_details: If True, skip fetching detailed product info (faster)
        """
        logger.info("Starting Product Scraper & Sync (v3 Module)...")
        
        # Import v3 module directly
        try:
            from bringo_catalog import bringo_products_v3
        except ImportError as e:
            logger.error(f"Failed to import scraper module: {e}")
            raise

        store = "carrefour_park_lake" 
        fetch_details = not no_details
        
        try:
            # Single category mode (preferred for targeted extraction)
            if category_slug:
                category_name = category_slug.replace('-', ' ').title()
                logger.info(f"Single-category mode: {category_name} ({category_slug})")
                asyncio.run(bringo_products_v3.main_single_category(
                    store=store,
                    category_slug=category_slug,
                    category_name=category_name,
                    output_file="pipeline_output.csv",
                    fetch_details=fetch_details,
                    max_products=limit
                ))
            else:
                # Multi-category mode (original behavior)
                logger.info(f"Multi-category mode: filter={category_filter}, max_categories={max_categories}")
                asyncio.run(bringo_products_v3.main(
                    store=store,
                    output_file="pipeline_output.csv",
                    fetch_details=fetch_details,
                    max_categories=max_categories,
                    max_products_per_category=limit,
                    category_filter=category_filter
                ))
            logger.info("Scraping & Sync completed.")
        except Exception as e:
            logger.error(f"Scraper module execution failed: {e}")
            raise

    @timer
    def step_2_fetch_data(self):
        """Fetch latest product data from BigQuery"""
        logger.info("Fetching products from BigQuery...")
        df = self.bq_client.fetch_products()
        logger.info(f"Fetched {len(df)} products.")
        return df

    @timer
    def step_3_generate_embeddings(self, df):
        """Generate text-only embeddings and save to GCS"""
        logger.info("Preparing data for embedding...")
        products = self.bq_client.prepare_for_embedding(df)
        
        logger.info(f"Generating embeddings for {len(products)} products...")
        # Process and save returns the GCS URI of the output file
        # Force regenerate to ensure we don't mix with old multimodal embeddings
        # Use dedicated filename for text-only embeddings
        gcs_uri = self.processor.process_and_save(
            products=products,
            filename="bringo_products_embeddings_text.json",
            force_regenerate=True
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
            
            # CRITICAL: Ensure index is deployed
            logger.info("Ensuring index is deployed to endpoint...")
            endpoint_name = settings.VS_ENDPOINT_NAME
            endpoint = self.index_manager.get_or_create_endpoint(endpoint_name)
            
            # Check deployment
            index_resource = self.index_manager.get_existing_index(index_name)
            is_deployed = False
            for deployed_index in endpoint.deployed_indexes:
                if deployed_index.index == index_resource.resource_name:
                    is_deployed = True
                    logger.info(f"✅ Index '{index_name}' is already deployed.")
                    break
            
            if not is_deployed:
                logger.info(f"🚀 Deploying index to endpoint '{endpoint_name}'...")
                self.index_manager.deploy_index(index=index_resource, endpoint=endpoint)

            logger.info("Vector Index updated and verified deployed.")
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

    def run(self, category_filter=None, category_slug=None, limit=None, max_categories=None, no_details=False, skip_scrape=False):
        """Run the full pipeline
        
        Args:
            category_filter: Partial match filter for categories (multi-category mode)
            category_slug: Exact category slug for single-category mode (e.g., 'mezeluri-110')
            limit: Max products per category
            max_categories: Max categories to scrape (multi-category mode)
            no_details: Skip detailed product info fetching (faster)
            skip_scrape: Skip scraping step completely
        """
        logger.info("🚀 STARTING BRINGO DATA PIPELINE")
        
        try:
            # 0. Scrape & Sync (Direct to BQ)
            if not skip_scrape:
                self.step_0_scrape_and_sync_data(
                    category_filter=category_filter, 
                    category_slug=category_slug,
                    limit=limit, 
                    max_categories=max_categories,
                    no_details=no_details
                )
            else:
                logger.info("⏭️  Skipping Step 0 (Scraping) as requested.")
            
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
    parser = argparse.ArgumentParser(description='Bringo End-to-End Pipeline (v3)')
    
    # Category selection (mutually preferred: use --category-slug for single category)
    parser.add_argument('--category', type=str, help='Filter scraping to specific category (partial match)')
    parser.add_argument('--category-slug', type=str, dest='category_slug',
                        help='Exact category slug for single-category extraction (e.g., "mezeluri-110")')
    
    # Limits
    parser.add_argument('--limit', type=int, default=None, help='Limit products per category')
    parser.add_argument('--max-categories', type=int, default=None, dest='max_categories',
                        help='Limit number of categories to scrape (multi-category mode)')
    
    # Speed optimization
    parser.add_argument('--no-details', action='store_true', dest='no_details',
                        help='Skip fetching detailed product info (faster scraping)')
    parser.add_argument('--skip-scrape', action='store_true', dest='skip_scrape',
                        help='Skip scraping step (process existing BQ data only)')
    
    args = parser.parse_args()

    pipeline = BringoPipeline()
    pipeline.run(
        category_filter=args.category, 
        category_slug=args.category_slug,
        limit=args.limit, 
        max_categories=args.max_categories,
        no_details=args.no_details,
        skip_scrape=args.skip_scrape
    )
