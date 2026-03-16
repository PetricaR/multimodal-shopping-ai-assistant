#!/usr/bin/env python3
"""
Pipeline Verification Suite
Consolidates all data integrity checks for the Bringo Vector Search Pipeline.

Usage:
    python scripts/verify_pipeline.py [all|duplicates|counts|embeddings|view]
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import argparse
from google.cloud import bigquery
from google.cloud import storage
from config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_duplicates():
    """Check for duplicate product names in BigQuery source"""
    logger.info("---------------------------------------------------------")
    logger.info("🔍 CHECK: Duplicate Data (Source Table)")
    logger.info("---------------------------------------------------------")
    
    client = bigquery.Client(project=settings.PROJECT_ID)
    table_id = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}.{settings.BQ_TABLE}"
    
    query = f"""
    SELECT product_name, cnt
    FROM (
        SELECT product_name, COUNT(*) as cnt
        FROM `{table_id}`
        WHERE product_name IS NOT NULL
        GROUP BY product_name
    )
    WHERE cnt > 1
    ORDER BY cnt DESC
    LIMIT 5
    """
    try:
        rows = list(client.query(query))
        if not rows:
            logger.info("✅ PASS: No duplicate product names found in raw table.")
            return True
        else:
            logger.warning(f"⚠️  WARN: Found duplicates in RAW table (Top 5):")
            for r in rows:
                logger.warning(f"   - '{r.product_name}': {r.cnt}")
            logger.info("   (Note: Use the 'unique' view for Feature Store to avoid errors)")
            return False
    except Exception as e:
        logger.error(f"❌ FAIL: Query error: {e}")
        return False

def count_view_rows():
    """Count rows in the deduplicated view"""
    logger.info("---------------------------------------------------------")
    logger.info("🔍 CHECK: Unique View Count (Feature Store Source)")
    logger.info("---------------------------------------------------------")
    
    client = bigquery.Client(project=settings.PROJECT_ID)
    view_id = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}.bringo_products_unique_names_view"
    
    try:
        query = f"SELECT count(*) as cnt FROM `{view_id}`"
        rows = list(client.query(query))
        count = rows[0].cnt
        logger.info(f"✅ View Count: {count} unique items")
        return count
    except Exception as e:
        logger.error(f"❌ FAIL: View query error: {e}")
        return 0

def inspect_gcs_id_format():
    """Verify generated embeddings use product_name as ID"""
    logger.info("---------------------------------------------------------")
    logger.info("🔍 CHECK: Embedding ID Format (GCS)")
    logger.info("---------------------------------------------------------")
    
    storage_client = storage.Client(project=settings.PROJECT_ID)
    bucket = storage_client.bucket(settings.STAGING_BUCKET)
    blob = bucket.blob("embeddings/bringo_products_embeddings.json") # Check .json
    
    if not blob.exists():
        logger.error("❌ FAIL: Embeddings file not found in GCS.")
        return False
        
    try:
        # Read a small chunk
        content = blob.download_as_bytes(start=0, end=5000).decode('utf-8', errors='ignore')
        lines = content.strip().split('\n')
        
        if not lines:
            logger.error("❌ FAIL: File is empty")
            return False
            
        first_line = json.loads(lines[0])
        record_id = first_line.get('id')
        
        logger.info(f"Sample ID: '{record_id}'")
        
        if record_id and not str(record_id).isdigit():
             logger.info("✅ PASS: ID format looks correct (Text/Product Name)")
             return True
        else:
             logger.warning("⚠️  WARN: ID might be numeric/incorrect. Expected product name.")
             return False
             
    except Exception as e:
        logger.error(f"❌ FAIL: Inspection error: {e}")
        return False

def verify_counts(expected_count=None):
    """Compare GCS line count vs Expected Count"""
    logger.info("---------------------------------------------------------")
    logger.info("🔍 CHECK: Data Integrity (Source vs Embeddings)")
    logger.info("---------------------------------------------------------")
    
    if not expected_count:
        # Fetch from view if not provided
        expected_count = count_view_rows()
    
    storage_client = storage.Client(project=settings.PROJECT_ID)
    bucket = storage_client.bucket(settings.STAGING_BUCKET)
    blob = bucket.blob("embeddings/bringo_products_embeddings.json")
    
    if not blob.exists():
        logger.error("❌ FAIL: Metadata check failed - file missing")
        return
        
    try:
        # Estimate or count? For < 10MB just download.
        content = blob.download_as_text()
        gcs_count = len(content.strip().split('\n'))
        
        logger.info(f"Source (Unique View): {expected_count}")
        logger.info(f"Generated Embeddings: {gcs_count}")
        
        if gcs_count == expected_count:
            logger.info("✅ PASS: Perfect Match (100%)")
        elif abs(gcs_count - expected_count) < 20:
             logger.warning(f"⚠️  WARN: Slight mismatch ({abs(gcs_count - expected_count)} items)")
        else:
             logger.error(f"❌ FAIL: Major mismatch!")
             
    except Exception as e:
        logger.error(f"❌ FAIL: Count error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Pipeline Verification")
    parser.add_argument("mode", nargs="?", default="all", choices=["all", "duplicates", "view", "ids", "counts"])
    args = parser.parse_args()
    
    logger.info("\n=== BRINGO PIPELINE HEALTH CHECK ===\n")
    
    view_count = 0
    
    if args.mode in ["all", "duplicates"]:
        check_duplicates()
        
    if args.mode in ["all", "view"]:
        view_count = count_view_rows()
        
    if args.mode in ["all", "ids"]:
        inspect_gcs_id_format()
        
    if args.mode in ["all", "counts"]:
        verify_counts(expected_count=view_count)
        
    logger.info("\n=== CHECK COMPLETE ===\n")

if __name__ == "__main__":
    main()
