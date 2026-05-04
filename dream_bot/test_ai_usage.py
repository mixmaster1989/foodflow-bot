import asyncio
import aiohttp
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def test_usage():
    url = "https://openrouter.ai/api/v1/chat/completions"
    api_key = os.getenv("OPENROUTER_API_KEY")
    proxy = os.getenv("GROK_PROXY")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-audio-mini",
        "messages": [{"role": "user", "content": "How many tokens is this?"}],
        "stream": True,
        # OpenRouter often requires this to include usage in stream
        "stream_options": {"include_usage": True} 
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, proxy=proxy) as resp:
                if resp.status != 200:
                    print(f"Error: {await resp.text()}")
                    return
                
                async for line in resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            if 'usage' in chunk:
                                print(f"\nUSAGE: {chunk['usage']}")
                        except:
                            continue
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_usage())
