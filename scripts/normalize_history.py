import asyncio
import logging
import sys
import os

# Add parent dir to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, update
from database.base import get_db, async_session
from database.models import ConsumptionLog
from services.normalization import NormalizationService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def normalize_history():
    logger.info("🚀 Starting history normalization...")
    
    async with async_session() as session:
        # 1. Fetch all logs without base_name
        stmt = select(ConsumptionLog).where(ConsumptionLog.base_name == None)
        result = await session.execute(stmt)
        logs = result.scalars().all()
        
        total_logs = len(logs)
        logger.info(f"Found {total_logs} logs to normalize.")
        
        if total_logs == 0:
            logger.info("Nothing to normalize.")
            return

        # 2. Group by product_name to save API calls
        unique_names = list(set([log.product_name for log in logs]))
        logger.info(f"Unique product names: {len(unique_names)}")
        
        name_map = {} # product_name -> base_name
        
        # 3. Analyze each unique name
        for i, name in enumerate(unique_names):
            logger.info(f"[{i+1}/{len(unique_names)}] Analyzing: {name}")
            try:
                # Use retry logic or just simple call
                # analyze_food_intake returns dict with 'base_name'
                # Note: analyze_food_intake relies on settings.OPENROUTER_API_KEY
                result = await NormalizationService.analyze_food_intake(name)
                base_name = result.get("base_name")
                
                if base_name:
                    name_map[name] = base_name
                    logger.info(f"   -> Essence: {base_name}")
                else:
                    logger.warning(f"   -> No base_name returned for {name}")
                    
                # Rate limit protection (simple sleep)
                await asyncio.sleep(0.5) 
                
            except Exception as e:
                logger.error(f"Error analyzing {name}: {e}")
        
        # 4. Update Database
        logger.info("Updating database...")
        update_count = 0
        
        for name, essence in name_map.items():
            if not essence:
                continue
                
            # Update all logs with this product_name
            # We filter by base_name == None to avoid overwriting if run again (double check)
            # Actually we just update all matches in this batch
            stmt = (
                update(ConsumptionLog)
                .where(ConsumptionLog.product_name == name)
                .where(ConsumptionLog.base_name == None)
                .values(base_name=essence)
            )
            res = await session.execute(stmt)
            update_count += res.rowcount
            
        await session.commit()
        logger.info(f"✅ Normalization complete! Updated {update_count} records.")

if __name__ == "__main__":
    asyncio.run(normalize_history())
