from datetime import datetime, timedelta
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_time_picker_keyboard(callback_prefix: str) -> types.InlineKeyboardMarkup:
    """
    Returns a keyboard with preset meal times and relative offsets.
    callback_prefix: prefix for the callback_data (e.g. 'i_ate_time' or 'batch_time')
    """
    builder = InlineKeyboardBuilder()
    
    # Presets
    # Format: label, hour, minute
    presets = [
        ("☕ Завтрак (09:00)", 9, 0),
        ("🍜 Обед (13:00)", 13, 0),
        ("🥪 Перекус (16:00)", 16, 0),
        ("🍗 Ужин (19:00)", 19, 0),
    ]
    
    for label, h, m in presets:
        builder.button(text=label, callback_data=f"{callback_prefix}:preset:{h}:{m}")
    
    # Offsets
    offsets = [
        ("-30м", -30),
        ("-1ч", -60),
        ("-2ч", -120),
        ("-3ч", -180),
    ]
    
    for label, mins in offsets:
        builder.button(text=label, callback_data=f"{callback_prefix}:offset:{mins}")
        
    builder.button(text="🔙 Назад", callback_data=f"{callback_prefix}:back")
    
    builder.adjust(1, 1, 1, 1, 4, 1)
    return builder.as_markup()

def get_time_from_callback(callback_data: str) -> datetime:
    """
    Parses callback data and returns the target datetime.
    Supports presets and offsets relative to now.
    """
    parts = callback_data.split(":")
    # Expected formats:
    # prefix:preset:h:m
    # prefix:offset:mins
    
    now = datetime.now() # Use local (Moscow) time
    
    if "preset" in parts:
        h, m = int(parts[2]), int(parts[3])
        # Return today at specified time
        return now.replace(hour=h, minute=m, second=0, microsecond=0)
    
    if "offset" in parts:
        mins = int(parts[2])
        return now + timedelta(minutes=mins)
        
    return now
