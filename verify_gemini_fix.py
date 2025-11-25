
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.gemini_analyzer import GeminiFireAlarmAnalyzer
from tenacity import RetryError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_fix")

def verify_fix():
    print("Verifying Gemini API Fix...")
    
    analyzer = GeminiFireAlarmAnalyzer()
    
    if not analyzer.is_available():
        print("❌ Gemini Analyzer not available. Check API Key.")
        return

    print("✅ Gemini Analyzer initialized.")
    
    # Check if _generate_model_text exists
    if hasattr(analyzer, '_generate_model_text'):
        print("✅ _generate_model_text method found.")
    else:
        print("❌ _generate_model_text method NOT found.")
        return

    # Try a simple generation
    try:
        print("Testing API call with _generate_model_text and safety settings...")
        # Inspect the method to ensure safety_settings are used (static analysis check)
        import inspect
        source = inspect.getsource(analyzer._generate_model_text)
        if "safety_settings" in source and "HarmBlockThreshold.BLOCK_NONE" in source:
             print("✅ Safety settings configuration found in source code.")
        else:
             print("❌ Safety settings configuration NOT found in source code.")

        response_text = analyzer._generate_model_text("Hello, are you working?")
        if response_text:
            print(f"✅ API Call Successful. Response: {response_text[:50]}...")
        else:
            print("❌ API Call Failed: Returned None or empty string.")
            
    except Exception as e:
        print(f"❌ API Call Failed: {e}")

if __name__ == "__main__":
    verify_fix()
