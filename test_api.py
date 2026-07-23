import httpx
import asyncio
import json

async def test_chat():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/api/v1/chat",
                json={"query": "test query"},
                timeout=30.0
            )
            print(f"Chat Sync Status: {resp.status_code}")
            print(f"Chat Sync Body: {resp.text}")
            
            # Test stream endpoint
            async with client.stream("POST", "http://localhost:8000/api/v1/chat/stream", json={"query": "test query"}) as stream_resp:
                print(f"Chat Stream Status: {stream_resp.status_code}")
                async for chunk in stream_resp.aiter_text():
                    print(chunk, end="")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())
