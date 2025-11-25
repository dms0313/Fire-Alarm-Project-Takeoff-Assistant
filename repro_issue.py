
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.gemini_analyzer import GeminiFireAlarmAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repro_debug")

def test_generate_model_text():
    print("Testing _generate_model_text behavior...")
    
    # Initialize with dummy key to avoid error in __init__
    analyzer = GeminiFireAlarmAnalyzer(api_key="dummy_key")
    
    # Mock the model to avoid actual API calls (though we expect it to not even reach the model)
    analyzer.model = "dummy_model" 
    
    # Call the method
    result = analyzer._generate_model_text("test prompt")
    
    print(f"Result: {result}")
    
    if result is None:
        print("❌ _generate_model_text returned None. Issue CONFIRMED.")
    else:
        print("✅ _generate_model_text returned a value. Issue NOT reproduced.")

if __name__ == "__main__":
    test_generate_model_text()
