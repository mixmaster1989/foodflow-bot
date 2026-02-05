"""Module for Curator's Marathon Management."""

from datetime import datetime, timedelta
import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from database.base import get_db
from database.models import User, Marathon, MarathonParticipant
from utils.user import get_user_display_name, get_user_display_long

logger = logging.getLogger(__name__)

router = Router()

class CuratorMarathonStates(StatesGroup):
    """FSM states for curator marathon management."""
    creating_name = State()
    creating_dates = State()
    
    adding_participants = State() # Selecting participants
    
    managing_waves = State() # Editing wave toggles
    
    creating_wave_name = State() # Wave name input
    creating_wave_dates = State() # Wave dates input
    
    awarding_snowflakes = State() # Selecting user to award
    entering_snowflake_amount = State() # Entering amount
    entering_snowflake_reason = State() # Entering reason


@router.callback_query(F.data == "curator_marathon_menu")
async def show_marathon_menu(callback: types.CallbackQuery) -> None:
    """Show main marathon menu for curator."""
    user_id = callback.from_user.id
    
    async for session in get_db():
        # Check if user is a curator (has role or wards)
        # For MVP, we assume if they can see this button, they are authorized.
        # But let's check active marathon.
        
        stmt = select(Marathon).where(
            Marathon.curator_id == user_id, 
            Marathon.is_active == True
        )
        marathon = (await session.execute(stmt)).scalar_one_or_none()
        
        builder = InlineKeyboardBuilder()
        
        if not marathon:
            # 1. No Active Marathon -> Prompt to Create
            builder.button(text="🆕 Создать Марафон", callback_data="marathon_create")
            builder.button(text="🔙 Назад", callback_data="main_menu") # Assuming main menu callback
            builder.adjust(1)
            
            text = (
                "🏆 **Управление Марафоном**\n\n"
                "У вас пока нет активного марафона.\n"
                "Создайте новый, чтобы начать соревнование!"
            )
        else:
            # 2. Active Marathon -> Management Dashboard
            
            # Get stats
            part_count = await session.scalar(
                select(func.count(MarathonParticipant.id))
                .where(MarathonParticipant.marathon_id == marathon.id, MarathonParticipant.is_active == True)
            )
            
            # Registration Status
            reg_status_icon = "🟢" if getattr(marathon, "is_registration_open", True) else "🔴"
            reg_action_text = "🔴 Закрыть рег." if getattr(marathon, "is_registration_open", True) else "🟢 Открыть рег."
            
            builder.button(text="🔗 Пригласить", callback_data=f"marathon_invite:{marathon.id}")
            builder.button(text=reg_action_text, callback_data=f"marathon_toggle_reg:{marathon.id}")
            
            builder.button(text="👥 Участники", callback_data=f"marathon_participants:{marathon.id}")
            builder.button(text="❄️ Снежинки (Баллы)", callback_data=f"marathon_snowflakes:{marathon.id}")
            builder.button(text="📊 Рейтинг (Вес)", callback_data=f"marathon_leaderboard:{marathon.id}")
            builder.button(text="⚙️ Настройки Волн", callback_data=f"marathon_waves:{marathon.id}")
            builder.button(text="🛑 Завершить Марафон", callback_data=f"marathon_stop_confirm:{marathon.id}")
            builder.button(text="🔙 Назад", callback_data="main_menu")
            builder.adjust(2, 2, 1, 1, 1, 1)
            
            # Determine status of waves
            waves = marathon.waves_config or {}
            current_wave = "Ожидание"
            now = datetime.utcnow()
            
            if marathon.start_date > now:
                current_wave = "⏳ До старта"
            elif marathon.end_date < now:
                current_wave = "🏁 Завершен (ждет закрытия)"
            else:
                current_wave = "🔥 Идет"

            reg_text = "Открыта" if getattr(marathon, "is_registration_open", True) else "Закрыта"

            text = (
                f"🏆 **Марафон: {marathon.name}**\n\n"
                f"📅 Даты: {marathon.start_date.strftime('%d.%m')} - {marathon.end_date.strftime('%d.%m')}\n"
                f"👥 Участников: **{part_count}**\n"
                f"📝 Регистрация: **{reg_status_icon} {reg_text}**\n"
                f"Статус: {current_wave}\n"
            )

        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
             await callback.message.delete()
             await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()


@router.callback_query(F.data == "marathon_create")
async def start_create_marathon(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start creation wizard."""
    await state.set_state(CuratorMarathonStates.creating_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="curator_marathon_menu")
    
    text = (
        "🆕 **Создание Марафона**\n\n"
        "Введите название для вашего марафона:\n"
        "*(Например: Весенняя Перезагрузка)*"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@router.message(CuratorMarathonStates.creating_name)
async def process_marathon_name(message: types.Message, state: FSMContext) -> None:
    """Save name and ask for dates."""
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(CuratorMarathonStates.creating_dates)
    
    text = (
        f"✅ Название: **{name}**\n\n"
        "Теперь введите **дату начала и дату конца** через пробел или запятую.\n"
        "Формат: ДД.ММ.ГГГГ\n\n"
        "Пример: `01.03.2026 30.03.2026`"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(CuratorMarathonStates.creating_dates)
async def process_marathon_dates(message: types.Message, state: FSMContext) -> None:
    """Parse dates and create marathon."""
    try:
        raw = message.text.replace(",", " ").strip()
        parts = raw.split()
        
        if len(parts) != 2:
            raise ValueError("Need 2 dates")
            
        start_date = datetime.strptime(parts[0], "%d.%m.%Y")
        end_date = datetime.strptime(parts[1], "%d.%m.%Y")
        
        if end_date <= start_date:
            await message.answer("❌ Дата конца должна быть позже даты начала.")
            return

        data = await state.get_data()
        name = data.get("name")
        user_id = message.from_user.id
        
        async for session in get_db():
            # Deactivate any existing active marathon (safety)
            await session.execute(
                update(Marathon)
                .where(Marathon.curator_id == user_id, Marathon.is_active == True)
                .values(is_active=False)
            )
            
            # Create new
            marathon = Marathon(
                curator_id=user_id,
                name=name,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                waves_config={} # Empty config initially
            )
            session.add(marathon)
            await session.commit()
            
            # Auto-add wards? No, user requested Manual Selection.
            # But we can prompt to add wards.
        
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="👥 Добавить участников", callback_data="curator_marathon_menu") # Takes back to menu where they can click Participants
        
        await message.answer(
            f"🎉 **Марафон '{name}' создан!**\n\n"
            f"📅 {start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')}\n\n"
            "Теперь добавьте участников через меню.",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer("❌ Ошибка формата. Попробуйте еще раз:\n`ДД.ММ.ГГГГ ДД.ММ.ГГГГ`")


@router.callback_query(F.data.startswith("marathon_participants:"))
async def manage_participants_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show list of wards to manage participation."""
    marathon_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async for session in get_db():
        # Get all wards
        wards_result = await session.execute(
            select(User).where(User.curator_id == user_id)
        )
        wards = wards_result.scalars().all()
        
        # Get existing participants
        participants_result = await session.execute(
            select(MarathonParticipant.user_id)
            .where(MarathonParticipant.marathon_id == marathon_id, MarathonParticipant.is_active == True)
        )
        existing_ids = {p for p in participants_result.scalars().all()} # Set for fast lookup
        
        # Build UI with Multi-Select Checkboxes
        builder = InlineKeyboardBuilder()
        
        # Retrieve currently toggled state (if any) or existing db state
        state_data = await state.get_data()
        selected_ids = state_data.get("selected_participants", list(existing_ids))
        
        for ward in wards:
            is_selected = ward.id in selected_ids
            mark = "✅" if is_selected else "⬜"
            name = get_user_display_name(ward)
            builder.button(
                text=f"{mark} {name}", 
                callback_data=f"toggle_part:{marathon_id}:{ward.id}"
            )
        
        builder.adjust(1) # Column
        
        builder.button(text="💾 Сохранить список", callback_data=f"save_participants:{marathon_id}")
        builder.button(text="🔙 Назад", callback_data="curator_marathon_menu")
        
        await state.update_data(selected_participants=selected_ids)
        
        text = (
            "👥 **Управление Участниками**\n\n"
            "Отметьте галочками тех, кто участвует в марафоне.\n"
            "Нажмите 'Сохранить', чтобы применить изменения."
        )
        
        try:
             await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
             # If message content same, telegram errs. Ignore or re-send.
             pass
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_part:"))
async def toggle_participant(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Toggle a specific user in the selection."""
    _, marathon_id_str, target_id_str = callback.data.split(":")
    marathon_id = int(marathon_id_str)
    target_id = int(target_id_str)
    
    data = await state.get_data()
    selected_ids = set(data.get("selected_participants", []))
    
    if target_id in selected_ids:
        selected_ids.remove(target_id)
    else:
        selected_ids.add(target_id)
        
    await state.update_data(selected_participants=list(selected_ids))
    
    # Refresh list (call main handler again)
    # We call managing logic directly to avoid code duplication, but need to mock callback?
    # Easier to just rebuild markup here or call the function.
    # Recursion is fine here since it's event driven.
    # But let's verify if we can simply "click" the menu button button virtually
    
    # We will just re-call manage_participants_menu contextually
    # Note: State is updated, so it will render correctly.
    await manage_participants_menu(callback, state)


@router.callback_query(F.data.startswith("save_participants:"))
async def save_participants(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Commit changes to DB."""
    marathon_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_ids = set(data.get("selected_participants", []))
    
    async for session in get_db():
        # Get current state in DB
        result = await session.execute(
            select(MarathonParticipant)
            .where(MarathonParticipant.marathon_id == marathon_id)
        )
        existing_records = result.scalars().all()
        existing_map = {r.user_id: r for r in existing_records}
        
        added_count = 0
        removed_count = 0
        
        # 1. Process additions/activations
        for uid in selected_ids:
            if uid in existing_map:
                record = existing_map[uid]
                if not record.is_active:
                    record.is_active = True # Reactivate
                    added_count += 1
            else:
                # Create new
                # Need start weight? For now, leave None or fetch latest weight log?
                # Let's try fetching latest weight log
                from database.models import WeightLog
                w_stmt = select(WeightLog.weight).where(WeightLog.user_id == uid).order_by(WeightLog.recorded_at.desc()).limit(1)
                start_w = await session.scalar(w_stmt)
                
                new_part = MarathonParticipant(
                    marathon_id=marathon_id,
                    user_id=uid,
                    start_weight=start_w,
                    is_active=True
                )
                session.add(new_part)
                added_count += 1

        # 2. Process removals (soft delete)
        for uid, record in existing_map.items():
            if uid not in selected_ids and record.is_active:
                record.is_active = False
                removed_count += 1
                
        await session.commit()
    
    await callback.answer(f"✅ Сохранено! +{added_count} / -{removed_count}", show_alert=True)
    await show_marathon_menu(callback)


# ===================== SNOWFLAKES =====================

@router.callback_query(F.data.startswith("marathon_snowflakes:"))
async def show_snowflakes_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show list of participants to award snowflakes."""
    marathon_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        # Get active participants with user info
        result = await session.execute(
            select(MarathonParticipant, User)
            .join(User, MarathonParticipant.user_id == User.id)
            .where(MarathonParticipant.marathon_id == marathon_id, MarathonParticipant.is_active == True)
        )
        participants = result.all()
        
        builder = InlineKeyboardBuilder()
        
        for part, user in participants:
            name = get_user_display_name(user)
            builder.button(
                text=f"❄️ {part.total_snowflakes} | {name}",
                callback_data=f"snowflake_select:{marathon_id}:{part.id}"
            )
        
        builder.adjust(1)
        builder.button(text="🔙 Назад", callback_data="curator_marathon_menu")
        
        text = (
            "❄️ **Начисление Снежинок**\n\n"
            "Выберите участника для начисления баллов.\n"
            "Текущий счет отображается слева от имени."
        )
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("snowflake_select:"))
async def select_snowflake_amount(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show quick buttons for snowflake amount."""
    _, marathon_id_str, participant_id_str = callback.data.split(":")
    marathon_id = int(marathon_id_str)
    participant_id = int(participant_id_str)
    
    await state.update_data(marathon_id=marathon_id, participant_id=participant_id)
    
    builder = InlineKeyboardBuilder()
    for amount in [1, 2, 3, 5, 10]:
        builder.button(text=f"+{amount}", callback_data=f"snowflake_add:{amount}")
    builder.button(text="✏️ Другое число", callback_data="snowflake_custom")
    builder.button(text="🔙 Назад", callback_data=f"marathon_snowflakes:{marathon_id}")
    builder.adjust(5, 1, 1)
    
    text = "❄️ Сколько снежинок начислить?"
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("snowflake_add:"))
async def add_snowflakes(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Add specified amount of snowflakes."""
    amount = int(callback.data.split(":")[1])
    data = await state.get_data()
    participant_id = data.get("participant_id")
    marathon_id = data.get("marathon_id")
    curator_id = callback.from_user.id
    
    from database.models import SnowflakeLog
    
    async for session in get_db():
        # Get participant
        part = await session.get(MarathonParticipant, participant_id)
        if part:
            part.total_snowflakes += amount
            
            # Log
            log = SnowflakeLog(
                participant_id=participant_id,
                curator_id=curator_id,
                amount=amount,
                reason="Quick add"
            )
            session.add(log)
            await session.commit()
    
    await callback.answer(f"✅ +{amount} ❄️", show_alert=True)
    
    # Go back to snowflakes menu
    callback.data = f"marathon_snowflakes:{marathon_id}"
    await show_snowflakes_menu(callback, state)


@router.callback_query(F.data == "snowflake_custom")
async def snowflake_custom_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start custom amount input."""
    await state.set_state(CuratorMarathonStates.entering_snowflake_amount)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="curator_marathon_menu")
    
    await callback.message.edit_text(
        "✏️ Введите количество снежинок (число):\n"
        "Для списания используйте отрицательное число (например -5).",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(CuratorMarathonStates.entering_snowflake_amount)
async def process_custom_snowflakes(message: types.Message, state: FSMContext) -> None:
    """Process custom snowflake amount."""
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введите целое число.")
        return
    
    data = await state.get_data()
    participant_id = data.get("participant_id")
    curator_id = message.from_user.id
    
    from database.models import SnowflakeLog
    
    async for session in get_db():
        part = await session.get(MarathonParticipant, participant_id)
        if part:
            part.total_snowflakes += amount
            
            log = SnowflakeLog(
                participant_id=participant_id,
                curator_id=curator_id,
                amount=amount,
                reason="Custom"
            )
            session.add(log)
            await session.commit()
    
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В меню марафона", callback_data="curator_marathon_menu")
    
    sign = "+" if amount > 0 else ""
    await message.answer(f"✅ {sign}{amount} ❄️ начислено!", reply_markup=builder.as_markup())


# ===================== LEADERBOARD =====================

@router.callback_query(F.data.startswith("marathon_leaderboard:"))
async def show_leaderboard(callback: types.CallbackQuery) -> None:
    """Show weight loss leaderboard (Kg and %)."""
    marathon_id = int(callback.data.split(":")[1])
    
    from database.models import WeightLog
    
    async for session in get_db():
        # Get participants with their start weight
        result = await session.execute(
            select(MarathonParticipant, User)
            .join(User, MarathonParticipant.user_id == User.id)
            .where(MarathonParticipant.marathon_id == marathon_id, MarathonParticipant.is_active == True)
        )
        participants = result.all()
        
        leaderboard = []
        
        for part, user in participants:
            # Get latest weight
            latest_weight_stmt = (
                select(WeightLog.weight)
                .where(WeightLog.user_id == user.id)
                .order_by(WeightLog.recorded_at.desc())
                .limit(1)
            )
            current_weight = await session.scalar(latest_weight_stmt)
            
            start_w = part.start_weight or current_weight or 0
            current_w = current_weight or start_w
            
            if start_w and start_w > 0:
                loss_kg = start_w - current_w
                loss_pct = (loss_kg / start_w) * 100
            else:
                loss_kg = 0
                loss_pct = 0
            
            leaderboard.append({
                "name": get_user_display_name(user),
                "loss_kg": loss_kg,
                "loss_pct": loss_pct,
                "snowflakes": part.total_snowflakes
            })
        
        # Sort by % loss (desc)
        leaderboard.sort(key=lambda x: x["loss_pct"], reverse=True)
        
        # Build text
        lines = ["📊 **Рейтинг по Весу**\n"]
        for i, entry in enumerate(leaderboard[:10], 1):
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
            lines.append(
                f"{medal} **{entry['name']}**: -{entry['loss_kg']:.1f} кг ({entry['loss_pct']:.1f}%)"
            )
        
        lines.append("\n❄️ **Рейтинг по Снежинкам**\n")
        snowflake_sorted = sorted(leaderboard, key=lambda x: x["snowflakes"], reverse=True)
        for i, entry in enumerate(snowflake_sorted[:5], 1):
            lines.append(f"{i}. **{entry['name']}**: {entry['snowflakes']} ❄️")
        
        text = "\n".join(lines)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="curator_marathon_menu")
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


# ===================== STOP MARATHON =====================

@router.callback_query(F.data.startswith("marathon_stop_confirm:"))
async def confirm_stop_marathon(callback: types.CallbackQuery) -> None:
    """Ask for confirmation to stop marathon."""
    marathon_id = int(callback.data.split(":")[1])
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, завершить", callback_data=f"marathon_stop:{marathon_id}")
    builder.button(text="🔙 Отмена", callback_data="curator_marathon_menu")
    builder.adjust(1)
    
    text = (
        "⚠️ **Вы уверены?**\n\n"
        "Марафон будет завершен. Вы сможете просмотреть итоги, но рейтинг перестанет обновляться."
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("marathon_stop:"))
async def stop_marathon(callback: types.CallbackQuery) -> None:
    """Mark marathon as inactive."""
    marathon_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        marathon = await session.get(Marathon, marathon_id)
        if marathon:
            marathon.is_active = False
            await session.commit()
    
    await callback.answer("🏁 Марафон завершен!", show_alert=True)
    await show_marathon_menu(callback)


# ===================== INVITES & REGISTRATION =====================

@router.callback_query(F.data.startswith("marathon_invite:"))
async def show_invite_link(callback: types.CallbackQuery) -> None:
    """Generate and show invite link."""
    marathon_id = int(callback.data.split(":")[1])
    
    # Get bot username for deep link
    bot_user = await callback.bot.get_me()
    username = bot_user.username
    
    link = f"https://t.me/{username}?start=m_{marathon_id}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="curator_marathon_menu")
    
    text = (
        "🔗 **Ссылка для приглашения**\n\n"
        f"Отправьте эту ссылку участникам:\n\n"
        f"`{link}`\n\n"
        "_(Нажмите на ссылку, чтобы скопировать)_"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("marathon_toggle_reg:"))
async def toggle_registration(callback: types.CallbackQuery) -> None:
    """Toggle registration open/closed status."""
    marathon_id = int(callback.data.split(":")[1])
    
    async for session in get_db():
        marathon = await session.get(Marathon, marathon_id)
        if marathon:
            # Toggle (default to True if None)
            current = getattr(marathon, "is_registration_open", True)
            marathon.is_registration_open = not current
            await session.commit()
            
            status_text = "открыта" if marathon.is_registration_open else "закрыта"
            await callback.answer(f"📝 Регистрация {status_text}!", show_alert=False)
    
    # Refresh menu
    await show_marathon_menu(callback)


# ===================== WAVES CONFIG =====================

@router.callback_query(F.data.startswith("marathon_waves:"))
async def show_waves_config(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show wave configuration with list of current waves."""
    marathon_id = int(callback.data.split(":")[1])
    
    await state.update_data(marathon_id=marathon_id)
    
    async for session in get_db():
        marathon = await session.get(Marathon, marathon_id)
        
        if not marathon:
            await callback.answer("❌ Марафон не найден", show_alert=True)
            return
        
        waves = marathon.waves_config or {}
        # waves format: {"wave_1": {"name": "Первая волна", "start": "2026-03-01", "end": "2026-03-10"}, ...}
        
        builder = InlineKeyboardBuilder()
        
        # List existing waves
        if waves:
            for wave_id, wave_data in sorted(waves.items()):
                name = wave_data.get("name", wave_id)
                start = wave_data.get("start", "?")
                end = wave_data.get("end", "?")
                builder.button(
                    text=f"🌊 {name} ({start} — {end})",
                    callback_data=f"wave_detail:{marathon_id}:{wave_id}"
                )
        
        builder.button(text="➕ Добавить волну", callback_data=f"wave_add:{marathon_id}")
        builder.button(text="🔙 Назад", callback_data="curator_marathon_menu")
        builder.adjust(1)
        
        # Build status text
        now_str = datetime.utcnow().strftime("%d.%m")
        wave_count = len(waves)
        
        text = (
            f"⚙️ **Настройка Волн**\n\n"
            f"📅 Марафон: {marathon.start_date.strftime('%d.%m')} — {marathon.end_date.strftime('%d.%m')}\n"
            f"🌊 Волн: **{wave_count}**\n\n"
        )
        
        if not waves:
            text += "_Волны не настроены. Добавьте первую!_"
        else:
            text += "Нажмите на волну для редактирования."
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("wave_add:"))
async def start_add_wave(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start adding a new wave."""
    marathon_id = int(callback.data.split(":")[1])
    await state.update_data(marathon_id=marathon_id)
    await state.set_state(CuratorMarathonStates.creating_wave_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data=f"marathon_waves:{marathon_id}")
    
    text = (
        "➕ **Новая Волна**\n\n"
        "Введите название волны:\n"
        "_(Например: Первая волна, Старт, Финиш)_"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@router.message(CuratorMarathonStates.creating_wave_name)
async def process_wave_name(message: types.Message, state: FSMContext) -> None:
    """Save wave name and ask for dates."""
    wave_name = message.text.strip()
    await state.update_data(wave_name=wave_name)
    await state.set_state(CuratorMarathonStates.creating_wave_dates)
    
    text = (
        f"✅ Название: **{wave_name}**\n\n"
        "Теперь введите **даты начала и конца** волны:\n"
        "Формат: `ДД.ММ ДД.ММ`\n\n"
        "Пример: `01.03 10.03`"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(CuratorMarathonStates.creating_wave_dates)
async def process_wave_dates(message: types.Message, state: FSMContext) -> None:
    """Parse dates and save wave."""
    data = await state.get_data()
    marathon_id = data.get("marathon_id")
    wave_name = data.get("wave_name")
    
    try:
        raw = message.text.replace(",", " ").strip()
        parts = raw.split()
        
        if len(parts) != 2:
            raise ValueError("Need 2 dates")
        
        # Parse dates (assuming current year)
        year = datetime.utcnow().year
        start_str = parts[0]
        end_str = parts[1]
        
        # Support both DD.MM and DD.MM.YYYY
        if len(start_str) <= 5:
            start_str = f"{start_str}.{year}"
        if len(end_str) <= 5:
            end_str = f"{end_str}.{year}"
        
        start_date = datetime.strptime(start_str, "%d.%m.%Y")
        end_date = datetime.strptime(end_str, "%d.%m.%Y")
        
        if end_date <= start_date:
            await message.answer("❌ Дата конца должна быть позже даты начала.")
            return
        
        async for session in get_db():
            marathon = await session.get(Marathon, marathon_id)
            
            if not marathon:
                await message.answer("❌ Марафон не найден.")
                await state.clear()
                return
            
            # Generate wave ID
            waves = marathon.waves_config or {}
            wave_id = f"wave_{len(waves) + 1}"
            
            # Add wave
            waves[wave_id] = {
                "name": wave_name,
                "start": start_date.strftime("%d.%m"),
                "end": end_date.strftime("%d.%m")
            }
            
            marathon.waves_config = waves
            await session.commit()
        
        await state.clear()
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 К волнам", callback_data=f"marathon_waves:{marathon_id}")
        
        await message.answer(
            f"✅ **Волна '{wave_name}' создана!**\n\n"
            f"📅 {start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m')}",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer("❌ Ошибка формата. Попробуйте еще раз:\n`ДД.ММ ДД.ММ`", parse_mode="Markdown")


@router.callback_query(F.data.startswith("wave_detail:"))
async def show_wave_detail(callback: types.CallbackQuery) -> None:
    """Show wave details with delete option."""
    parts = callback.data.split(":")
    marathon_id = int(parts[1])
    wave_id = parts[2]
    
    async for session in get_db():
        marathon = await session.get(Marathon, marathon_id)
        
        if not marathon:
            await callback.answer("❌ Марафон не найден", show_alert=True)
            return
        
        waves = marathon.waves_config or {}
        wave = waves.get(wave_id)
        
        if not wave:
            await callback.answer("❌ Волна не найдена", show_alert=True)
            return
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🗑️ Удалить волну", callback_data=f"wave_delete:{marathon_id}:{wave_id}")
        builder.button(text="🔙 Назад", callback_data=f"marathon_waves:{marathon_id}")
        builder.adjust(1)
        
        text = (
            f"🌊 **{wave.get('name', wave_id)}**\n\n"
            f"📅 Начало: **{wave.get('start', '?')}**\n"
            f"📅 Конец: **{wave.get('end', '?')}**"
        )
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("wave_delete:"))
async def delete_wave(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Delete a wave from marathon."""
    parts = callback.data.split(":")
    marathon_id = int(parts[1])
    wave_id = parts[2]
    
    async for session in get_db():
        marathon = await session.get(Marathon, marathon_id)
        
        if not marathon:
            await callback.answer("❌ Марафон не найден", show_alert=True)
            return
        
        waves = marathon.waves_config or {}
        
        if wave_id in waves:
            del waves[wave_id]
            marathon.waves_config = waves
            await session.commit()
            await callback.answer("✅ Волна удалена!", show_alert=True)
        else:
            await callback.answer("❌ Волна не найдена", show_alert=True)
    
    # Go back to waves list
    callback.data = f"marathon_waves:{marathon_id}"
    await show_waves_config(callback, state)




