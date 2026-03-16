import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path before imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Mock dependencies that are not needed for prompt building
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()

from substitution.gemini_substitutor import GeminiSubstitutor

def test_reproduce_error():
    print("🚀 Reproducing top_n NameError...")
    substitutor = GeminiSubstitutor()
    
    missing_product = {
        'product_name': 'Test Product',
        'category': 'Test Category',
        'producer': 'Test Producer',
        'price': 10.0,
        'description': 'Test Description'
    }
    candidates = [
        {'id': '1', 'product_name': 'Candidate 1', 'category': 'Test Category', 'price': 11.0}
    ]
    current_basket = []
    user_history = []
    
    try:
        # This should trigger the NameError during prompt building
        substitutor.select_best(
            missing_product=missing_product,
            candidates=candidates,
            current_basket=current_basket,
            user_history=user_history,
            top_n=3
        )
        print("❌ Error: Expected NameError but call succeeded (might be due to mock generate_content)")
    except NameError as e:
        print(f"✅ Successfully reproduced NameError: {e}")
    except Exception as e:
        print(f"⚠️ Caught unexpected exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    # Add project root to sys.path
    import os
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    sys.path.append(str(project_root))
    
    test_reproduce_error()
