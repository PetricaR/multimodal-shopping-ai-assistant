
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data import BigQueryClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inspect_bq")

def main():
    client = BigQueryClient()
    logger.info("Fetching sample products from BigQuery...")
    df = client.fetch_products(limit=10)
    
    if df.empty:
        logger.warning("No products found in BigQuery.")
        return

    logger.info(f"Columns found: {df.columns.tolist()}")
    
    cols_to_check = ['product_name', 'product_id', 'variant_id', 'category', 'store', 'price_ron']
    present_cols = [c for c in cols_to_check if c in df.columns]
    
    logger.info("Sample Data:")
    print(df[present_cols].to_string())
    
    # Check for nulls in critical fields
    for col in ['product_id', 'variant_id', 'product_name']:
        if col in df.columns:
            null_count = df[col].isna().sum()
            logger.info(f"Field '{col}' null count: {null_count} / {len(df)}")
            
            # Check format of variant_id
            if col == 'variant_id' and null_count < len(df):
                sample_variants = df[col].dropna().head(3).tolist()
                logger.info(f"Sample variant_ids: {sample_variants}")

if __name__ == "__main__":
    main()
