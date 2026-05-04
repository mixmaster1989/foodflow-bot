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
        "messages": [{"role": "user", "content": "Tell me a short joke."}],
        "stream": True
    }
    
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
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            if delta:
                                print(f"Delta keys: {delta.keys()}")
                                if 'content' in delta and delta['content']:
                                    print(f"Content: {delta['content']}")
                                if 'audio' in delta:
                                    print(f"Audio keys: {delta['audio'].keys()}")
                                    if 'transcript' in delta['audio']:
                                        print(f"Transcript: {delta['audio']['transcript']}")
                        except:
                            continue
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())
