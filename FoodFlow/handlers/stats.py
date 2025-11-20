from aiogram import Router, F, types

router = Router()

@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    await message.answer("📊 **Твоя статистика за сегодня:**\n\n🔥 Калории: 1200 / 2000\n🥩 Белки: 60г\n🥑 Жиры: 40г\n🍞 Углеводы: 150г")
