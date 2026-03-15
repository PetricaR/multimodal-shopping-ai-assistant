#!/usr/bin/env python3
"""
Debug Feature Store: check what entity IDs are actually stored
and what format the product_id column has in BigQuery.
"""
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def check_bq_schema():
    """Check the product_id column type in BigQuery."""
    from google.cloud import bigquery

    client = bigquery.Client(project="formare-ai")
    table = client.get_table("formare-ai.bringo_products_data.bringo_products_native")

    logger.info("BigQuery table schema:")
    for field in table.schema:
        marker = " <-- entity ID column" if field.name == "product_id" else ""
        logger.info(f"  {field.name}: {field.field_type} ({field.mode}){marker}")

    logger.info(f"\nTotal rows: {table.num_rows}")

    # Check actual product_id values
    query = """
        SELECT product_id, TYPEOF(product_id) as type_name
        FROM `formare-ai.bringo_products_data.bringo_products_native`
        LIMIT 5
    """
    rows = list(client.query(query).result())
    logger.info("\nSample product_id values:")
    for row in rows:
        logger.info(f"  product_id={row.product_id!r}  type={row.type_name}")


def check_feature_view_config():
    """Check the Feature View configuration details."""
    from google.cloud import aiplatform_v1
    from google.api_core import client_options

    api_endpoint = "europe-west1-aiplatform.googleapis.com"
    client = aiplatform_v1.FeatureOnlineStoreAdminServiceClient(
        client_options=client_options.ClientOptions(api_endpoint=api_endpoint)
    )

    feature_view_name = (
        "projects/formare-ai/locations/europe-west1/"
        "featureOnlineStores/bringo_realtime_features/"
        "featureViews/bringo_feature_store"
    )

    view = client.get_feature_view(name=feature_view_name)
    logger.info("\nFeature View config:")
    logger.info(f"  Name: {view.name}")
    logger.info(f"  BQ URI: {view.big_query_source.uri}")
    logger.info(f"  Entity ID columns: {list(view.big_query_source.entity_id_columns)}")
    logger.info(f"  Sync config: {view.sync_config}")


def try_fetch_with_different_formats():
    """Try fetching with different ID formats to find what works."""
    from google.cloud.aiplatform_v1 import FeatureOnlineStoreServiceClient
    from google.cloud.aiplatform_v1.types import feature_online_store_service
    from google.api_core import client_options
    from config.settings import settings

    client = FeatureOnlineStoreServiceClient(
        client_options=client_options.ClientOptions(
            api_endpoint=settings.FS_PUBLIC_ENDPOINT
        )
    )

    feature_view = (
        "projects/formare-ai/locations/europe-west1/"
        "featureOnlineStores/bringo_realtime_features/"
        "featureViews/bringo_feature_store"
    )

    # Try different formats for product_id 32377185
    test_keys = [
        "32377185",           # string
        "32377185.0",         # float-like string
        "Cafea Boabe Espresso 500G Carrefour Extra",  # product name (old format?)
    ]

    logger.info("\nTrying different entity ID formats:")
    for key in test_keys:
        try:
            data_key = feature_online_store_service.FeatureViewDataKey(key=key)
            request = feature_online_store_service.FetchFeatureValuesRequest(
                feature_view=feature_view,
                data_key=data_key,
            )
            response = client.fetch_feature_values(request=request)
            logger.info(f"  ✅ key={key!r} → FOUND")

            # Print features
            for fv in response.key_values.features:
                field = fv.value._pb.WhichOneof("value")
                val = getattr(fv.value, field) if field else None
                logger.info(f"      {fv.name}: {val}")
            return
        except Exception as e:
            logger.info(f"  ❌ key={key!r} → {e}")


def main():
    logger.info("=" * 80)
    logger.info("DEBUG FEATURE STORE")
    logger.info("=" * 80)

    check_bq_schema()
    check_feature_view_config()
    try_fetch_with_different_formats()


if __name__ == "__main__":
    main()
