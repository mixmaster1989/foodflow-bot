import os
import random
import sqlite3

DB_PATH = "/home/user1/foodflow-bot_new/foodflow.db"

def get_random_meal_for_demo():
    """
    Fetches a random parsed food log from the database that has valid macros
    and preferably a photo.
    Returns: dict with food_name, calories, protein, fat, carbs, and photo_path.
    """
    if not os.path.exists(DB_PATH):
        return _fallback_meal()

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query the actual consumption_logs table
        cursor.execute('''
            SELECT product_name, calories, protein, fat, carbs 
            FROM consumption_logs 
            WHERE calories > 0 AND product_name IS NOT NULL
            ORDER BY RANDOM() LIMIT 20
        ''')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return _fallback_meal()

        for row in rows:
            return {
                'food_name': row['product_name'].capitalize(),
                'calories': int(row['calories'] or 0),
                'protein': round(row['protein'] or 0.0, 1),
                'fat': round(row['fat'] or 0.0, 1),
                'carbs': round(row['carbs'] or 0.0, 1),
                'file_id': None
            }

        return _fallback_meal()
    except Exception as e:
        print(f"DB Error: {e}")
        return _fallback_meal()

def _fallback_meal():
    meals = [
        {'food_name': 'Сырники со сметаной', 'calories': 380, 'protein': 28, 'fat': 18, 'carbs': 25},
        {'food_name': 'Цезарь с курицей', 'calories': 420, 'protein': 35, 'fat': 22, 'carbs': 15},
        {'food_name': 'Гречка с котлетой', 'calories': 450, 'protein': 25, 'fat': 16, 'carbs': 48},
        {'food_name': 'Капучино и круассан', 'calories': 350, 'protein': 8, 'fat': 18, 'carbs': 38}
    ]
    return random.choice(meals)
