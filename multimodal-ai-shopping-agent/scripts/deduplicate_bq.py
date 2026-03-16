import logging
import sys
from pathlib import Path
from google.cloud import bigquery

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def deduplicate_table():
    client = bigquery.Client(project=settings.PROJECT_ID)
    table_id = f"{settings.PROJECT_ID}.{settings.BQ_DATASET}.{settings.BQ_TABLE}"
    
    logger.info(f"🛑 Starting Deduplication for table: {table_id}")
    
    # 1. Get current count
    query_count = f"SELECT COUNT(*) FROM `{table_id}`"
    initial_count = client.query(query_count).to_dataframe().iloc[0][0]
    logger.info(f"📊 Initial Row Count: {initial_count}")
    
    # 2. Execute CREATE OR REPLACE
    # We use partition by product_id and keep the one that is in_stock first, or just arbitrary.
    query = f"""
    CREATE OR REPLACE TABLE `{table_id}` AS
    SELECT * EXCEPT(row_num)
    FROM (
      SELECT *,
        ROW_NUMBER() OVER (
          PARTITION BY product_id 
          ORDER BY in_stock DESC, product_name
        ) as row_num
      FROM `{table_id}`
    )
    WHERE row_num = 1
    """
    
    logger.info("⏳ Running Deduplication Query (this may take a moment)...")
    job = client.query(query)
    job.result() # Wait for completion
    
    # 3. Get final count
    final_count = client.query(query_count).to_dataframe().iloc[0][0]
    logger.info(f"✅ Deduplication Complete.")
    logger.info(f"📊 Final Row Count: {final_count}")
    logger.info(f"🗑️  Removed {initial_count - final_count} duplicates.")

if __name__ == "__main__":
    deduplicate_table()
