
import sqlite3
from datetime import datetime, timedelta

def analyze_yesterday():
    db_path = "foodflow.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Analysis for: {yesterday}")

    # 1. New Users
    cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = ?", (yesterday,))
    new_users_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT id, username, first_name, created_at FROM users WHERE date(created_at) = ?", (yesterday,))
    new_users_details = cursor.fetchall()

    # 2. Active Users (Last Activity yesterday)
    cursor.execute("SELECT COUNT(DISTINCT id) FROM users WHERE date(last_activity) = ?", (yesterday,))
    active_users_count = cursor.fetchone()[0]

    # 3. Meals Logged
    cursor.execute("SELECT COUNT(*) FROM consumption_logs WHERE date(date) = ?", (yesterday,))
    meals_count = cursor.fetchone()[0]

    # 4. New Subscriptions
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE date(starts_at) = ?", (yesterday,))
    new_subs_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT user_id, tier, payment_source FROM subscriptions WHERE date(starts_at) = ?", (yesterday,))
    new_subs_details = cursor.fetchall()

    # 5. Feature Usage (UserActivity)
    cursor.execute("SELECT feature_name, COUNT(*) FROM user_activity WHERE date(last_used_at) = ? GROUP BY feature_name", (yesterday,))
    feature_usage = cursor.fetchall()

    # 6. Errors or issues (checking guide_history for "error" or similar, or just counting logs if we had a logs table)
    # Since we don't have a logs table in DB, we rely on the file logs, but let's check guide_history for issues.
    cursor.execute("SELECT COUNT(*) FROM guide_history WHERE date(created_at) = ? AND content LIKE '%ошибка%' OR content LIKE '%error%'", (yesterday,))
    ai_errors = cursor.fetchone()[0]

    # 7. Referral Events
    cursor.execute("SELECT event_type, COUNT(*) FROM referral_events WHERE date(created_at) = ? GROUP BY event_type", (yesterday,))
    ref_events = cursor.fetchall()

    # 8. Feedback
    cursor.execute("SELECT feedback_type, answer FROM user_feedback WHERE date(created_at) = ?", (yesterday,))
    feedbacks = cursor.fetchall()

    print(f"\n--- Summary ---")
    print(f"New Users: {new_users_count}")
    for u in new_users_details:
        print(f"  - {u[0]} (@{u[1] if u[1] else 'N/A'}, {u[2]}): {u[3]}")
    
    print(f"Active Users: {active_users_count}")
    print(f"Meals Logged: {meals_count}")
    print(f"New Subscriptions: {new_subs_count}")
    for s in new_subs_details:
        print(f"  - User {s[0]}: {s[1]} (via {s[2]})")
    
    print(f"\nFeature Usage:")
    for f in feature_usage:
        print(f"  - {f[0]}: {f[1]}")
    
    print(f"\nReferral Events:")
    for r in ref_events:
        print(f"  - {r[0]}: {r[1]}")

    print(f"\nAI Potential Issues (mentions of 'error' in guide): {ai_errors}")

    if feedbacks:
        print(f"\nUser Feedback:")
        for f in feedbacks:
            print(f"  - {f[0]}: {f[1]}")

    conn.close()

if __name__ == "__main__":
    analyze_yesterday()
