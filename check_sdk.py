
import google.generativeai as genai
import inspect

print(f"GenAI Version: {genai.__version__}")

try:
    model = genai.GenerativeModel('gemini-pro')
    print("GenerativeModel initialized.")
    
    # Check generate_content signature
    sig = inspect.signature(model.generate_content)
    print(f"generate_content signature: {sig}")
    
    # Check configure signature
    sig_conf = inspect.signature(genai.configure)
    print(f"configure signature: {sig_conf}")
    
except Exception as e:
    print(f"Error: {e}")
