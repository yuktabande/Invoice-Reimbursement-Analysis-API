import google.generativeai as genai
from dotenv import load_dotenv
import os
import time

def test_gemini_api():
    # Load environment variables
    load_dotenv()
    
    # Debug: Print current working directory
    print(f"Current directory: {os.getcwd()}")
    
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in .env file")
        return
    
    print("🔑 API key loaded")
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Test the API with retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"📝 Testing API (attempt {attempt + 1}/{max_retries})...")
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content("Say 'API is working!'")
                
                print("✅ API test successful!")
                print(f"Response: {response.text}")
                return
                
            except Exception as retry_error:
                if "API_KEY_INVALID" in str(retry_error):
                    print("❌ API key is invalid or expired")
                    print("Please generate a new key at: https://makersuite.google.com/app/apikey")
                    return
                    
                if attempt < max_retries - 1:
                    print(f"⚠️ Attempt failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise
                    
    except Exception as e:
        print("❌ API test failed!")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_gemini_api()