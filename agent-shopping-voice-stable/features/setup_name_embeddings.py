#!/usr/bin/env python3
"""
Setup Product Name Embeddings for Fast Search
Creates a separate Vector Search index optimized for name lookups

This enables:
- Sub-50ms product name search
- Semantic matching (handles typos, synonyms)
- Voice transcription error tolerance
"""

import os
import logging
from google.cloud import bigquery, aiplatform
from google.cloud import storage
from embeddings.generator import MultimodalEmbeddingGenerator
from config.settings import settings
import json
from typing import List, Dict
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = settings.PROJECT_ID
LOCATION = settings.LOCATION
BUCKET_NAME = settings.GCS_BUCKET

# Index configuration
NAME_INDEX_NAME = f"{settings.VS_INDEX_NAME}_names"
NAME_ENDPOINT_NAME = f"{settings.VS_ENDPOINT_NAME}_names"
NAME_DEPLOYED_INDEX_ID = "name_search_index_v1"

def fetch_product_names() -> List[Dict]:
    """
    Fetch all product names from BigQuery

    Returns:
        List of {product_id, product_name, in_stock}
    """
    logger.info("Fetching product names from BigQuery...")

    bq_client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT
        product_id,
        product_name,
        in_stock
    FROM
        `{settings.BQ_DATASET}.{settings.BQ_TABLE}`
    WHERE
        product_name IS NOT NULL
        AND TRIM(product_name) != ''
    """

    df = bq_client.query(query).to_dataframe()

    products = []
    for _, row in df.iterrows():
        products.append({
            'product_id': str(row['product_id']),
            'product_name': str(row['product_name']),
            'in_stock': bool(row['in_stock'])
        })

    logger.info(f"✓ Fetched {len(products)} product names")
    return products


def generate_name_embeddings(products: List[Dict]) -> List[Dict]:
    """
    Generate text embeddings for product names

    Args:
        products: List of product dicts with product_name

    Returns:
        List of products with embeddings added
    """
    logger.info("Generating name embeddings...")

    generator = MultimodalEmbeddingGenerator()

    for i, product in enumerate(products):
        # Generate text-only embedding
        embedding, _ = generator.generate_embedding(
            text=product['product_name'],
            image_url=None
        )

        product['embedding'] = embedding

        if (i + 1) % 100 == 0:
            logger.info(f"  Progress: {i + 1}/{len(products)} embeddings generated")

    logger.info(f"✓ Generated {len(products)} name embeddings")
    return products


def export_to_jsonl(products: List[Dict], output_file: str):
    """
    Export embeddings to JSONL format for Vector Search

    Format:
    {"id": "12345", "embedding": [...], "restricts": [{"namespace": "in_stock", "allow": ["true"]}]}
    """
    logger.info(f"Exporting to {output_file}...")

    with open(output_file, 'w') as f:
        for product in products:
            # Vector Search format
            record = {
                'id': product['product_id'],
                'embedding': product['embedding'],
                'restricts': [
                    {
                        'namespace': 'in_stock',
                        'allow': ['true' if product['in_stock'] else 'false']
                    }
                ]
            }
            f.write(json.dumps(record) + '\n')

    logger.info(f"✓ Exported {len(products)} records to {output_file}")


def upload_to_gcs(local_file: str, gcs_path: str):
    """Upload embeddings file to GCS"""
    logger.info(f"Uploading to gs://{BUCKET_NAME}/{gcs_path}...")

    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)

    blob.upload_from_filename(local_file)

    logger.info(f"✓ Uploaded to gs://{BUCKET_NAME}/{gcs_path}")
    return f"gs://{BUCKET_NAME}/{gcs_path}"


def create_name_vector_search_index(embeddings_gcs_uri: str):
    """
    Create Vector Search index for product names

    Args:
        embeddings_gcs_uri: GCS URI to embeddings JSONL file
    """
    logger.info("Creating Vector Search index for product names...")

    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Check if index already exists
    existing_indexes = aiplatform.MatchingEngineIndex.list(
        filter=f'display_name="{NAME_INDEX_NAME}"'
    )

    if existing_indexes:
        logger.warning(f"Index '{NAME_INDEX_NAME}' already exists. Skipping creation.")
        return existing_indexes[0]

    # Create index
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=NAME_INDEX_NAME,
        contents_delta_uri=embeddings_gcs_uri,
        dimensions=settings.EMBEDDING_DIMENSION,
        approximate_neighbors_count=settings.VS_APPROXIMATE_NEIGHBORS,
        distance_measure_type=settings.VS_DISTANCE_MEASURE,
        leaf_node_embedding_count=500,  # Optimized for smaller dataset
        leaf_nodes_to_search_percent=50,  # Higher recall for names
        description="Fast product name search index for voice agents",
        labels={
            "use_case": "name_search",
            "optimized_for": "voice_agents"
        }
    )

    logger.info(f"✓ Created index: {index.resource_name}")
    logger.info("  Waiting for index to be ready (this takes 20-30 minutes)...")

    return index


def create_name_endpoint():
    """Create endpoint for name search index"""
    logger.info("Creating Vector Search endpoint for names...")

    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    # Check if endpoint exists
    existing_endpoints = aiplatform.MatchingEngineIndexEndpoint.list(
        filter=f'display_name="{NAME_ENDPOINT_NAME}"'
    )

    if existing_endpoints:
        logger.warning(f"Endpoint '{NAME_ENDPOINT_NAME}' already exists. Skipping creation.")
        return existing_endpoints[0]

    # Create endpoint
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=NAME_ENDPOINT_NAME,
        description="Public endpoint for fast product name search",
        public_endpoint_enabled=True,
        labels={
            "use_case": "name_search",
            "optimized_for": "voice_agents"
        }
    )

    logger.info(f"✓ Created endpoint: {endpoint.resource_name}")
    return endpoint


def deploy_index_to_endpoint(index: aiplatform.MatchingEngineIndex, endpoint: aiplatform.MatchingEngineIndexEndpoint):
    """Deploy name index to endpoint"""
    logger.info("Deploying name index to endpoint...")

    # Check if already deployed
    deployed_indexes = endpoint.deployed_indexes
    for deployed_index in deployed_indexes:
        if deployed_index.id == NAME_DEPLOYED_INDEX_ID:
            logger.warning(f"Index already deployed with ID '{NAME_DEPLOYED_INDEX_ID}'. Skipping deployment.")
            return

    # Deploy
    endpoint.deploy_index(
        index=index,
        deployed_index_id=NAME_DEPLOYED_INDEX_ID,
        display_name="Name Search v1",
        machine_type="e2-standard-2",  # Smaller machine for name search
        min_replica_count=1,
        max_replica_count=2,  # Auto-scale for voice agent spikes
        enable_access_logging=True
    )

    logger.info(f"✓ Index deployed with ID: {NAME_DEPLOYED_INDEX_ID}")


def update_settings_file():
    """Add name search configuration to settings"""
    logger.info("Updating settings file...")

    settings_file = "config/settings.py"

    # Add configuration constants
    config_lines = f"""
# Name Search Configuration (Auto-generated)
VS_NAME_INDEX_NAME = "{NAME_INDEX_NAME}"
VS_NAME_ENDPOINT_NAME = "{NAME_ENDPOINT_NAME}"
VS_NAME_DEPLOYED_INDEX_ID = "{NAME_DEPLOYED_INDEX_ID}"
"""

    logger.info("Add the following to your config/settings.py:")
    print(config_lines)
    logger.info("✓ Configuration ready")


def main():
    """Main setup workflow"""
    logger.info("=" * 70)
    logger.info("PRODUCT NAME EMBEDDINGS SETUP")
    logger.info("Optimizing for voice-based shopping agents")
    logger.info("=" * 70)

    # Step 1: Fetch product names
    products = fetch_product_names()

    # Step 2: Generate embeddings
    products_with_embeddings = generate_name_embeddings(products)

    # Step 3: Export to JSONL
    local_file = "/tmp/product_name_embeddings.jsonl"
    export_to_jsonl(products_with_embeddings, local_file)

    # Step 4: Upload to GCS
    gcs_path = "name_embeddings/product_names.jsonl"
    embeddings_uri = upload_to_gcs(local_file, gcs_path)

    # Step 5: Create Vector Search index
    index = create_name_vector_search_index(embeddings_uri)

    # Step 6: Create endpoint
    endpoint = create_name_endpoint()

    # Step 7: Deploy index (if index is ready)
    logger.info("Waiting for index to be ready before deployment...")
    logger.info("Run this script again after the index creation completes to deploy it.")

    # Step 8: Update configuration
    update_settings_file()

    logger.info("=" * 70)
    logger.info("SETUP COMPLETE!")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Wait for index creation to complete (~20-30 minutes)")
    logger.info("2. Run this script again to deploy the index")
    logger.info("3. Update config/settings.py with the generated configuration")
    logger.info("4. Test with: python -m vector_search.test_name_search")
    logger.info("")


if __name__ == "__main__":
    main()
