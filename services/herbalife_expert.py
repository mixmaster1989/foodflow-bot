import json
import os
import re
from typing import Optional, Dict, List, Any

class HerbalifeExpertService:
    _instance = None
    _db: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HerbalifeExpertService, cls).__new__(cls)
            cls._instance._load_db()
        return cls._instance

    def _load_db(self):
        db_path = "/home/user1/foodflow-bot/herbalife_db.json"
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                self._db = json.load(f)
        else:
            self._db = {"products": []}

    async def find_product_by_alias(self, text: str) -> Optional[Dict]:
        """Use AI Brain to find the most likely product from the database."""
        from services.ai_brain import AIBrainService
        
        products = self._db.get("products", [])
        matched_id = await AIBrainService.resolve_herbalife_product(text, products)
        
        if matched_id:
            for p in products:
                if p["id"] == matched_id:
                    return p
        return None

    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """Direct lookup by ID."""
        for p in self._db.get("products", []):
            if p["id"] == product_id:
                return p
        return None

    def parse_quantity(self, text: str) -> Dict[str, Any]:
        """
        Extract amount and unit from text.
        Example: "3 ложки" -> {'amount': 3.0, 'unit': 'ложка'}
        """
        text = text.lower().replace(',', '.')
        # Pattern for number + unit
        match = re.search(r"(\d+(?:\.\d+)?)\s*(ложки?|ложк|g|г|ml|мл|шт|таблетки?|таблетк|капсул|колпач|колпак)", text)
        
        if match:
            return {
                "amount": float(match.group(1)),
                "unit": match.group(2)
            }
        
        # Fallback for "пол-ложки", "полложки" (half scoop)
        if "пол-ложк" in text or "полложк" in text:
            return {"amount": 0.5, "unit": "ложка"}
            
        return {"amount": 1.0, "unit": "serving"} # Default to 1 serving if amount missing

    def calculate_nutrition(self, product: Dict, amount: float, unit: str) -> Dict[str, Any]:
        """Calculate total nutrition based on product data and input quantity."""
        
        std_serving = product.get("standard_serving", {})
        measurement_unit = product.get("measurement_unit", "граммы")
        
        # 1. Determine Grams based on unit type
        total_grams = 0.0
        
        # Calculate single unit weight from DB (e.g. 1 scoop weight)
        std_amount = std_serving.get("amount", 1)
        std_grams = std_serving.get("grams", 0)
        
        # Default unit weight (if grams known)
        unit_weight = 0.0
        if std_grams and std_amount:
            unit_weight = std_grams / std_amount
        
        # Fallbacks for specific known types if DB is missing data
        if not unit_weight:
             if "ложка" in std_serving.get("unit", ""): unit_weight = 13.0 # F1 approx
             elif product["id"] == "h24_rebuild": unit_weight = 25.0
             else: unit_weight = 1.0 # Safe default
        
        if "ложк" in unit or "черпак" in unit:
            # Scoops/spoons
            total_grams = amount * unit_weight
            
        elif unit in ["g", "г"]:
            total_grams = amount
            
        elif unit in ["ml", "мл"]:
            total_grams = amount  # 1ml ≈ 1g for most liquids
            
        elif "колпач" in unit or "колпак" in unit:
            # Caps for Aloe (1 cap = ~5ml)
            total_grams = amount * 5.0
            
        elif "шт" in unit or "таблет" in unit or "капсул" in unit or "витамин" in unit:
            # Tablets/Capsules - use per-piece weight or nutrition_per_serving
            per_serving = product.get("nutrition_per_serving", {})
            if per_serving:
                # Return serving nutrition directly (tablets don't need gram calculation)
                serving_multiplier = amount / std_serving.get("amount", 1)
                return {
                    "name": product["name"],
                    "weight": amount,  # pieces, not grams
                    "calories": (per_serving.get("energy_kcal") or 0) * serving_multiplier,
                    "protein": (per_serving.get("protein_g") or 0) * serving_multiplier,
                    "fat": (per_serving.get("fat_g") or 0) * serving_multiplier,
                    "carbs": (per_serving.get("carbs_g") or 0) * serving_multiplier,
                    "fiber": (per_serving.get("fiber_g") or 0) * serving_multiplier,
                    "warnings": product.get("warnings", [])
                }
            # Fallback: estimate ~0.5g per tablet
            total_grams = amount * 0.5
            
        elif unit == "serving":
            # Default serving - use standard_serving.grams if available
            if std_serving.get("grams"):
                total_grams = amount * std_serving["grams"]
            elif std_serving.get("unit") == "граммы":
                total_grams = amount * std_serving.get("amount", 26.0)
            elif measurement_unit == "таблетки":
                # Tablets: use nutrition_per_serving directly
                per_serving = product.get("nutrition_per_serving", {})
                if per_serving:
                    return {
                        "name": product["name"],
                        "weight": amount,
                        "calories": (per_serving.get("energy_kcal") or 0) * amount,
                        "protein": (per_serving.get("protein_g") or 0) * amount,
                        "fat": (per_serving.get("fat_g") or 0) * amount,
                        "carbs": (per_serving.get("carbs_g") or 0) * amount,
                        "fiber": (per_serving.get("fiber_g") or 0) * amount,
                        "warnings": product.get("warnings", [])
                    }
                total_grams = amount * 0.5  # Fallback
            else:
                # Default scoop weight
                total_grams = amount * unit_weight
        else:
            # Unknown unit - use scoop weight as fallback
            total_grams = amount * unit_weight

        # 2. Calculate nutrition from per_100g
        nutr_100 = product.get("nutrition_per_100g", {})
        if "nutrition_per_100ml" in product:
            nutr_100 = product["nutrition_per_100ml"]
              
        ratio = total_grams / 100.0
        
        return {
            "name": product["name"],
            "weight": total_grams,
            "calories": (nutr_100.get("energy_kcal") or 0) * ratio,
            "protein": (nutr_100.get("protein_g") or 0) * ratio,
            "fat": (nutr_100.get("fat_g") or 0) * ratio,
            "carbs": (nutr_100.get("carbs_g") or 0) * ratio,
            "fiber": (nutr_100.get("fiber_g") or 0) * ratio,
            "warnings": product.get("warnings", [])
        }

    def get_expert_prompt_context(self) -> str:
        """Context to inject into Gemini when Herbalife mode is active."""
        return (
            "Ты — эксперт по продукции Herbalife. Используй следующие правила:\n"
            "- Ф1 = Протеиновый коктейль Формула 1. 1 мерная ложка = 6г. Стандартная порция = 2-3 ложки.\n"
            "- Ф3 / Белок = Протеиновая смесь Формула 3 (5г белка в 6г смеси).\n"
            "- ОЯН = Овсяно-яблочный напиток (5г клетчатки в 7.1г порции).\n"
            "- Алоэ = 1 колпачок ≈ 5мл. Пить ТОЛЬКО в разбавленном виде.\n"
            "- ВС = Восстановление Силы H24. 1 мерная ложка = 25г.\n"
            "При расчете всегда старайся выделить количество мерных ложек."
        )

# Global Instance
herbalife_expert = HerbalifeExpertService()
