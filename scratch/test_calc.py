
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append('/home/user1/foodflow-bot_new')

from services.herbalife_expert import herbalife_expert

async def test():
    tests = ["1 порция Грин Макс", "2 ложки Грин Макс", "1 ложка Грин Макс"]
    for text in tests:
        print(f"\nTesting: {text}")
        product = await herbalife_expert.find_product_by_alias(text)
        if product:
            quantity = herbalife_expert.parse_quantity(text)
            print(f"Parsed Quantity: {quantity}")
            nutrition = herbalife_expert.calculate_nutrition(product, quantity['amount'], quantity['unit'])
            print(f"Result -> Weight: {nutrition['weight']}g, Calories: {nutrition['calories']} kcal")
        else:
            print("Product not found")

if __name__ == "__main__":
    asyncio.run(test())
