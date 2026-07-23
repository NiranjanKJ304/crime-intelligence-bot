import asyncio
from groq import AsyncGroq
import os

async def main():
    try:
        api_key = os.getenv("GROQ_API_KEY", "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")
        print(f"API Key: {api_key[:10]}...")
        client = AsyncGroq(api_key=api_key)
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role": "user", "content": "hi"}]
        )
        print("Success!")
        print(resp.choices[0].message.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
