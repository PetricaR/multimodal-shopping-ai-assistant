"""
Text-Only Flow Verification Script
Tests the full search -> substitution flow using text-only queries
"""
import asyncio
import logging
import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from vector_search.search_engine import SearchEngine
from substitution.gemini_substitutor import GeminiSubstitutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_text_only_flow():
    """Test the complete text-only flow"""
    
    logger.info("=" * 60)
    logger.info("TEXT-ONLY FLOW VERIFICATION")
    logger.info("=" * 60)
    
    # Verify configuration
    logger.info(f"\n📋 Configuration Check:")
    logger.info(f"   • Generation Model: {settings.GENERATION_MODEL}")
    logger.info(f"   • Embedding Model: {settings.EMBEDDING_MODEL}")
    logger.info(f"   • Embedding Dimension: {settings.EMBEDDING_DIMENSION}")
    logger.info(f"   • Use Multimodal: {settings.USE_MULTIMODAL}")
    
    assert settings.GENERATION_MODEL == "gemini-3-flash-preview", "Wrong generation model!"
    assert settings.USE_MULTIMODAL == False, "Multimodal should be disabled!"
    
    logger.info("   ✅ Configuration verified\n")
    
    # Test 1: Vector Search with Text Query
    logger.info("🔍 Test 1: Text-based Vector Search")
    try:
        search_engine = SearchEngine()
        query = "lapte integral Zuzu"
        
        logger.info(f"   Searching for: '{query}'")
        results = search_engine.search_by_text(
            query_text=query,
            num_neighbors=10,
            filter_in_stock=True
        )
        
        logger.info(f"   ✅ Found {len(results)} products")
        if results:
            logger.info(f"   Top result: {results[0].get('product_name', 'N/A')}")
        
    except Exception as e:
        logger.error(f"   ❌ Search failed: {e}", exc_info=True)
        return False
    
    # Test 2: Gemini Substitution (Text-Only)
    logger.info("\n🤖 Test 2: Text-based Gemini Substitution")
    try:
        substitutor = GeminiSubstitutor()
        
        missing_product = {
            'product_name': 'Lapte Zuzu 3.5% 1L',
            'category': 'Lactate',
            'producer': 'Zuzu',
            'price': 8.5,
            'description': 'Lapte integral pasteurizat'
        }
        
        # Mock candidates and context
        candidates = results[:5] if results else []
        current_basket = []
        user_history = []
        
        logger.info(f"   Finding substitutes for: {missing_product['product_name']}")
        
        suggestions = substitutor.select_best(
            missing_product=missing_product,
            candidates=candidates,
            current_basket=current_basket,
            user_history=user_history,
            top_n=3
        )
        
        logger.info(f"   ✅ Generated {len(suggestions)} suggestions")
        for i, s in enumerate(suggestions, 1):
            logger.info(f"   {i}. {s.get('product_name', 'N/A')} ({s.get('gemini_confidence', 0):.2f} confidence)")
        
    except Exception as e:
        logger.error(f"   ❌ Substitution failed: {e}", exc_info=True)
        return False
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ ALL TESTS PASSED - Text-Only Flow Verified!")
    logger.info("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_text_only_flow()
    sys.exit(0 if success else 1)
