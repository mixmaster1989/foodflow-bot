
import asyncio
import logging
import sqlite3
import os
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import FSInputFile

# --- CONFIGURATION ---
TOKEN = "8486697960:AAFxWmY9vR0SjCgSDV-_HJoQujStkqq-l-E"
CHANNEL_ID = -1003856929949 
ADMIN_IDS = [432823154]
DB_PATH = "reception.db"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waitlist (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            bonus_days INTEGER DEFAULT 0,
            referred_by_id INTEGER,
            refs_count INTEGER DEFAULT 0,
            has_joined_channel BOOLEAN DEFAULT 0,
            has_requested_ref BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM waitlist WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "bonus_days": row[2],
            "referred_by_id": row[3],
            "refs_count": row[4],
            "has_joined_channel": row[5],
            "has_requested_ref": row[6]
        }
    return None

def create_user(user_id, username, referred_by_id=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO waitlist (user_id, username, referred_by_id) VALUES (?, ?, ?)",
            (user_id, username, referred_by_id)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error creating user: {e}")
    finally:
        conn.close()

def update_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    cursor.execute(f"UPDATE waitlist SET {set_clause} WHERE user_id = ?", values)
    conn.commit()
    conn.close()

# --- BOT LOGIC ---
bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_emoji_number(n):
    mapping = {
        '0': '\u0030\uFE0F\u20E3', '1': '\u0031\uFE0F\u20E3', '2': '\u0032\uFE0F\u20E3', 
        '3': '\u0033\uFE0F\u20E3', '4': '\u0034\uFE0F\u20E3', '5': '\u0035\uFE0F\u20E3', 
        '6': '\u0036\uFE0F\u20E3', '7': '\u0037\uFE0F\u20E3', '8': '\u0038\uFE0F\u20E3', 
        '9': '\u0039\uFE0F\u20E3'
    }
    return "".join(mapping.get(d, d) for d in str(n))

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Handle referral
    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id != user_id:
            referred_by = ref_id

    user = get_user(user_id)
    if not user:
        create_user(user_id, username, referred_by)
        user = get_user(user_id)

    # Calculate Spots Left (Keep for exclusivity effect)
    try:
        count = await bot.get_chat_member_count(CHANNEL_ID)
        spots_left = max(0, 100 - count)
    except Exception:
        spots_left = "??"

    builder = InlineKeyboardBuilder()
    # Main CTA Button
    builder.button(text="🚀 ПЕРЕЙТИ В БОТ (FoodFlow)", url="https://t.me/FoodFlow2026bot")
    
    if user and user["has_joined_channel"]:
        status_info = (
            f"\n\n<b>Вы в списке Пионеров! ✅</b>\n"
            f" 👥 Приглашено друзей: <b>{get_emoji_number(user['refs_count'])}</b>\n"
            f" 🎁 Бонусов накоплено: <b>{get_emoji_number(user['bonus_days'])} дней PRO</b>\n\n"
            f"<i>Все бонусы будут автоматически зачислены в основном боте!</i>"
        )
        builder.button(text="🔗 Моя реф-ссылка для бонусов", callback_data="get_ref")
    else:
        status_info = (
            f"\n\nХочешь получить <b>3 дня PRO-доступа</b> в подарок?\n"
            "1️⃣ Вступи в наш секретный канал.\n"
            "2️⃣ Нажми кнопку «Проверить» ниже."
        )
        builder.button(text="📢 Вступить в канал", url="https://t.me/+g1gHtCNUHZBjN2Fi")
        builder.button(text="✅ Я вступил, проверить!", callback_data="check_sub")

    builder.adjust(1)
    welcome_text = (
        f"🥳 <b>УРА! МЫ ЗАПУСТИЛИСЬ, {username}!</b>\n\n"
        "Проект FoodFlow официально открыт. Ты получил это приглашение как участник <b>Закрытого списка</b>. 💎\n\n"
        "Статус «Пионера» всё еще доступен для первых <b>100</b> участников. "
        "Это дает вечный доступ к секретным функциям и бонусы на старте! 🏆\n\n"
        f"🔥 Осталось мест: <b>{get_emoji_number(spots_left)}</b>\n"
        f"{status_info}\n\n"
        "<b>Скорее заходи в основной бот и начинай менять свою жизнь прямо сейчас!</b> 👇"
    )
    
    video_path = "/home/user1/foodflow-bot_new/assets/grok-video-74406efc-afd9-467a-a40a-b9936f3beaf7.mp4"
    if os.path.exists(video_path):
        video = FSInputFile(video_path)
        await message.answer_video(
            video=video,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "check_sub")
async def handle_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user and user["has_joined_channel"]:
        await callback.answer("\u2705 \u0422\u044B \u0443\u0436\u0435 \u0432 \u0441\u043F\u0438\u0441\u043A\u0435 \u0438\u0437\u0431\u0440\u0430\u043D\u043D\u044B\u0445!", show_alert=True)
        return

    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            # Grant 3 days
            new_bonus = (user["bonus_days"] if user else 0) + 3
            update_user(user_id, has_joined_channel=1, bonus_days=new_bonus)
            
            # Handle referrer bonus (1:1 logic)
            if user and user["referred_by_id"]:
                ref_id = user["referred_by_id"]
                referrer = get_user(ref_id)
                if referrer and referrer["refs_count"] < 3:
                    update_user(ref_id, 
                                bonus_days=referrer["bonus_days"] + 1, 
                                refs_count=referrer["refs_count"] + 1)
                    try:
                        await bot.send_message(ref_id, "\U0001F389 \u0422\u0432\u043E\u0439 \u0434\u0440\u0443\u0433 \u0432\u0441\u0442\u0443\u043F\u0438\u043B \u0432 \u043A\u0430\u043D\u0430\u043B! \u0422\u0435\u0431\u0435 \u043D\u0430\u0447\u0438\u0441\u043B\u0435\u043D <b>+1 \u0434\u0435\u043D\u044C PRO</b>! \U0001F680", parse_mode="HTML")
                    except Exception:
                        pass

            builder = InlineKeyboardBuilder()
            builder.button(text="\U0001F517 \u041F\u043E\u043B\u0443\u0447\u0438\u0442\u044C \u0440\u0435\u0444-\u0441\u0441\u044B\u043B\u043A\u0443 (+1 \u0434\u0435\u043D\u044C)", callback_data="get_ref")
            builder.adjust(1)

            success_text = (
                "\U0001F3AF <b>\u041F\u043E\u0437\u0434\u0440\u0430\u0432\u043B\u044F\u0435\u043C!</b> \u0422\u044B \u0432 \u0441\u043F\u0438\u0441\u043A\u0435 \u041F\u0438\u043E\u043D\u0435\u0440\u043E\u0432 FoodFlow.\n\n"
                "\u0422\u0435\u0431\u0435 \u043D\u0430\u0447\u0438\u0441\u043B\u0435\u043D\u043E <b>3 \u0434\u043D\u044F PRO</b>. \U0001F381\n\n"
                "\u0425\u043E\u0447\u0435\u0448\u044C \u0435\u0449\u0435? \u0416\u043C\u0438 \u043A\u043D\u043E\u043F\u043A\u0443 \u043D\u0438\u0436\u0435, \u0447\u0442\u043E\u0431\u044B \u043F\u043E\u043B\u0443\u0447\u0438\u0442\u044C \u0440\u0435\u0444-\u0441\u0441\u044B\u043B\u043A\u0443. "
                "\u0417\u0430 \u0441\u0430\u043C\u0443 \u0433\u0435\u043D\u0435\u0440\u0430\u0446\u0438\u044E \u0441\u0441\u044B\u043B\u043A\u0438 \u0434\u0430\u0440\u0438\u043C <b>+1 \u0434\u0435\u043D\u044C</b>, \u0430 \u0437\u0430 \u043A\u0430\u0436\u0434\u043E\u0433\u043E \u0438\u0437 \u043F\u0435\u0440\u0432\u044B\u0445 3-\u0445 \u0434\u0440\u0443\u0437\u0435\u0439 \u2014 \u0435\u0449\u0435 \u043F\u043E \u0434\u043D\u044E! \U0001F525"
            )
            await callback.message.answer(success_text, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            await callback.answer("\u274C \u0422\u044B \u0435\u0449\u0435 \u043D\u0435 \u043F\u043E\u0434\u043F\u0438\u0441\u0430\u043D \u043D\u0430 \u043A\u0430\u043D\u0430\u043B! \u041F\u043E\u0434\u043F\u0438\u0441\u044C \u0438 \u043F\u043E\u043F\u0440\u043E\u0431\u0443\u0439 \u0441\u043D\u043E\u0432\u0430. \U0001F957", show_alert=True)
    except Exception as e:
        logger.error(f"Error checking sub: {e}")
        await callback.answer("\u26A0\uFE0F \u041E\u0448\u0438\u0431\u043A\u0430 \u043F\u0440\u043E\u0432\u0435\u0440\u0438. \u0423\u0431\u0435\u0434\u0438\u0441\u044C, \u0447\u0442\u043E \u0431\u043E\u0442 \u2014 \u0430\u0434\u043C\u0438\u043D \u0432 \u043A\u0430\u043D\u0430\u043B\u0435. \D83D\uDDE0", show_alert=True)

@dp.callback_query(F.data == "get_ref")
async def handle_get_ref(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not user or not user["has_joined_channel"]:
        await callback.answer("\u274C \u0421\u043F\u0430\u0447\u0430\u043B\u0430 \u043F\u043E\u0434\u043F\u0438\u0441\u043D\u0438\u0441\u044C \u043D\u0430 \u043A\u0430\u043D\u0430\u043B!", show_alert=True)
        return

    bonus_add = 0
    if not user["has_requested_ref"]:
        bonus_add = 1
        update_user(user_id, has_requested_ref=1, bonus_days=user["bonus_days"] + 1)
        user = get_user(user_id) # Refresh user data
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    current_bonus = user["bonus_days"]
    
    ref_text = (
        "🚀 <b>Твоя реферальная программа активирована!</b>\n\n"
        f"Твой текущий бонус: <b>{current_bonus} дней PRO</b> 💎\n\n"
        "Твоя ссылка для друзей:\n"
        f"<code>{ref_link}</code>\n\n"
        "🎁 <b>Условия:</b>\n"
        "• +1 день PRO сразу (уже начислен).\n"
        "• +1 день за каждого из первых 3-х друзей.\n\n"
        "<i>Делись ссылкой и копи бонусы! После перехода в основной бот они будут синхронизированы.</i> 🙌"
    )
    await callback.message.answer(ref_text, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(bonus_days) FROM waitlist")
    stats = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM waitlist WHERE has_joined_channel = 1")
    subs = cursor.fetchone()[0]
    conn.close()
    
    await message.answer(
        f"\U0001F4CA <b>\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430 \u0420\u0435\u0441\u0435\u043F\u0448\u043D-\u0431\u043E\u0442\u0430:</b>\n\n"
        f"\uD83D\uDC65 \u0412\u0441\u0435\u0433\u043E \u044E\u0437\u0435\u0440\u043E\u0432: {stats[0]}\n"
        f"\u2705 \u041F\u043E\u0434\u043F\u0438\u0441\u0430\u043B\u0438\u0441\u044C \u043D\u0430 \u043A\u0430\u043D\u0430\u043B: {subs}\n"
        f"\U0001F381 \u0412\u0441\u0435\u0433\u043E \u0431\u043E\u043D\u0443\u0441\u043D\u044B\u0445 \u0434\u043D\u0435\u0439: {stats[1] or 0}",
        parse_mode="HTML"
    )

async def start_bot():
    init_db()
    logger.info("Reception Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(start_bot())
