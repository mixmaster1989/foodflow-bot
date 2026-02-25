
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database.models import SavedDish, User
from handlers import saved_dishes


# --- Mock Normalization Service ---
# We mock this to avoid real API calls and ensure deterministic results
async def mock_analyze_food_intake(description):
    if "Banana" in description:
        return {
            "name": "Banana",
            "base_name": "Banana",
            "weight_grams": 100.0,
            "weight_missing": False,
            "calories": 90.0,
            "protein": 1.0,
            "fat": 0.5,
            "carbs": 23.0,
            "fiber": 2.6
        }
    if "Milk" in description:
        return {
            "name": "Milk",
            "base_name": "Milk",
            "weight_grams": 200.0,
            "weight_missing": False,
            "calories": 120.0,
            "protein": 6.0,
            "fat": 6.5,
            "carbs": 9.0,
            "fiber": 0.0
        }
    return {}

@pytest.mark.asyncio
async def test_dish_builder_integration(db_session):
    """
    Integration test for 'Build Dish' flow:
    1. Start Builder.
    2. Add Ingredient 1 (Banana 100g).
    3. Add Ingredient 2 (Milk 200g).
    4. Finish Building.
    5. Name and Save Dish ("Banana Milkshake").
    6. Verify SavedDish in DB with correct totals.
    """
    # 1. Setup User
    user_id = 998877
    user = User(id=user_id, username="chef_tester", first_name="Chef", last_name="Boyardee")
    db_session.add(user)
    await db_session.commit()

    # Setup State (In-Memory FSM)
    # We use a real-ish dict storage for the FSM to verify data passing
    state_storage = {}

    # Mock FSMContext to read/write to our state_storage
    state = AsyncMock(spec=FSMContext)

    async def update_data(**kwargs):
        state_storage.update(kwargs)
        return state_storage

    async def get_data():
        return state_storage

    async def set_state(s):
        state_storage['state'] = s

    state.update_data.side_effect = update_data
    state.get_data.side_effect = get_data
    state.set_state.side_effect = set_state

    # ---------------------------------------------------------
    # Step 1: Start Builder
    # ---------------------------------------------------------
    callback_start = AsyncMock(spec=CallbackQuery)
    # Configure nested mock manually for spec compliance or just set it
    user_mock = MagicMock()
    user_mock.id = user_id
    callback_start.from_user = user_mock
    callback_start.message = AsyncMock(spec=Message)
    callback_start.message.edit_text = AsyncMock()
    callback_start.answer = AsyncMock()

    await saved_dishes.start_build_dish(callback_start, state)

    assert state_storage['dish_components'] == []
    assert state_storage['total_stats']['cal'] == 0

    # ---------------------------------------------------------
    # Step 2: Add Ingredient 1 (Banana)
    # ---------------------------------------------------------
    msg_ing1 = AsyncMock(spec=Message)
    msg_ing1.from_user = MagicMock()
    msg_ing1.from_user.id = user_id
    msg_ing1.text = "Banana 100g"
    msg_ing1.answer = AsyncMock() # Mock answer (which returns a msg that gets edited)
    msg_ing1_reply = AsyncMock()
    msg_ing1.answer.return_value = msg_ing1_reply

    # Patch Normalization Service
    with patch('services.normalization.NormalizationService.analyze_food_intake', side_effect=mock_analyze_food_intake):
        await saved_dishes.process_ingredient_input(msg_ing1, state)

    # Verify State after Ingredient 1
    assert len(state_storage['dish_components']) == 1
    assert state_storage['dish_components'][0]['name'] == "Banana"
    assert state_storage['total_stats']['cal'] == 90.0

    # ---------------------------------------------------------
    # Step 3: Add Ingredient 2 (Milk)
    # ---------------------------------------------------------
    msg_ing2 = AsyncMock(spec=Message)
    msg_ing2.from_user = MagicMock()
    msg_ing2.from_user.id = user_id
    msg_ing2.text = "Milk 200g"
    msg_ing2.answer = AsyncMock()
    msg_ing2_reply = AsyncMock()
    msg_ing2.answer.return_value = msg_ing2_reply

    with patch('services.normalization.NormalizationService.analyze_food_intake', side_effect=mock_analyze_food_intake):
        await saved_dishes.process_ingredient_input(msg_ing2, state)

    # Verify State after Ingredient 2
    assert len(state_storage['dish_components']) == 2
    assert state_storage['dish_components'][1]['name'] == "Milk"
    # Totals: 90 + 120 = 210 cal; 2.6 + 0 = 2.6 fiber
    assert state_storage['total_stats']['cal'] == 210.0
    assert state_storage['total_stats']['fib'] == 2.6

    # ---------------------------------------------------------
    # Step 4: Finish Building
    # ---------------------------------------------------------
    callback_finish = AsyncMock(spec=CallbackQuery)
    callback_finish.from_user = MagicMock()
    callback_finish.from_user.id = user_id
    callback_finish.message = AsyncMock()
    callback_finish.message.edit_text = AsyncMock()
    callback_finish.answer = AsyncMock()

    await saved_dishes.finish_building_dish(callback_finish, state)

    # Should transition to naming state
    assert state_storage['state'] == saved_dishes.SavedDishStates.naming_dish

    # ---------------------------------------------------------
    # Step 5: Name and Save
    # ---------------------------------------------------------
    msg_name = AsyncMock(spec=Message)
    msg_name.chat = MagicMock()
    msg_name.chat.id = user_id
    msg_name.from_user = MagicMock()
    msg_name.from_user.id = user_id
    msg_name.text = "Banana Milkshake"
    msg_name.answer = AsyncMock()

    # Mock get_db to return our test db_session
    async def mock_get_db():
        yield db_session

    with patch('handlers.saved_dishes.get_db', side_effect=mock_get_db):
        await saved_dishes.save_dish_final(msg_name, state)

    # ---------------------------------------------------------
    # Step 6: Verify Persistence
    # ---------------------------------------------------------
    result = await db_session.execute(
        select(SavedDish).where(SavedDish.user_id == user_id)
    )
    dishes = result.scalars().all()

    assert len(dishes) == 1
    saved_dish = dishes[0]

    # Assertions
    assert saved_dish.name == "Banana Milkshake"
    assert saved_dish.total_calories == 210.0
    assert saved_dish.total_fiber == 2.6
    assert len(saved_dish.components) == 2
    assert saved_dish.components[0]['name'] == 'Banana'
    assert saved_dish.components[1]['name'] == 'Milk'

    print("\n✅ Integration Test Passed: Dish 'Banana Milkshake' created and verified in DB.")
