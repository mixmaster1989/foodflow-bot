import sqlite3
from datetime import datetime

db_path = '/home/user1/foodflow-bot_new/foodflow.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

yesterday = '2026-04-29'

print(f"Stats for {yesterday}:")

# New users
cursor.execute("SELECT count(*) FROM users WHERE date(created_at) = ?", (yesterday,))
new_users = cursor.fetchone()[0]
print(f"New users: {new_users}")

# Food logs
# Let's check table names first to be sure
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]

if 'consumption_logs' in tables:
    cursor.execute("SELECT count(*) FROM consumption_logs WHERE date(date) = ?", (yesterday,))
    food_logs = cursor.fetchone()[0]
    print(f"Food logs (consumption_logs): {food_logs}")

if 'user_feedback' in tables:
    cursor.execute("SELECT count(*) FROM user_feedback WHERE date(created_at) = ?", (yesterday,))
    feedback = cursor.fetchone()[0]
    print(f"User feedback: {feedback}")

# Activity by hour to see if there were gaps
if 'consumption_logs' in tables:
    print("\nActivity by hour (MSK):")
    cursor.execute("SELECT strftime('%H', date) as hr, count(*) FROM consumption_logs WHERE date(date) = ? GROUP BY hr", (yesterday,))
    for row in cursor.fetchall():
        print(f"{row[0]}:00 - {row[1]} logs")

conn.close()
