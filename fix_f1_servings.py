
import json

DB_PATH = "/home/user1/foodflow-bot/herbalife_db.json"

def fix_f1_structure():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        count = 0
        for p in data["products"]:
            # Target F1 shakes explicitly
            if p["id"].startswith("f1_") and "bar" not in p["id"]:
                
                std = p.get("standard_serving", {})
                
                # If current structure is amount=26, unit=grams
                if std.get("amount") == 26 and std.get("unit") == "граммы":
                    print(f"🔧 Restructuring {p['id']}...")
                    p["standard_serving"] = {
                        "amount": 3,
                        "unit": "мерные ложки",
                        "grams": 26,
                        "description": "3 мерные ложки (26г)"
                    }
                    count += 1
                    
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        print(f"✅ Fixed structure for {count} products")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_f1_structure()
