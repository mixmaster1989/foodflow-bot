import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from database.base import async_session
from database.models import UserSettings
from services.nutrition_calculator import NutritionCalculator


async def restore_elena():
    user_id = 109153550
    gender = "female"
    age = 48
    height = 164
    weight = 59.9
    goal = "lose_weight"

    # Calculate targets using the bot's logic
    targets = NutritionCalculator.calculate_targets(
        gender, weight, height, age, goal
    )

    print(f"Restoring Elena (ID {user_id})...")
    print(f"Params: {gender}, {age}y, {height}cm, {weight}kg, {goal}")
    print(f"Targets: {targets}")

    async with async_session() as session:
        settings = UserSettings(
            user_id=user_id,
            gender=gender,
            age=age,
            height=height,
            weight=weight,
            goal=goal,
            calorie_goal=targets["calories"],
            protein_goal=targets["protein"],
            fat_goal=targets["fat"],
            carb_goal=targets["carbs"],
            fiber_goal=targets.get("fiber", 30),
            is_initialized=True,
        )
        session.add(settings)
        await session.commit()
        print("✅ COMMITTED!")

if __name__ == "__main__":
    asyncio.run(restore_elena())
