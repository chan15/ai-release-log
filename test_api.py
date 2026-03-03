import os
import google.genai as genai
from dotenv import load_dotenv

load_dotenv(override=True)

def test_api():
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"Testing API Key: {api_key[:10]}...")
    
    try:
        client = genai.Client(api_key=api_key)
        # Use a simple generation to test
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents="Say 'API is working!'"
        )
        print(f"Success! Response: {response.text}")
    except Exception as e:
        print(f"Failed! Error: {e}")

if __name__ == "__main__":
    test_api()
