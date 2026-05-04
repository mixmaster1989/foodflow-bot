import asyncio
import aiohttp
import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()

async def test_openrouter():
    url = "https://openrouter.ai/api/v1/chat/completions"
    api_key = os.getenv("OPENROUTER_API_KEY")
    proxy = os.getenv("GROK_PROXY")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-audio-mini",
        "modalities": ["text", "audio"],
        "audio": {"voice": "shimmer", "format": "pcm16"},
        "messages": [{"role": "user", "content": "Hello, interpret a short dream about a cat."}],
        "stream": True
    }
    
    print(f"Testing with Proxy: {proxy}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, proxy=proxy) as resp:
                print(f"Status: {resp.status}")
                if resp.status != 200:
                    print(f"Error: {await resp.text()}")
                    return
                
                async for line in resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            print("\n[DONE]")
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            if 'content' in delta:
                                print(delta['content'], end="", flush=True)
                            if 'audio' in delta:
                                print(".", end="", flush=True)
                        except Exception as e:
                            # print(f"\nParse Error: {e} | data: {data_str}")
                            continue
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())
