import asyncio
import sys
import os
sys.path.append(os.getcwd())

from unittest.mock import AsyncMock, MagicMock
from aiogram import types
from aiogram.fsm.context import FSMContext
from handlers.pilot_commands import cmd_etalon_list
from handlers.universal_input import process_text_food_logging
from config import settings

async def verify_etalon_command():
    print("\n--- Verifying /etalon Command ---")
    message = AsyncMock(spec=types.Message)
    # Set up user mock
    user_mock = MagicMock(spec=types.User)
    user_mock.id = 33587682 # Vasily (Pilot)
    message.from_user = user_mock
    message.answer = AsyncMock()
    
    await cmd_etalon_list(message)
    
    calls = message.answer.call_args_list
    if any("Список эталонных продуктов" in call[0][0] for call in calls):
        print("✅ /etalon command works for pilot users!")
    else:
        print("❌ /etalon command failed or ignored for pilot users!")

async def verify_food_logging_label():
    print("\n--- Verifying [ЭТАЛОН] Label ---")
    
    target = AsyncMock(spec=types.Message)
    user_mock = MagicMock(spec=types.User)
    user_mock.id = 33587682 # Vasily (Pilot)
    target.from_user = user_mock
    target.answer = AsyncMock()
    
    status_msg = AsyncMock(spec=types.Message)
    status_msg.edit_text = AsyncMock()
    status_msg.edit_text.return_value = status_msg
    
    state = AsyncMock(spec=FSMContext)
    
    # We need to mock show_confirmation_interface or just check state update
    # In universal_input.py:823 result of KBJUCore is processed.
    
    await process_text_food_logging(
        target=target,
        state=state,
        text="банан",
        status_msg=status_msg
    )
    
    # Check if state update data contains the label
    state_calls = state.update_data.call_args_list
    found_etalon = False
    for call in state_calls:
        # Check all possible kwargs or args
        data = call.kwargs.get("pending_product", {})
        if "💎 [ЭТАЛОН]" in data.get("name", ""):
            found_etalon = True
            print(f"✅ Found etalon label in state: {data['name']}")
    
    if found_etalon:
        print("✅ Pilot food logging uses [ЭТАЛОН] label for cached items!")
    else:
        # Print what we found to debug
        print("❌ Pilot food logging failed to add [ЭТАЛОН] label!")
        print(f"State calls: {state_calls}")

async def main():
    # Ensure pilot IDs include our test ID
    if 33587682 not in settings.PILOT_USER_IDS:
        settings.PILOT_USER_IDS.append(33587682)
    
    await verify_etalon_command()
    await verify_food_logging_label()

if __name__ == "__main__":
    asyncio.run(main())
