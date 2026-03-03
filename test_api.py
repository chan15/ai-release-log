import os

import google.genai as genai
from dotenv import load_dotenv

load_dotenv(override=True)


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    print(f"Testing API key: {api_key[:10]}...")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents="Say 'API is working!'",
    )
    print(f"Success! Response: {response.text}")


if __name__ == "__main__":
    main()
