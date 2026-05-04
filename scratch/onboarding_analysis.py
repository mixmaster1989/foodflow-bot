
import sqlite3
from datetime import datetime, timedelta

def analyze_onboarding():
    db_path = "foodflow.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # New users from yesterday
    cursor.execute("SELECT id, username, first_name FROM users WHERE date(created_at) = ?", (yesterday,))
    new_users = cursor.fetchall()

    print(f"Onboarding analysis for users from {yesterday}:")
    for user_id, username, first_name in new_users:
        cursor.execute("SELECT is_initialized, calorie_goal, weight FROM user_settings WHERE user_id = ?", (user_id,))
        settings = cursor.fetchone()
        
        if settings:
            is_init, c_goal, weight = settings
            print(f"User: {first_name} (@{username}) | ID: {user_id}")
            print(f"  - Initialized: {is_init}")
            print(f"  - Calorie Goal: {c_goal}")
            print(f"  - Current Weight: {weight}")
        else:
            print(f"User: {first_name} (@{username}) | ID: {user_id} - NO SETTINGS FOUND")
        
        # Check if they logged anything
        cursor.execute("SELECT COUNT(*) FROM consumption_logs WHERE user_id = ?", (user_id,))
        meals = cursor.fetchone()[0]
        print(f"  - Meals Logged: {meals}")
        print("-" * 20)

    conn.close()

if __name__ == "__main__":
    analyze_onboarding()
