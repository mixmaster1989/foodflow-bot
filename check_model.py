import aiohttp
import asyncio
import sys
import os

# Add project root to path to import config
sys.path.insert(0, os.getcwd())
try:
    from FoodFlow.config import settings
except ImportError:
    # Fallback if running from root
    sys.path.insert(0, os.path.join(os.getcwd(), 'FoodFlow'))
    from config import settings

async def check_model():
    model_id = "openai/gpt-oss-20b:free"
    print(f"Checking availability for: {model_id}...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Method 1: Check model info directly (if endpoint exists/supported) or list models
            async with session.get(
                'https://openrouter.ai/api/v1/models',
                headers={'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}'}
            ) as response:
                if response.status != 200:
                    print(f"Error fetching models: {response.status}")
                    text = await response.text()
                    print(text)
                    return

                data = await response.json()
                models = data.get('data', [])
                
                found = False
                print("Searching for DeepSeek models...")
                for model in models:
                    if "deepseek" in model['id'].lower():
                        print(f"Found DeepSeek variant: {model['id']}")
                    
                    if model['id'] == model_id:
                        found = True
                        print(f"✅ EXACT MATCH found!")
                        print(f"ID: {model['id']}")
                        print(f"Name: {model.get('name')}")
                        print(f"Pricing: {model.get('pricing')}")
                        
                
                if not found:
                    print(f"❌ Model {model_id} NOT found in OpenRouter model list.")

            # Method 2: Try a small completion
            print("\nAttempting test generation...")
            async with session.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/mixmaster1989/foodflow-bot',
                },
                json={
                    'model': model_id,
                    'messages': [{'role': 'user', 'content': 'Hi'}],
                    'max_tokens': 5
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Test generation successful!")
                    print(f"Response: {data['choices'][0]['message']['content']}")
                else:
                    print(f"❌ Test generation failed: {response.status}")
                    text = await response.text()
                    print(text)
            
            # Method 3: Try a known working model (Gemini) to verify API key for generation
            print("\nVerifying API key with Gemini...")
            async with session.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/mixmaster1989/foodflow-bot',
                },
                json={
                    'model': 'google/gemini-2.0-flash-exp:free',
                    'messages': [{'role': 'user', 'content': 'Hi'}],
                    'max_tokens': 5
                }
            ) as response:
                if response.status == 200:
                    print("✅ Gemini generation successful (API Key is OK)")
                else:
                    print(f"❌ Gemini generation failed: {response.status}")
                    text = await response.text()
                    print(text)

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_model())
