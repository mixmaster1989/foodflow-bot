from aiogram import Router, types, F
from aiogram.filters import Command
from database.base import SessionLocal
from database.models import User
from config import OPENROUTER_API_KEY

router = Router()

@router.message(Command("buy"))
async def cmd_buy(message: types.Message):
    await message.answer_invoice(
        title="Звездная пыль (3 толкования)",
        description="Энергия для открытия тайн твоих снов",
        payload="dream_pack_3",
        currency="XTR",
        prices=[types.LabeledPrice(label="3 сновидения", amount=15)], # 15 Stars
    )

@router.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def success_payment(message: types.Message):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if user:
            user.dreams_balance += 3
            await session.commit()
    await message.answer("🌟 <b>Энергия получена!</b> Теперь ты можешь разгадать еще 3 сна.", parse_mode="HTML")
