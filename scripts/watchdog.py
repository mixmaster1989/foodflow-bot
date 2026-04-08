import asyncio
import os
import sys
import psutil
import subprocess
import json
import logging
from datetime import datetime
from aiogram import Bot

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("watchdog")

# Пороги срабатывания
DISK_THRESHOLD_GB = 1.0  # Алерт если < 1 ГБ
RAM_THRESHOLD_PERCENT = 90.0
PM2_RESTART_THRESHOLD = 5 # Алерт если > 5 перезапусков с момента последнего чека

# Состояние для отслеживания изменений
state = {
    "last_pm2_restarts": {},
    "last_disk_alert": 0,
    "last_ram_alert": 0
}

async def get_pm2_status():
    """Get status of PM2 processes via CLI JSON output."""
    try:
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Failed to get PM2 status: {e}")
        return []

async def check_resources(bot: Bot, admin_id: int):
    # 1. Disk Space
    disk = psutil.disk_usage('/')
    free_gb = disk.free / (1024**3)
    if free_gb < DISK_THRESHOLD_GB:
        msg = f"🚨 **КРИТИЧЕСКИЙ УРОВЕНЬ ДИСКА!**\nСвободно: `{free_gb:.2f} ГБ`\nПожалуйста, очистите место!"
        await bot.send_message(admin_id, msg, parse_mode="Markdown")
        logger.warning(f"Disk alert: {free_gb:.2f} GB free")

    # 2. RAM Usage
    ram = psutil.virtual_memory()
    if ram.percent > RAM_THRESHOLD_PERCENT:
        msg = f"⚠️ **ВЫСОКАЯ НАГРУЗКА ОЗУ!**\nЗанято: `{ram.percent}%`"
        await bot.send_message(admin_id, msg, parse_mode="Markdown")
        logger.warning(f"RAM alert: {ram.percent}%")

    # 3. PM2 Processes
    processes = await get_pm2_status()
    for proc in processes:
        name = proc['name']
        status = proc['pm2_env']['status']
        restarts = proc['pm2_env']['restart_time']
        
        # Check if status is not online
        if status not in ['online', 'one-launch-status'] and name != 'ssh-tunnel':
            msg = f"🔴 **ПРОЦЕСС УПАЛ!**\nИмя: `{name}`\nСтатус: `{status}`"
            await bot.send_message(admin_id, msg, parse_mode="Markdown")
            logger.error(f"Process {name} is {status}")

        # Check for rapid restarts
        prev_restarts = state['last_pm2_restarts'].get(name, restarts)
        if restarts - prev_restarts >= PM2_RESTART_THRESHOLD:
            msg = f"🔄 **ЧАСТЫЕ ПЕРЕЗАПУСКИ!**\nИмя: `{name}`\nВсего рестартов: `{restarts}`\nРост: `+{restarts - prev_restarts}`"
            await bot.send_message(admin_id, msg, parse_mode="Markdown")
            logger.warning(f"Process {name} restarting too fast: +{restarts - prev_restarts}")
        
        state['last_pm2_restarts'][name] = restarts

async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    admin_id = settings.ADMIN_IDS[0]
    
    logger.info("🛡️ FoodFlow Watchdog started...")
    
    # Send "I'm alive" notification (optional, during test)
    # await bot.send_message(admin_id, "🛡️ Мониторинг Watchdog запущен.")

    while True:
        try:
            await check_resources(bot, admin_id)
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        
        # Check every 5 minutes
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
