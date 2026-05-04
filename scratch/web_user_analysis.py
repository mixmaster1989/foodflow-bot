
import sqlite3
from datetime import datetime, timedelta

def analyze_web_users():
    db_path = "foodflow.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Web User Analysis for: {yesterday}")

    # Users with email
    cursor.execute("SELECT id, email, is_web_only, created_at FROM users WHERE email IS NOT NULL AND date(created_at) = ?", (yesterday,))
    web_users = cursor.fetchall()

    print(f"New Web Users: {len(web_users)}")
    for u in web_users:
        print(f"  - ID: {u[0]} | Email: {u[1]} | WebOnly: {u[2]} | Created: {u[3]}")

    conn.close()

if __name__ == "__main__":
    analyze_web_users()
