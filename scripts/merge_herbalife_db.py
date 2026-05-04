#!/usr/bin/env python3
"""
Smart Herbalife Database Merger
Объединяет herbalife_db.json и herbalife_db_v2.json в одну базу.
Приоритет: v2 > v1 (если ID совпадают, берём данные из v2)
"""

import json
import sys
from pathlib import Path

DB_DIR = Path("/home/user1/foodflow-bot")
DB_V1 = DB_DIR / "herbalife_db.json"
DB_V2 = DB_DIR / "herbalife_db_v2.json"
DB_OUTPUT = DB_DIR / "herbalife_db.json"


def load_json(path: Path) -> dict:
    """Load JSON safely with error handling."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON Error in {path.name}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"⚠️ File not found: {path.name}, skipping...")
        return {"products": []}


def merge_databases():
    print("🔄 Loading databases...")

    db_v1 = load_json(DB_V1)
    db_v2 = load_json(DB_V2)

    products_v1 = {p["id"]: p for p in db_v1.get("products", [])}
    products_v2 = {p["id"]: p for p in db_v2.get("products", [])}

    print(f"   📦 v1: {len(products_v1)} products")
    print(f"   📦 v2: {len(products_v2)} products")

    # Merge: v2 overwrites v1
    merged = {**products_v1, **products_v2}

    # Find what was added/updated
    new_ids = set(products_v2.keys()) - set(products_v1.keys())
    updated_ids = set(products_v2.keys()) & set(products_v1.keys())
    only_v1 = set(products_v1.keys()) - set(products_v2.keys())

    print("\n📊 Merge Stats:")
    print(f"   ➕ New from v2: {len(new_ids)}")
    print(f"   🔄 Updated (v2 priority): {len(updated_ids)}")
    print(f"   📁 Only in v1: {len(only_v1)}")
    print(f"   ✅ Total: {len(merged)}")

    # Build result
    result = {
        "database_version": "3.0-merged",
        "last_updated": "2026-01-23",
        "data_sources": db_v2.get("data_sources", db_v1.get("data_sources", "")),
        "note": "Объединённая база из v1 и v2. Приоритет: v2.",
        "products": sorted(merged.values(), key=lambda x: (x.get("category", ""), x.get("id", ""))),
    }

    # Copy other metadata from v2
    for key in ["category_definitions", "warnings_and_notes"]:
        if key in db_v2:
            result[key] = db_v2[key]
        elif key in db_v1:
            result[key] = db_v1[key]

    # Validate
    print("\n🔍 Validating...")
    try:
        json.dumps(result, ensure_ascii=False)
        print("   ✅ JSON is valid!")
    except Exception as e:
        print(f"   ❌ Validation failed: {e}")
        sys.exit(1)

    # Save
    with open(DB_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Saved to: {DB_OUTPUT}")
    print(f"   Total products: {len(result['products'])}")


if __name__ == "__main__":
    merge_databases()
