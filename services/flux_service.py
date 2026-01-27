import asyncio
import aiohttp
import os
import time
import logging
from typing import Optional, List
import urllib.parse
from PIL import Image
import io

logger = logging.getLogger("flux_service")

POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt"
ASSETS_DIR = "/home/user1/foodflow-bot/static/generated_assets"

# Fingerprint of the Pollinations "Rate Limit Reached" placeholder image
POLLINATIONS_LIMIT_FINGERPRINT = 1284566

# Semaphore to prevent rate limiting (stricter now)
generation_semaphore = asyncio.Semaphore(1)

class FluxService:
    def __init__(self):
        os.makedirs(ASSETS_DIR, exist_ok=True)
        os.makedirs(f"{ASSETS_DIR}/icons", exist_ok=True)
        os.makedirs(f"{ASSETS_DIR}/daily", exist_ok=True)
        self.cooldown_until = 0

    async def generate_product_icon(self, product_name: str) -> Optional[str]:
        """Generates a professional 512x512 icon for a product."""
        # Sanitize name for filename and prompt
        clean_name = "".join(x for x in product_name if x.isalnum() or x == " ").strip()
        safe_name = clean_name.replace(" ", "_").lower()[:50]
        filename = f"icon_{safe_name}.png"
        filepath = f"{ASSETS_DIR}/icons/{filename}"

        # Cache check
        if os.path.exists(filepath):
            return filepath

        prompt = f"Professional high-quality studio photo of {clean_name}, isolated on neutral dark background, 8k resolution, food photography"
        return await self._generate(prompt, filepath, width=512, height=512)

    async def generate_daily_collage(self, products: List[str]) -> Optional[str]:
        """Generates a daily collage of the current fridge content."""
        date_str = time.strftime("%Y-%m-%d")
        filepath = f"{ASSETS_DIR}/daily/fridge_{date_str}.png"

        if os.path.exists(filepath):
            return filepath

        products_str = ", ".join(products[:8])
        prompt = f"Abstract artistic composition of healthy food ingredients: {products_str}. Dynamic lighting, dark cinematic background, vibrant colors, wide angel photography, top down view"
        
        return await self._generate(prompt, filepath, width=1280, height=720)

    async def _generate(self, prompt: str, filepath: str, width: int, height: int) -> Optional[str]:
        if time.time() < self.cooldown_until:
            wait_left = int(self.cooldown_until - time.time())
            logger.warning(f"🕒 Flux service is on cooldown for {wait_left}s...")
            return None

        async with generation_semaphore:
            encoded_prompt = urllib.parse.quote(prompt)
            url = f"{POLLINATIONS_BASE_URL}/{encoded_prompt}"
            
            params = {
                "width": width,
                "height": height,
                "model": "flux",
                "enhance": "true",
                "nologo": "true",
                "seed": int(time.time())
            }

            max_retries = 3
            for attempt in range(max_retries):
                logger.info(f"Generating Flux image (Attempt {attempt+1}): {prompt[:50]}...")
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(url, params=params, timeout=60) as response:
                            if response.status == 200:
                                data = await response.read()
                                
                                # CHECK FINGERPRINT (Detect "Limit Reached" placeholder)
                                if len(data) == POLLINATIONS_LIMIT_FINGERPRINT:
                                    wait_time = (attempt + 1) * 60 # wait 1 min, then 2, then 3
                                    logger.warning(f"🚨 Rate limit placeholder detected! Cooling down for {wait_time}s...")
                                    self.cooldown_until = time.time() + wait_time
                                    await asyncio.sleep(10) # Short intra-retry sleep
                                    continue # Try next attempt after waiting

                                img = Image.open(io.BytesIO(data))
                                img = img.convert("RGB")
                                img.save(filepath, "PNG", optimize=True)
                                logger.info(f"✅ Generated and saved: {filepath}")
                                return filepath
                            
                            elif response.status == 429:
                                wait_time = (attempt + 1) * 30
                                logger.warning(f"⚠️ API 429. Waiting {wait_time}s...")
                                await asyncio.sleep(wait_time)
                            else:
                                logger.error(f"❌ Flux API Error {response.status}")
                                break 
                    except Exception as e:
                        logger.error(f"❌ Flux Generation Exception: {e}")
                        await asyncio.sleep(5)
            
            return None

flux_service = FluxService()
