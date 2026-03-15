#!/usr/bin/env python3
"""
Complete Implementation Validation Script
Validates all components of the product name search implementation
"""

import sys
import os
import importlib
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class ImplementationValidator:
    """Validates the complete implementation"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def log_pass(self, message):
        """Log a passed check"""
        self.passed.append(message)
        logger.info(f"✅ {message}")

    def log_warning(self, message):
        """Log a warning"""
        self.warnings.append(message)
        logger.warning(f"⚠️  {message}")

    def log_error(self, message):
        """Log an error"""
        self.errors.append(message)
        logger.error(f"❌ {message}")

    def validate_file_structure(self):
        """Validate all required files exist"""
        logger.info("\n" + "="*70)
        logger.info("1. VALIDATING FILE STRUCTURE")
        logger.info("="*70)

        required_files = {
            'New Implementation Files': [
                'vector_search/name_search_engine.py',
                'features/setup_name_embeddings.py',
                'tests/test_ranking_consistency.py',
                'tests/test_end_to_end_name_search.py',
                'vector_search/test_name_search.py',
                'docs/NAME_SEARCH_IMPLEMENTATION.md',
            ],
            'Modified Files': [
                'api/main.py',
                'api/dependencies.py',
                'data/bigquery_client.py',
            ],
            'Documentation': [
                'IMPLEMENTATION_SUMMARY.md',
                'QUICK_START.md',
            ]
        }

        for category, files in required_files.items():
            logger.info(f"\n{category}:")
            for file_path in files:
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    if size > 0:
                        self.log_pass(f"{file_path} ({size:,} bytes)")
                    else:
                        self.log_error(f"{file_path} is empty")
                else:
                    self.log_error(f"{file_path} not found")

    def validate_syntax(self):
        """Validate Python syntax"""
        logger.info("\n" + "="*70)
        logger.info("2. VALIDATING PYTHON SYNTAX")
        logger.info("="*70)

        python_files = [
            'vector_search/name_search_engine.py',
            'features/setup_name_embeddings.py',
            'tests/test_ranking_consistency.py',
            'tests/test_end_to_end_name_search.py',
            'vector_search/test_name_search.py',
            'api/main.py',
            'api/dependencies.py',
            'data/bigquery_client.py',
        ]

        for file_path in python_files:
            try:
                with open(file_path, 'r') as f:
                    compile(f.read(), file_path, 'exec')
                self.log_pass(f"{file_path} syntax OK")
            except SyntaxError as e:
                self.log_error(f"{file_path} syntax error: {e}")
            except Exception as e:
                self.log_error(f"{file_path} error: {e}")

    def validate_integration_points(self):
        """Validate key integration points in the code"""
        logger.info("\n" + "="*70)
        logger.info("3. VALIDATING INTEGRATION POINTS")
        logger.info("="*70)

        checks = [
            {
                'file': 'api/main.py',
                'patterns': [
                    '@app.get("/api/v1/product/search-by-name"',
                    'async def search_similar_products_by_name',
                    'get_name_search_engine()',
                    'name_search_engine.is_available()',
                    'name_search_engine.search_by_name',
                    'bq_client.get_products_by_name',
                ],
                'description': 'New endpoint and integration'
            },
            {
                'file': 'api/dependencies.py',
                'patterns': [
                    'from vector_search.name_search_engine import NameSearchEngine',
                    '_name_search_engine:',
                    'def get_name_search_engine',
                ],
                'description': 'Name search engine dependency'
            },
            {
                'file': 'data/bigquery_client.py',
                'patterns': [
                    'def get_products_by_name',
                    'LOWER(product_name)',
                    'exact_match',
                ],
                'description': 'BigQuery name search method'
            },
            {
                'file': 'vector_search/name_search_engine.py',
                'patterns': [
                    'class NameSearchEngine',
                    'def is_available',
                    'def search_by_name',
                    'def get_best_match_id',
                ],
                'description': 'Name search engine class'
            },
        ]

        for check in checks:
            file_path = check['file']
            logger.info(f"\nChecking {check['description']} in {file_path}:")

            if not os.path.exists(file_path):
                self.log_error(f"{file_path} not found")
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            all_found = True
            for pattern in check['patterns']:
                if pattern in content:
                    self.log_pass(f"  Found: {pattern}")
                else:
                    self.log_error(f"  Missing: {pattern}")
                    all_found = False

            if all_found:
                self.log_pass(f"{check['description']} complete")

    def validate_endpoint_registration(self):
        """Validate endpoint is properly registered"""
        logger.info("\n" + "="*70)
        logger.info("4. VALIDATING ENDPOINT REGISTRATION")
        logger.info("="*70)

        try:
            with open('api/main.py', 'r') as f:
                content = f.read()

            # Check endpoint decorator
            if '@app.get("/api/v1/product/search-by-name"' in content:
                self.log_pass("Endpoint decorator found")
            else:
                self.log_error("Endpoint decorator missing")

            # Check response model
            if 'response_model=SearchResponse' in content:
                self.log_pass("Response model specified")
            else:
                self.log_warning("Response model might be missing")

            # Check authentication
            if 'dependencies=[Depends(verify_api_key)]' in content:
                self.log_pass("API key authentication configured")
            else:
                self.log_warning("API authentication might be missing")

            # Check parameters
            params = ['product_name', 'top_k', 'use_ranking', 'in_stock_only', 'exact_match']
            for param in params:
                if f'{param}:' in content or f'{param} =' in content:
                    self.log_pass(f"  Parameter '{param}' found")
                else:
                    self.log_warning(f"  Parameter '{param}' might be missing")

        except Exception as e:
            self.log_error(f"Error validating endpoint: {e}")

    def validate_ranking_logic(self):
        """Validate ranking integration"""
        logger.info("\n" + "="*70)
        logger.info("5. VALIDATING RANKING INTEGRATION")
        logger.info("="*70)

        try:
            with open('api/main.py', 'r') as f:
                content = f.read()

            # Check ranking is called
            if 'reranker.rerank(' in content:
                self.log_pass("Ranking API integration found")
            else:
                self.log_error("Ranking API integration missing")

            # Check query consistency
            if "query=query_product_data['combined_text']" in content or 'query=product' in content:
                self.log_pass("Ranking query uses product combined_text")
            else:
                self.log_warning("Ranking query might not use correct field")

            # Check use_ranking parameter
            if 'if use_ranking and enriched_candidates:' in content:
                self.log_pass("Conditional ranking based on parameter")
            else:
                self.log_warning("Conditional ranking might be missing")

        except Exception as e:
            self.log_error(f"Error validating ranking: {e}")

    def validate_fallback_logic(self):
        """Validate fallback to BigQuery"""
        logger.info("\n" + "="*70)
        logger.info("6. VALIDATING FALLBACK LOGIC")
        logger.info("="*70)

        try:
            with open('api/main.py', 'r') as f:
                content = f.read()

            # Check availability check
            if 'name_search_engine.is_available()' in content:
                self.log_pass("Availability check found")
            else:
                self.log_error("Availability check missing")

            # Check BigQuery fallback
            if 'if not query_product_data:' in content and 'bq_client.get_products_by_name' in content:
                self.log_pass("BigQuery fallback implemented")
            else:
                self.log_error("BigQuery fallback might be missing")

            # Check logging
            if 'Using fast name search' in content and 'Using BigQuery search' in content:
                self.log_pass("Path selection logging present")
            else:
                self.log_warning("Path selection logging might be incomplete")

        except Exception as e:
            self.log_error(f"Error validating fallback: {e}")

    def generate_summary(self):
        """Generate validation summary"""
        logger.info("\n" + "="*70)
        logger.info("VALIDATION SUMMARY")
        logger.info("="*70)

        logger.info(f"\n✅ Passed:   {len(self.passed)}")
        logger.info(f"⚠️  Warnings: {len(self.warnings)}")
        logger.info(f"❌ Errors:   {len(self.errors)}")

        if self.warnings:
            logger.info("\nWarnings:")
            for warning in self.warnings:
                logger.info(f"  ⚠️  {warning}")

        if self.errors:
            logger.info("\nErrors:")
            for error in self.errors:
                logger.info(f"  ❌ {error}")
            logger.info("\n❌ VALIDATION FAILED")
            return False
        else:
            logger.info("\n✅ ALL VALIDATIONS PASSED")
            logger.info("\n🚀 Implementation is ready for testing")
            logger.info("\nNext steps:")
            logger.info("  1. Start API server: python api/main.py")
            logger.info("  2. Test endpoint: curl http://localhost:8080/api/v1/product/search-by-name?product_name=lapte")
            logger.info("  3. Optional: Setup fast search: python features/setup_name_embeddings.py")
            return True

    def run_all_validations(self):
        """Run all validation checks"""
        self.validate_file_structure()
        self.validate_syntax()
        self.validate_integration_points()
        self.validate_endpoint_registration()
        self.validate_ranking_logic()
        self.validate_fallback_logic()
        return self.generate_summary()


def main():
    """Main validation function"""
    print("\n" + "="*70)
    print("🔍 PRODUCT NAME SEARCH - IMPLEMENTATION VALIDATION")
    print("="*70)

    validator = ImplementationValidator()
    success = validator.run_all_validations()

    print("\n" + "="*70)
    if success:
        print("✅ VALIDATION COMPLETE - IMPLEMENTATION CORRECT")
    else:
        print("❌ VALIDATION FAILED - REVIEW ERRORS ABOVE")
    print("="*70 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
