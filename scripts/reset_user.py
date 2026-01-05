import sqlite3
import os

DB_PATH = '/home/user1/foodflow-bot/foodflow.db'
TARGET_USER = 'alitaneiropodruga'

if not os.path.exists(DB_PATH):
    print(f"❌ Database not found at {DB_PATH}")
    exit(1)

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get user ID first
    cursor.execute("SELECT id FROM users WHERE username = ?", (TARGET_USER,))
    result = cursor.fetchone()
    
    if result:
        user_id = result[0]
        print(f"Found user {TARGET_USER} with ID {user_id}")
        
        # Delete from settings
        cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        print(f"Deleted settings for {user_id}")
        
        # Delete from users
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        print(f"Deleted user {TARGET_USER}")
        
        conn.commit()
        print("✅ Database cleanup successful")
    else:
        print(f"⚠️ User {TARGET_USER} not found in DB. Already clean?")

    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
