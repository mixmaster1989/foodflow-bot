import asyncio
import aiohttp
import sys
import os
os.chdir('FoodFlow')
sys.path.insert(0, '.')
from config import settings

async def test_perplexity_prices():
    headers = {
        'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://foodflow.app',
        'X-Title': 'FoodFlow Bot'
    }
    
    payload = {
        'model': 'perplexity/sonar',
        'messages': [{
            'role': 'user',
            'content': 'Сколько стоит сахар 1кг сегодня в магазинах Пятёрочка, Магнит, Лента в России? Дай актуальные цены на ноябрь 2025.'
        }]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60
        ) as resp:
            result = await resp.json()
            print("=" * 80)
            print("FULL RESPONSE:")
            print(result)
            print("=" * 80)
            if 'choices' in result:
                print("PERPLEXITY RESPONSE:")
                print("=" * 80)
                print(result['choices'][0]['message']['content'])
                print("=" * 80)
            else:
                print("ERROR: No 'choices' in response")
                if 'error' in result:
                    print(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(test_perplexity_prices())
