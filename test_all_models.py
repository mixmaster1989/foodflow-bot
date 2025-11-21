import aiohttp
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load env directly to be sure
load_dotenv('FoodFlow/.env')
API_KEY = os.getenv('OPENROUTER_API_KEY')

async def test_model(session, model):
    print(f"⏳ Testing {model}...")
    try:
        async with session.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/mixmaster1989/foodflow-bot',
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'max_tokens': 5
            },
            timeout=15
        ) as response:
            if response.status == 200:
                data = await response.json()
                content = data['choices'][0]['message']['content']
                print(f"✅ {model}: OK")
                print(f"   Response: {content}")
                return True
            else:
                text = await response.text()
                print(f"❌ {model}: Failed ({response.status}) - {text}")
                return False
    except Exception as e:
        print(f"❌ {model}: Error - {e}")
        return False

async def get_free_models(session):
    print("📋 Fetching list of available models...")
    try:
        async with session.get(
            'https://openrouter.ai/api/v1/models',
            headers={'Authorization': f'Bearer {API_KEY}'}
        ) as response:
            if response.status != 200:
                print(f"❌ Failed to fetch models: {response.status}")
                return []
            
            data = await response.json()
            all_models = data.get('data', [])
            
            # Filter for free models (id ends with :free)
            free_models = [m['id'] for m in all_models if m['id'].endswith(':free')]
            print(f"ℹ️ Found {len(free_models)} free models.")
            return free_models
    except Exception as e:
        print(f"❌ Error fetching models: {e}")
        return []

async def main():
    if not API_KEY:
        print("❌ Error: OPENROUTER_API_KEY not found in .env")
        return

    print(f"🔑 Key loaded: {API_KEY[:10]}... (Length: {len(API_KEY)})")
    
    async with aiohttp.ClientSession() as session:
        # 1. Get all free models dynamically
        models_to_test = await get_free_models(session)
        
        if not models_to_test:
            print("⚠️ No free models found to test. Using fallback list.")
            models_to_test = [
                "google/gemini-2.0-flash-exp:free",
                "google/gemma-3-27b-it:free",
                "mistralai/mistral-small-3.2-24b-instruct:free",
                "qwen/qwen2.5-vl-32b-instruct:free",
                "deepseek/deepseek-chat-v3-0324:free"
            ]

        # 2. Test them all (limit concurrency to avoid self-imposed rate limits if needed, but user said "let's fuck up openrouter", so...)
        # We'll use a semaphore just to be polite-ish and not crash our own network stack
        sem = asyncio.Semaphore(5) 
        
        async def safe_test(model):
            async with sem:
                return await test_model(session, model)

        tasks = [safe_test(model) for model in models_to_test]
        print(f"🚀 Starting tests for {len(models_to_test)} models...")
        results = await asyncio.gather(*tasks)
    
    print("\n--- Summary ---")
    working = [m for m, r in zip(models_to_test, results) if r]
    failed = [m for m, r in zip(models_to_test, results) if not r]
    
    print(f"✅ Working ({len(working)}):")
    for m in working:
        print(f"  - {m}")
        
    print(f"\n❌ Failed ({len(failed)}):")
    for m in failed:
        print(f"  - {m}")

if __name__ == "__main__":
    asyncio.run(main())
