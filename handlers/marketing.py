"""Marketing analytics handler for FoodFlow.

Provides bot commands and inline buttons for the marketing group.
Command /mstats shows a digest + inline menu with analytics options.
Access restricted to MARKETING_GROUP_ID and ADMIN_IDS.
"""
import logging
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from services.marketing_analytics import (
    export_csv,
    get_acquisition_funnel,
    get_acquisition_sources,
    get_daily_digest,
    get_hourly_activity,
    get_retention_metrics,
    get_tier_distribution,
)

router = Router()
logger = logging.getLogger(__name__)


def _is_authorized(event: types.Message | types.CallbackQuery) -> bool:
    """Check if the event comes from the marketing group or an admin."""
    chat_id = None
    if isinstance(event, types.CallbackQuery):
        chat_id = event.message.chat.id if event.message else None
    elif isinstance(event, types.Message):
        chat_id = event.chat.id

    # Allow from marketing group
    if chat_id == settings.MARKETING_GROUP_ID:
        return True
    # Allow admins from anywhere
    if event.from_user and event.from_user.id in settings.ADMIN_IDS:
        return True
    return False


def _build_menu() -> types.InlineKeyboardMarkup:
    """Build inline keyboard with analytics options."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Воронка (14д)", callback_data="mkt_funnel")
    builder.button(text="📈 Удержание", callback_data="mkt_retention")
    builder.button(text="💎 Тарифы", callback_data="mkt_tiers")
    builder.button(text="🕐 Часы активности", callback_data="mkt_hourly")
    builder.button(text="📋 Источники", callback_data="mkt_sources")
    builder.button(text="📥 Скачать CSV", callback_data="mkt_csv")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


@router.message(Command("mstats"))
async def cmd_mstats(message: types.Message):
    """Show marketing digest with inline menu."""
    if not _is_authorized(message):
        return

    try:
        digest = await get_daily_digest()
        await message.answer(digest, reply_markup=_build_menu())
    except Exception as e:
        logger.error(f"Error in /mstats: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "mkt_funnel")
async def cb_funnel(callback: types.CallbackQuery):
    """Show acquisition funnel."""
    if not _is_authorized(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        text = await get_acquisition_funnel(days=14)
        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "mkt_retention")
async def cb_retention(callback: types.CallbackQuery):
    """Show retention metrics."""
    if not _is_authorized(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        text = await get_retention_metrics()
        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "mkt_tiers")
async def cb_tiers(callback: types.CallbackQuery):
    """Show tier distribution."""
    if not _is_authorized(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        text = await get_tier_distribution()
        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "mkt_hourly")
async def cb_hourly(callback: types.CallbackQuery):
    """Show hourly activity heatmap."""
    if not _is_authorized(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        text = await get_hourly_activity(days=7)
        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "mkt_sources")
async def cb_sources(callback: types.CallbackQuery):
    """Show acquisition source distribution."""
    if not _is_authorized(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        text = await get_acquisition_sources()
        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data == "mkt_csv")
async def cb_csv(callback: types.CallbackQuery, bot: Bot):
    """Generate and send CSV export."""
    if not _is_authorized(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chat_id = callback.message.chat.id
    status_msg = await callback.message.answer("⏳ Генерирую CSV за 30 дней...")

    try:
        csv_io = await export_csv(days=30)
        doc = BufferedInputFile(
            csv_io.getvalue(),
            filename=f"foodflow_stats_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        await bot.send_document(
            chat_id=chat_id,
            document=doc,
            caption="📊 Статистика FoodFlow за 30 дней\nГотов для загрузки в Excel / Google Sheets."
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"CSV export failed: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {e}")

    await callback.answer()
