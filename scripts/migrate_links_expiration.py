import asqlite
import asyncio
from config import settings

async def apply_migrations():
    print("Starting links migrations...")
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    
    async with asqlite.connect(db_path) as conn:
        # Add referral_token_expires_at to users
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN referral_token_expires_at DATETIME;")
            print("✅ Added referral_token_expires_at to users")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠️ referral_token_expires_at already exists")
            else:
                print(f"❌ Error adding referral_token_expires_at: {e}")

        # Add invite_token to marathons
        try:
            await conn.execute("ALTER TABLE marathons ADD COLUMN invite_token VARCHAR UNIQUE;")
            print("✅ Added invite_token to marathons")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠️ invite_token already exists")
            else:
                print(f"❌ Error adding invite_token: {e}")

        # Add invite_token_expires_at to marathons
        try:
            await conn.execute("ALTER TABLE marathons ADD COLUMN invite_token_expires_at DATETIME;")
            print("✅ Added invite_token_expires_at to marathons")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠️ invite_token_expires_at already exists")
            else:
                print(f"❌ Error adding invite_token_expires_at: {e}")

        await conn.commit()
    print("Migrations finished.")

if __name__ == "__main__":
    asyncio.run(apply_migrations())
