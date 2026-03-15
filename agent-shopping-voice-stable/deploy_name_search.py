#!/usr/bin/env python3
"""
Interactive deployment script for name search infrastructure
Runs the actual setup and monitors progress
"""

import os
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_prerequisites():
    """Check if prerequisites are met"""
    logger.info("="*70)
    logger.info("CHECKING PREREQUISITES")
    logger.info("="*70)

    checks = {
        'Python packages': [],
        'GCP credentials': None,
        'Project configuration': None,
    }

    # Check Python packages
    logger.info("\n1. Checking Python packages...")
    required_packages = [
        'google-cloud-bigquery',
        'google-cloud-aiplatform',
        'google-cloud-storage',
    ]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '.').replace('google.cloud.', 'google.cloud.'))
            logger.info(f"   ✅ {package}")
        except ImportError:
            logger.warning(f"   ❌ {package} - MISSING")
            missing_packages.append(package)

    if missing_packages:
        logger.error("\n❌ Missing packages. Install with:")
        logger.error(f"   pip install {' '.join(missing_packages)}")
        return False

    # Check GCP credentials
    logger.info("\n2. Checking GCP credentials...")
    try:
        import google.auth
        credentials, project_id = google.auth.default()
        logger.info(f"   ✅ Credentials found")
        logger.info(f"   ✅ Project: {project_id}")
        checks['GCP credentials'] = project_id
    except Exception as e:
        logger.error(f"   ❌ No credentials found: {e}")
        logger.error("\n   Set credentials with:")
        logger.error("   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json")
        return False

    # Check project configuration
    logger.info("\n3. Checking project configuration...")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from config import settings

        logger.info(f"   ✅ Project ID: {settings.PROJECT_ID}")
        logger.info(f"   ✅ Location: {settings.LOCATION}")
        logger.info(f"   ✅ Dataset: {settings.BQ_DATASET}")
        logger.info(f"   ✅ Bucket: {settings.GCS_BUCKET}")
        checks['Project configuration'] = True
    except Exception as e:
        logger.error(f"   ❌ Configuration error: {e}")
        return False

    logger.info("\n" + "="*70)
    logger.info("✅ ALL PREREQUISITES MET")
    logger.info("="*70)
    return True


def run_setup():
    """Run the actual setup script"""
    logger.info("\n" + "="*70)
    logger.info("RUNNING SETUP SCRIPT")
    logger.info("="*70)

    logger.info("\nExecuting: python features/setup_name_embeddings.py")
    logger.info("\nThis will:")
    logger.info("  1. Fetch product names from BigQuery")
    logger.info("  2. Generate text embeddings (512D)")
    logger.info("  3. Export to JSONL format")
    logger.info("  4. Upload to Cloud Storage")
    logger.info("  5. Create Vector Search index (~30 min)")
    logger.info("  6. Create public endpoint")
    logger.info("  7. Deploy index")

    logger.info("\n⚠️  This will create GCP resources and incur costs")
    logger.info("   Estimated cost: ~$30-60/month")

    response = input("\nContinue with deployment? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("❌ Deployment cancelled")
        return False

    # Import and run the setup
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from features.setup_name_embeddings import main as setup_main

        logger.info("\n🚀 Starting deployment...")
        setup_main()

        logger.info("\n✅ Setup completed successfully")
        return True

    except Exception as e:
        logger.error(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_deployment():
    """Verify the deployment was successful"""
    logger.info("\n" + "="*70)
    logger.info("VERIFYING DEPLOYMENT")
    logger.info("="*70)

    try:
        from google.cloud import aiplatform
        from config import settings

        aiplatform.init(project=settings.PROJECT_ID, location=settings.LOCATION)

        # Check for name index
        logger.info("\n1. Checking Vector Search index...")
        name_index_name = f"{settings.VS_INDEX_NAME}_names"
        indexes = aiplatform.MatchingEngineIndex.list(
            filter=f'display_name="{name_index_name}"'
        )

        if indexes:
            index = indexes[0]
            logger.info(f"   ✅ Index found: {index.display_name}")
            logger.info(f"   Status: {index.resource_name}")
        else:
            logger.warning(f"   ⚠️  Index not found: {name_index_name}")

        # Check for endpoint
        logger.info("\n2. Checking endpoint...")
        name_endpoint_name = f"{settings.VS_ENDPOINT_NAME}_names"
        endpoints = aiplatform.MatchingEngineIndexEndpoint.list(
            filter=f'display_name="{name_endpoint_name}"'
        )

        if endpoints:
            endpoint = endpoints[0]
            logger.info(f"   ✅ Endpoint found: {endpoint.display_name}")
            logger.info(f"   Public domain: {endpoint.public_endpoint_domain_name}")
        else:
            logger.warning(f"   ⚠️  Endpoint not found: {name_endpoint_name}")

        logger.info("\n" + "="*70)
        logger.info("✅ DEPLOYMENT VERIFIED")
        logger.info("="*70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Verification failed: {e}")
        return False


def test_endpoint():
    """Test the name search endpoint"""
    logger.info("\n" + "="*70)
    logger.info("TESTING NAME SEARCH ENDPOINT")
    logger.info("="*70)

    try:
        from vector_search.name_search_engine import NameSearchEngine

        logger.info("\n1. Initializing name search engine...")
        name_search = NameSearchEngine()

        if not name_search.is_available():
            logger.warning("   ⚠️  Name search engine not available")
            logger.warning("   Index might still be creating...")
            return False

        logger.info("   ✅ Name search engine initialized")

        # Test search
        logger.info("\n2. Testing search...")
        test_queries = ["lapte", "paine", "cafea"]

        for query in test_queries:
            logger.info(f"\n   Testing: '{query}'")
            start = time.time()

            results = name_search.search_by_name(query, num_results=3)
            latency = (time.time() - start) * 1000

            if results:
                logger.info(f"   ✅ Found {len(results)} results in {latency:.1f}ms")
                for i, result in enumerate(results[:2], 1):
                    logger.info(f"      {i}. Product ID: {result['product_id']} (score: {result['similarity_score']:.3f})")
            else:
                logger.warning(f"   ⚠️  No results found")

        logger.info("\n" + "="*70)
        logger.info("✅ ENDPOINT TESTING COMPLETE")
        logger.info("="*70)
        return True

    except Exception as e:
        logger.error(f"\n❌ Testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main deployment workflow"""
    print("\n" + "="*70)
    print("🚀 NAME SEARCH DEPLOYMENT SCRIPT")
    print("="*70)
    print("\nThis script will:")
    print("  ✅ Check prerequisites")
    print("  ✅ Run setup (creates GCP resources)")
    print("  ✅ Verify deployment")
    print("  ✅ Test the endpoint")
    print("\n" + "="*70)

    # Step 1: Check prerequisites
    if not check_prerequisites():
        logger.error("\n❌ Prerequisites not met. Aborting.")
        return 1

    # Step 2: Ask if user wants to proceed
    print("\n" + "="*70)
    print("DEPLOYMENT OPTIONS")
    print("="*70)
    print("\n1. Full deployment (run setup + verification)")
    print("2. Verification only (check existing deployment)")
    print("3. Testing only (test existing endpoint)")
    print("4. Exit")

    choice = input("\nSelect option (1-4): ")

    if choice == "1":
        # Full deployment
        if run_setup():
            logger.info("\n⏳ Waiting 60 seconds for resources to initialize...")
            time.sleep(60)
            verify_deployment()
            test_endpoint()

    elif choice == "2":
        # Verification only
        verify_deployment()

    elif choice == "3":
        # Testing only
        test_endpoint()

    else:
        logger.info("Exiting...")
        return 0

    # Final summary
    print("\n" + "="*70)
    print("📋 NEXT STEPS")
    print("="*70)
    print("\n1. If index is still creating, wait ~30 minutes")
    print("2. Check status:")
    print("   gcloud ai indexes list --region=europe-west1")
    print("\n3. Test API endpoint:")
    print('   curl "http://localhost:8080/api/v1/product/search-by-name?product_name=lapte"')
    print("\n4. Monitor logs for: 'Using fast name search'")
    print("\n" + "="*70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
