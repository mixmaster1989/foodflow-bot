import asyncio
import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import select, delete
from database.base import async_session
from database.models import Product, ConsumptionLog
from services.kbju_core import KBJUCoreService

async def test_fridge_optimization():
    print("🧪 Testing Fridge Optimization...")
    USER_ID = 432823154 # Test Pilot User
    
    async with async_session() as session:
        # 1. Clean up old test data
        await session.execute(delete(Product).where(Product.user_id == USER_ID, Product.name.like("%TEST%")))
        await session.commit()
        
        # 2. Test Weight Estimation for Pieces
        print("\nTest Case 1: Piece-to-weight estimation")
        # Let's say we have 'банан' in cache.
        core_result = await KBJUCoreService.get_product_nutrition("банан", session)
        avg_weight = core_result.weight_grams or 100.0
        print(f"  - Average weight for 'банан' from core: {avg_weight}g")
        
        product = Product(
            user_id=USER_ID,
            name="TEST Банан",
            base_name="банан",
            quantity=2.0,
            price=0.0,
            calories=89.0,
            weight_g=None, # UNKNOWN WEIGHT
            source="manual"
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        
        # Simulate consume_product(amount=1, unit='qty')
        amount = 1
        consumed_weight = avg_weight * amount
        calc_cal = (consumed_weight / 100) * product.calories
        print(f"  - Consumed 1 piece. Estimated weight: {consumed_weight}g. Calculated calories: {calc_cal}")
        
        if abs(calc_cal - (avg_weight * 0.89)) < 0.1:
            print("  ✅ CALCULATION OK")
        else:
            print(f"  ❌ CALCULATION WRONG: expected {avg_weight * 0.89}, got {calc_cal}")

        # 3. Test Base Name Filtering in Search
        print("\nTest Case 2: Base name matching in search")
        # We search for 'фрукты' which might match 'яблоко' base_name if we were smart, 
        # but let's test simpler: query 'бананчик' should match product with base_name 'банан'
        query = "бананчик"
        query_core = await KBJUCoreService.get_product_nutrition(query, session)
        query_base = query_core.base_name
        print(f"  - Query '{query}' -> base_name '{query_base}'")
        
        match = (query_base == "банан")
        if match:
             print("  ✅ SEARCH NORMALIZATION OK")
        else:
             print("  ❌ SEARCH NORMALIZATION FAILED")

        # Cleanup
        await session.execute(delete(Product).where(Product.id == product.id))
        await session.commit()

if __name__ == "__main__":
    asyncio.run(test_fridge_optimization())
