import asyncio
import os
import sys
from unittest.mock import AsyncMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import types

from handlers.universal_input import handle_quantity_input

# Mock objects
mock_user = AsyncMock(spec=types.User)
mock_user.id = 123456789
mock_message = AsyncMock(spec=types.Message)
mock_message.text = "2"
mock_message.answer = AsyncMock(return_value=AsyncMock(spec=types.Message))
mock_message.from_user = mock_user

mock_state = AsyncMock()
mock_state.get_data = AsyncMock(return_value={
    "pending_product": {
        "name": "Яйцо",
        "base_name": "Яйцо",
        "calories100": 150,
        "protein100": 12,
        "fat100": 10,
        "carbs100": 1,
        "fiber100": 0
    },
    "intent": "log"
})

async def test_quantity_logic():
    print("🚀 Starting Quantity Logic Simulation...")

    # Initialize DB (if needed for imports, but we mock DB calls mostly)
    # Actually handle_quantity_input uses real NormalizationService which calls API.
    # We should allow it to call API to verify real logic!

    try:
        await handle_quantity_input(mock_message, mock_state)
        print("✅ Handle function executed without error.")

        # Check if state was updated
        args, kwargs = mock_state.update_data.call_args
        product = kwargs.get('pending_product') or args[0].get('pending_product')

        print(f"📦 Resulting Product Name: {product['name']}")
        print(f"⚖️ Resulting Calories: {product['calories100']}")

        if "2 шт" in product['name']:
            print("✅ Quantity detected in name!")
        else:
            print("❌ Quantity NOT found in name.")

    except Exception as e:
        print(f"❌ Simulation Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_quantity_logic())
