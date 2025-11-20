from aiogram import Router, F, types, Bot
from aiogram.enums import ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from FoodFlow.services.ocr import OCRService
from FoodFlow.services.normalization import NormalizationService
from FoodFlow.database.base import get_db
from FoodFlow.database.models import Receipt, Product
import io

router = Router()

@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    # Create Inline Keyboard
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Это чек", callback_data="action_receipt")
    builder.button(text="🏷️ Это ценник", callback_data="action_price_tag")
    builder.button(text="🍽️ Я это съел", callback_data="action_log_food")
    builder.button(text="❌ Отмена", callback_data="action_cancel")
    builder.adjust(1) # 1 button per row
    
    # Save file_id in state or just pass it? 
    # For simplicity, we can't easily pass the file_id in callback_data (too long).
    # We should ask the user to reply or just assume the last photo.
    # BETTER APPROACH: Reply to the photo with the menu. 
    # The callback handler will need to access the original message (which is the photo).
    # But callback_query.message is the message WITH buttons (bot's message), not the user's photo.
    # However, callback_query.message.reply_to_message might be the user's photo if we reply.
    
    await message.reply(
        "📸 **Вижу фото!** Что с ним сделать?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "action_cancel")
async def cancel_action(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

@router.callback_query(F.data == "action_price_tag")
async def price_tag_action(callback: types.CallbackQuery):
    await callback.answer("Функция в разработке! (Phase 2)", show_alert=True)

@router.callback_query(F.data == "action_log_food")
async def log_food_action(callback: types.CallbackQuery):
    await callback.answer("Функция 'Дневник питания' скоро будет!", show_alert=True)

@router.callback_query(F.data == "action_receipt")
async def process_receipt(callback: types.CallbackQuery, bot: Bot):
    # Get the original photo message
    photo_message = callback.message.reply_to_message
    if not photo_message or not photo_message.photo:
        await callback.message.edit_text("❌ Ошибка: не могу найти исходное фото.")
        return

    await callback.message.edit_text("⏳ Анализирую чек... (это может занять пару секунд)")
    
    try:
        # Download photo
        photo = photo_message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, photo_bytes)
        image_data = photo_bytes.getvalue()
        
        # Call OCR
        data = await OCRService.parse_receipt(image_data)
        
        # Call Normalization (Perplexity)
        status_msg_text = "⏳ Анализирую чек... (OCR завершен, нормализую названия...)"
        try:
            await callback.message.edit_text(status_msg_text)
        except:
            pass

        raw_items = data.get("items", [])
        normalized_items = await NormalizationService.normalize_products(raw_items)
        
        # Save to DB
        # Save to DB and send individual messages
        product_ids = []
        async for session in get_db():
            receipt = Receipt(
                user_id=photo_message.from_user.id,
                raw_text=str(data),
                total_amount=data.get("total", 0.0)
            )
            session.add(receipt)
            await session.flush() # Get ID
            
            for item in normalized_items:
                product = Product(
                    receipt_id=receipt.id,
                    name=item.get("name", "Unknown"),
                    price=item.get("price", 0.0),
                    quantity=item.get("quantity", 1.0),
                    category=item.get("category", "Uncategorized")
                )
                session.add(product)
                await session.flush()  # Get product ID
                product_ids.append(product.id)
            
            await session.commit()
        
        # Delete status message
        await callback.message.delete()
        
        # Send summary first
        await callback.message.answer(
            f"✅ <b>Чек обработан!</b>\n\n"
            f"💰 <b>Итого:</b> {data.get('total', 0.0)}р\n"
            f"📦 <b>Позиций:</b> {len(normalized_items)}\n\n"
            f"Продукты добавлены в холодильник.",
            parse_mode="HTML"
        )
        
        # Send each product as separate message with correction button
        for idx, item in enumerate(normalized_items):
            product_id = product_ids[idx]
            builder = InlineKeyboardBuilder()
            builder.button(text="✏️ Коррекция", callback_data=f"correct_{product_id}")
            
            await callback.message.answer(
                f"▫️ <b>{item.get('name')}</b>\n"
                f"💵 {item.get('price')}р × {item.get('quantity')} шт\n"
                f"🏷️ {item.get('category')}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при обработке: {str(e)}")
