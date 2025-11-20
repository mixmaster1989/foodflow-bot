import os
import asyncio
import aiohttp
from dotenv import load_dotenv

# Load env from FoodFlow/.env
load_dotenv("FoodFlow/.env")
api_key = os.getenv("OPENROUTER_API_KEY")

models_to_test = [
    "openai/gpt-4o-mini",
    "perplexity/sonar-reasoning",
    "perplexity/sonar",
]

async def test_model(model):
    print(f"\n--- Testing {model} ---")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app",
        "X-Title": "FoodFlow Test"
    }
    
    # Query checking for real-time info
    prompt = "Какой сегодня день (число и год)? Какая погода в Ростове прямо сейчас? Какой курс доллара к рублю? Отвечай кратко."
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['message']['content']
                        print(f"Response:\n{content}")
                    else:
                        print(f"No choices in response: {data}")
                else:
                    print(f"Error: {resp.status} - {await resp.text()}")
        except Exception as e:
            print(f"Exception: {e}")

async def main():
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in .env")
        return
    
    print("Starting Model Web Search Capability Test...")
    for m in models_to_test:
        await test_model(m)

if __name__ == "__main__":
    asyncio.run(main())
