import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from services.normalization import NormalizationService
from dotenv import load_dotenv

load_dotenv()

async def test_weight_detection():
    items = ["яблоко", "банан 200г", "шаурма", "1 конфета"]
    for item in items:
        print(f"\nTesting: '{item}'")
        result = await NormalizationService.analyze_food_intake(item)
        print(f"Result: weight_grams={result.get('weight_grams')}, weight_missing={result.get('weight_missing')}")

if __name__ == "__main__":
    asyncio.run(test_weight_detection())
