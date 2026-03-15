#!/usr/bin/env python3
"""
Feature Store API Availability Test
Validates that all required classes and methods exist in the installed SDK
"""

import sys

def test_sdk_version():
    """Test that google-cloud-aiplatform is installed with correct version"""
    try:
        import google.cloud.aiplatform as aiplatform
        version = aiplatform.__version__
        print(f"✓ google-cloud-aiplatform version: {version}")
        
        # Minimum version: 1.40.0 (as of Jan 2026)
        major, minor = map(int, version.split('.')[:2])
        if major >= 1 and minor >= 40:
            print(f"✓ SDK version is sufficient (>= 1.40.0)")
            return True
        else:
            print(f"⚠ SDK version may be outdated. Recommended: >= 1.40.0")
            return False
    except ImportError:
        print("✗ google-cloud-aiplatform not installed")
        print("  Install with: pip install google-cloud-aiplatform")
        return False

def test_feature_online_store_api():
    """Test FeatureOnlineStore class and methods"""
    try:
        from google.cloud import aiplatform
        
        # Test class exists
        assert hasattr(aiplatform, 'FeatureOnlineStore'), \
            "FeatureOnlineStore class not found"
        print("✓ aiplatform.FeatureOnlineStore class exists")
        
        # Test create_optimized_store method
        assert hasattr(aiplatform.FeatureOnlineStore, 'create_optimized_store'), \
            "create_optimized_store method not found"
        print("✓ FeatureOnlineStore.create_optimized_store() method exists")
        
        return True
    except AssertionError as e:
        print(f"✗ {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_feature_view_api():
    """Test FeatureView class and methods"""
    try:
        from google.cloud import aiplatform
        
        # Test class exists
        assert hasattr(aiplatform, 'FeatureView'), \
            "FeatureView class not found"
        print("✓ aiplatform.FeatureView class exists")
        
        # Test create method
        assert hasattr(aiplatform.FeatureView, 'create'), \
            "create method not found"
        print("✓ FeatureView.create() method exists")
        
        # Test SyncConfig
        assert hasattr(aiplatform.FeatureView, 'SyncConfig'), \
            "SyncConfig not found"
        print("✓ FeatureView.SyncConfig class exists")
        
        return True
    except AssertionError as e:
        print(f"✗ {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_feature_online_store_service_client():
    """Test FeatureOnlineStoreServiceClient and methods"""
    try:
        from google.cloud import aiplatform_v1
        
        # Test client class
        assert hasattr(aiplatform_v1, 'FeatureOnlineStoreServiceClient'), \
            "FeatureOnlineStoreServiceClient not found"
        print("✓ aiplatform_v1.FeatureOnlineStoreServiceClient class exists")
        
        # Initialize client (won't connect, just tests class availability)
        client = aiplatform_v1.FeatureOnlineStoreServiceClient()
        
        # Test fetch_feature_values method
        assert hasattr(client, 'fetch_feature_values'), \
            "fetch_feature_values method not found"
        print("✓ client.fetch_feature_values() method exists")
        
        # Test search_nearest_entities method
        assert hasattr(client, 'search_nearest_entities'), \
            "search_nearest_entities method not found"
        print("✓ client.search_nearest_entities() method exists")
        
        return True
    except AssertionError as e:
        print(f"✗ {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_utils():
    """Test utility classes for BigQuery source"""
    try:
        from google.cloud import aiplatform
        
        # Test FeatureViewBigQuerySource
        assert hasattr(aiplatform.utils, 'FeatureViewBigQuerySource'), \
            "FeatureViewBigQuerySource not found"
        print("✓ aiplatform.utils.FeatureViewBigQuerySource class exists")
        
        return True
    except AssertionError as e:
        print(f"✗ {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def main():
    """Run all API availability tests"""
    print("=" * 70)
    print("VERTEX AI FEATURE STORE - API AVAILABILITY TEST")
    print("=" * 70)
    print()
    
    tests = [
        ("SDK Version", test_sdk_version),
        ("FeatureOnlineStore API", test_feature_online_store_api),
        ("FeatureView API", test_feature_view_api),
        ("FeatureOnlineStoreServiceClient API", test_feature_online_store_service_client),
        ("Utility Classes", test_utils),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        results.append(test_func())
        print()
    
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All API availability tests passed!")
        print("✓ Feature Store implementation is ready to deploy")
        sys.exit(0)
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        print("⚠ Please update google-cloud-aiplatform:")
        print("  pip install --upgrade google-cloud-aiplatform")
        sys.exit(1)

if __name__ == "__main__":
    main()
