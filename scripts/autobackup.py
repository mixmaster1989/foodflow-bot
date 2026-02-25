
import os
import sqlite3
import shutil
import tarfile
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from aiogram import Bot

# Direct settings import to avoid circular dependency issues or path problems
# We need BOT_TOKEN and ADMIN_IDS (or specific admin ID)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

# --- CONFIG ---
BACKUP_ROOT = "/home/user1/backups/foodflow"
PROJECT_ROOT = "/home/user1/foodflow-bot_new"
DB_PATH = os.path.join(PROJECT_ROOT, "foodflow.db")
RETENTION_COUNT = 14  # Keep last 14 backups (7 days x 2)
LOG_FILE = os.path.join(PROJECT_ROOT, "backup.log")

# Setup Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AUTOBACKUP")

async def send_notification(success: bool, message: str):
    """Send Telegram notification to Admin."""
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        # Notify Igor (Default Admin)
        if not settings.ADMIN_IDS:
            logger.error("No ADMIN_IDS in settings")
            return
            
        admin_id = settings.ADMIN_IDS[0]
        
        status_icon = "✅" if success else "❌"
        text = f"{status_icon} **Backup Status**\n\n{message}"
        
        await bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        await bot.session.close()
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

def db_hot_backup(backup_dir: Path) -> Path:
    """Perform hot backup of SQLite DB."""
    dst = backup_dir / "foodflow.db"
    
    try:
        # Connect to source and destination
        # 'file:...' is standard file path
        # We use sqlite3 API for atomic backup
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(str(dst))
        
        with dst_conn:
            src_conn.backup(dst_conn)
            
        dst_conn.close()
        src_conn.close()
        logger.info(f"DB Backup created at {dst}")
        return dst
    except Exception as e:
        logger.error(f"DB Backup Failed: {e}")
        raise

def code_backup(backup_dir: Path) -> Path:
    """Create tar.gz of codebase."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"code_{timestamp}.tar.gz"
    dst = backup_dir / archive_name
    
    try:
        with tarfile.open(dst, "w:gz") as tar:
            tar.add(PROJECT_ROOT, arcname=os.path.basename(PROJECT_ROOT), 
                    filter=lambda x: None if any(ignore in x.name for ignore in ['venv', '__pycache__', '.git', '.idea', 'node_modules']) else x)
        logger.info(f"Code Backup created at {dst}")
        return dst
    except Exception as e:
        logger.error(f"Code Backup Failed: {e}")
        raise

def rotate_backups():
    """Delete old backups."""
    try:
        backup_path = Path(BACKUP_ROOT)
        # List subdirectories (each is a backup timestamp)
        backups = sorted([x for x in backup_path.iterdir() if x.is_dir()])
        
        while len(backups) > RETENTION_COUNT:
            oldest = backups.pop(0)
            shutil.rmtree(oldest)
            logger.info(f"Rotated/Deleted old backup: {oldest}")
            
    except Exception as e:
        logger.error(f"Rotation Failed: {e}")

async def main():
    start_time = datetime.now()
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(BACKUP_ROOT) / timestamp
    
    logger.info("--- Starting Backup ---")
    
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. DB Backup
        db_file = db_hot_backup(backup_dir)
        db_size_mb = db_file.stat().st_size / (1024 * 1024)
        
        # 2. Code Backup
        code_file = code_backup(backup_dir)
        code_size_mb = code_file.stat().st_size / (1024 * 1024)
        
        # 3. Rotation
        rotate_backups()
        
        # 4. Success Notify
        duration = (datetime.now() - start_time).total_seconds()
        
        msg = (
            f"📦 **Backup Created Successfully**\n"
            f"📂 Dir: `{timestamp}`\n"
            f"🗄️ DB: `{db_size_mb:.2f} MB`\n"
            f"💻 Code: `{code_size_mb:.2f} MB`\n"
            f"⏱️ Time: `{duration:.1f}s`"
        )
        logger.info("Backup Completed Successfully")
        await send_notification(True, msg)
        
    except Exception as e:
        logger.error(f"Backup Process Failed: {e}", exc_info=True)
        await send_notification(False, f"Critical Failure: {e}")

if __name__ == "__main__":
    asyncio.run(main())
