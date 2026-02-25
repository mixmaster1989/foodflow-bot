"""Service for calculating nutrition goals (Calories, Macros)."""

from typing import Dict, Any

class NutritionCalculator:
    """Calculates BMR, TDEE, and Macro splits based on user profile."""

    @staticmethod
    def calculate_targets(
        gender: str,
        weight: float,
        height: int,
        age: int,
        goal: str
    ) -> Dict[str, Any]:
        """Calculate daily calorie and macro targets.
        
        Formula: Mifflin-St Jeor
        BMR (Men) = 10*W + 6.25*H - 5*A + 5
        BMR (Women) = 10*W + 6.25*H - 5*A - 161
        """
        # 1. BMR Calculation
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
            
        # 2. TDEE (Activity Level)
        # Defaulting to Moderate (1.55) as a safe baseline for active people/bots
        # TODO: Add activity level selection in future
        tdee = bmr * 1.55
        
        # 3. Goal Adjustment
        if goal == "lose_weight":
            calories = int(tdee * 0.80)  # 20% deficit (Standard)
        elif goal == "gain_mass":
            calories = int(tdee * 1.15)  # 15% surplus (Lean bulk)
        else:
            calories = int(tdee)         # Maintenance
            
        # 4. Macro Calculation
        return NutritionCalculator.calculate_macros(calories, weight, goal)

    @staticmethod
    def calculate_macros(calories: int, weight: float, goal: str) -> Dict[str, int]:
        """Calculate macro split based on calorie target."""
        
        # Protein Strategy
        # Lose Weight -> High Protein (to spare muscle) -> ~2.0g/kg
        # Gain Mass -> High Protein -> ~2.0g/kg
        # Maintain/Healthy -> Moderate -> ~1.6g/kg
        
        if goal in ["lose_weight", "gain_mass"]:
            protein_per_kg = 2.0
        else:
            protein_per_kg = 1.6
            
        protein = int(weight * protein_per_kg)
        
        # Safety cap for protein (e.g. not more than 35% of calories usually, or 3g/kg)
        # 1g Protein = 4 kcal
        protein_cals = protein * 4
        
        # Fat Strategy
        # Standard: 25-30% of total calories
        fat_pct = 0.25
        fat_cals = int(calories * fat_pct)
        fat = int(fat_cals / 9)
        
        # Carbs Strategy
        # Remainder
        carbs_cals = calories - protein_cals - fat_cals
        
        # Safety check: if carbs < 0 (impossible), adjust protein/fat down
        if carbs_cals < 0:
            carbs_cals = 0
            # Scale down others if needed, but for now just clip
            
        carbs = int(carbs_cals / 4)
        
        # Fiber Recommendation (General rule: 14g per 1000kcal)
        fiber = int((calories / 1000) * 14)
        
        return {
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carbs": carbs,
            "fiber": fiber
        }
