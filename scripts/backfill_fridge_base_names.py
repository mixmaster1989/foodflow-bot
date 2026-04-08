import asyncio
import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import select
from database.base import async_session
from database.models import Product
from services.kbju_core import KBJUCoreService

async def populate_fridge_base_names():
    print("🚀 Populating base_names for fridge products...")
    
    async with async_session() as session:
        stmt = select(Product).where(Product.base_name == None)
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        if not products:
            print("✅ All products already have base_name.")
            return

        print(f"Found {len(products)} products without base_name.")
        
        for p in products:
            core_result = await KBJUCoreService.get_product_nutrition(p.name, session)
            p.base_name = core_result.base_name
            print(f"  - '{p.name}' -> base_name='{p.base_name}'")
        
        await session.commit()
        print(f"✅ Successfully updated {len(products)} products.")

if __name__ == "__main__":
    asyncio.run(populate_fridge_base_names())
