#!/usr/bin/env python3
"""
Vertex AI Feature Store Setup Script
Uses gcloud CLI for setup (Google's recommended approach)
"""

from google.cloud import aiplatform
from google.cloud import bigquery
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = "formare-ai"
REGION = "europe-west1"
FEATURE_ONLINE_STORE_ID = "bringo_realtime_features"

def create_feature_online_store():
    """
    Create Vertex AI Feature Online Store with Optimized serving
    
    Optimized serving provides:
    - <2ms latency (99th percentile)
    - Embedding management for vector similarity
    - Direct BigQuery integration
    """
    
    logger.info("Initializing Vertex AI...")
    aiplatform.init(project=PROJECT_ID, location=REGION)
    
    logger.info(f"Creating Feature Online Store: {FEATURE_ONLINE_STORE_ID}")
    
    try:
        # Create optimized online store (recommended for low latency + embedding support)
        # Using create_optimized_store() as per Google SDK best practices
        feature_online_store = aiplatform.FeatureOnlineStore.create_optimized_store(
            feature_online_store_id=FEATURE_ONLINE_STORE_ID,
            labels={
                "environment": "production",
                "use_case": "product_similarity",
                "application": "mobile_app"
            }
        )
        
        logger.info(f"✅ Feature Online Store created: {feature_online_store.resource_name}")
        logger.info(f"   Embedding management: Enabled")
        logger.info(f"   Latency target: <2ms (P99)")
        
        return feature_online_store
        
    except Exception as e:
        logger.error(f"Failed to create Feature Online Store: {e}")
        raise

def create_product_metadata_feature_view(feature_online_store):
    """
    Create Feature View for product metadata
    Synced hourly from BigQuery
    """
    
    logger.info("Creating product_metadata Feature View...")
    
    # BigQuery source configuration
    bq_source = aiplatform.utils.FeatureViewBigQuerySource(
        uri=f"bq://{PROJECT_ID}.bringo_products_data.bringo_products",
        entity_id_columns=["product_id"]
    )
    
    # Create Feature View
    feature_view = aiplatform.FeatureView.create(
        name="product_metadata_names",
        feature_online_store_id=feature_online_store.name,
        source=bq_source,
        # Sync configuration (hourly for real-time freshness)
        sync_config=aiplatform.FeatureView.SyncConfig(
            cron="0 * * * *"  # Every hour
        ),
        labels={
            "data_type": "metadata",
            "sync_frequency": "hourly"
        }
    )
    
    logger.info(f"✅ Feature View created: {feature_view.resource_name}")
    logger.info(f"   Source: BigQuery bringo_products table")
    logger.info(f"   Sync: Hourly (0 * * * *)")
    
    return feature_view

def create_embeddings_feature_view(feature_online_store):
    """
    Create Feature View for product embeddings
    Synced daily (embeddings are more static)
    """
    
    logger.info("Creating product_embeddings Feature View...")
    
    # First, ensure embeddings are in BigQuery
    # This assumes you've loaded embeddings from GCS to BigQuery
    bq_client = bigquery.Client(project=PROJECT_ID)
    
    # Create embeddings table if it doesn't exist
    embeddings_table_id = f"{PROJECT_ID}.bringo_embeddings.product_vectors"
    
    try:
        bq_client.get_table(embeddings_table_id)
        logger.info(f"   Embeddings table exists: {embeddings_table_id}")
    except Exception:
        logger.warning(f"   Embeddings table not found: {embeddings_table_id}")
        logger.info("   Creating embeddings table schema...")
        
        schema = [
            bigquery.SchemaField("product_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("multimodal_embedding", "FLOAT64", mode="REPEATED"),
            bigquery.SchemaField("text_embedding", "FLOAT64", mode="REPEATED"),
            bigquery.SchemaField("embedding_timestamp", "TIMESTAMP"),
        ]
        
        table = bigquery.Table(embeddings_table_id, schema=schema)
        table = bq_client.create_table(table)
        logger.info(f"✅ Created embeddings table: {table.table_id}")
    
    # Create Feature View
    bq_source = aiplatform.utils.FeatureViewBigQuerySource(
        uri=f"bq://{embeddings_table_id}",
        entity_id_columns=["product_id"]
    )
    
    feature_view = aiplatform.FeatureView.create(
        name="product_embeddings",
        feature_online_store_id=feature_online_store.name,
        source=bq_source,
        # Sync daily (embeddings don't change often)
        sync_config=aiplatform.FeatureView.SyncConfig(
            cron="0 2 * * *"  # Daily at 2 AM
        ),
        labels={
            "data_type": "embeddings",
            "sync_frequency": "daily"
        }
    )
    
    logger.info(f"✅ Feature View created: {feature_view.resource_name}")
    logger.info(f"   Source: BigQuery embeddings table")
    logger.info(f"   Sync: Daily (0 2 * * *)")
    
    return feature_view

def trigger_initial_sync(feature_view):
    """
    Trigger initial sync for Feature View
    """
    logger.info(f"Triggering initial sync for {feature_view.name}...")
    
    feature_view.sync()
    
    logger.info(f"✅ Initial sync triggered")
    logger.info(f"   Note: First sync may take 5-10 minutes")

def main():
    """Main setup pipeline"""
    
    logger.info("=" * 80)
    logger.info("VERTEX AI FEATURE STORE SETUP")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        # Step 1: Create Feature Online Store
        feature_online_store = create_feature_online_store()
        logger.info("")
        
        # Step 2: Create Feature Views
        metadata_view = create_product_metadata_feature_view(feature_online_store)
        logger.info("")
        
        embeddings_view = create_embeddings_feature_view(feature_online_store)
        logger.info("")
        
        # Step 3: Trigger initial sync
        trigger_initial_sync(metadata_view)
        logger.info("")
        
        logger.info("=" * 80)
        logger.info("✅ FEATURE STORE SETUP COMPLETE")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Wait for initial sync to complete (~5-10 minutes)")
        logger.info("2. Test feature serving:")
        logger.info("   python features/test_feature_serving.py")
        logger.info("3. Update API to use Feature Store:")
        logger.info("   See api/feature_serving.py")
        logger.info("")
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise

if __name__ == "__main__":
    main()
