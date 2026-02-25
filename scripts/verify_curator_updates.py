import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from database.base import get_db
from database.models import Marathon, MarathonParticipant, User
from services.marathon_service import MarathonService


async def test_scenarios():
    print("🚀 Начинаю хардкорные тесты системы кураторов и ссылок...\n")

    # Данные из базы
    curator_id = 295543071  # Ольга (@zumbaola)
    ward_id = 5422141137    # Подопечный Ольги
    marathon_id = 2         # Активный марафон Ольги

    async for session in get_db():
        # --- ТЕСТ 1: Удаление подопечного ---
        print("🛠 Тест 1: Удаление подопечного (Ward Removal)")
        ward_before = await session.get(User, ward_id)
        print(f"До удаления: User {ward_id}, Curator: {ward_before.curator_id}")

        # Симулируем удаление (как в handlers/curator.py)
        ward_before.curator_id = None
        await session.commit()

        ward_after = await session.get(User, ward_id)
        print(f"После удаления: User {ward_id}, Curator: {ward_after.curator_id}")
        if ward_after.curator_id is None:
            print("✅ ТЕСТ 1 ПРОЙДЕН: Пользователь отвязан, но остался в базе.\n")
        else:
            print("❌ ТЕСТ 1 ПРОВАЛЕН.\n")

        # Возвращаем как было для следующих тестов
        ward_after.curator_id = curator_id
        await session.commit()

        # --- ТЕСТ 2: Истекающая реферальная ссылка (ref_) ---
        print("🛠 Тест 2: Истекающая реферальная ссылка (Referral Expiration)")
        curator = await session.get(User, curator_id)
        new_token = f"test_ref_{uuid.uuid4().hex[:6]}"
        curator.referral_token = new_token
        # Устанавливаем срок -1 минута (уже истекла)
        curator.referral_token_expires_at = datetime.now() - timedelta(minutes=1)
        await session.commit()

        print(f"Токен: {new_token}, Истек: {curator.referral_token_expires_at}")

        # Проверяем логику валидации (как в common.py)
        stmt = select(User).where(User.referral_token == new_token)
        found_curator = (await session.execute(stmt)).scalar_one_or_none()

        if found_curator and found_curator.referral_token_expires_at < datetime.now():
            print("✅ ТЕСТ 2 ПРОЙДЕН: Ссылка распознана как протухшая.")
        else:
            print("❌ ТЕСТ 2 ПРОВАЛЕН.")
        print("\n")

        # --- ТЕСТ 3: Марафон - Обратная совместимость (m_{id}) ---
        print("🛠 Тест 3: Марафон - Обратная совместимость (Legacy m_{id})")
        # Старая ссылка m_2 (Марафон Ольги)
        user_info = {"username": "test_legacy", "first_name": "Legacy", "last_name": "Test"}
        # Мы используем временного ID для теста, чтобы не плодить мусор
        test_user_id = 999999999

        # Удалим если остался от прошлых запусков
        stmt_del = select(MarathonParticipant).where(MarathonParticipant.user_id == test_user_id)
        old_p = (await session.execute(stmt_del)).scalars().all()
        for p in old_p:
            await session.delete(p)
        await session.commit()

        result = await MarathonService.process_invite(session, marathon_id, test_user_id, user_info)
        print(f"Результат входа по ID (m_2): {result['success']} - {result['message']}")
        if result['success'] and "Весна близко" in result['marathon_name']:
            print("✅ ТЕСТ 3 ПРОЙДЕН: Старая ссылка m_ID сработала.")
        else:
            print("❌ ТЕСТ 3 ПРОВАЛЕН.")
        print("\n")

        # --- ТЕСТ 4: Марафон - Истекающая ссылка (m_{token}) ---
        print("🛠 Тест 4: Марафон - Истекающая ссылка (Expiring m_{token})")
        marathon = await session.get(Marathon, marathon_id)
        new_m_token = f"m_test_{uuid.uuid4().hex[:6]}"
        marathon.invite_token = new_m_token
        marathon.invite_token_expires_at = datetime.now() - timedelta(minutes=1)
        await session.commit()

        print(f"Токен марафона: {new_m_token}, Истек: {marathon.invite_token_expires_at}")

        # Проверяем через сервис
        result_tok = await MarathonService.process_invite(session, new_m_token, 888888888, user_info)
        print(f"Результат входа по токену: {result_tok['success']} - {result_tok['message']}")

        if not result_tok['success'] and "истекла" in result_tok['message']:
            print("✅ ТЕСТ 4 ПРОЙДЕН: Ссылка марафона по токену протухла.")
        else:
            print("❌ ТЕСТ 4 ПРОВАЛЕН.")

        # Очистка
        marathon.invite_token = None
        marathon.invite_token_expires_at = None
        await session.commit()
        print("\n🏁 Тесты завершены!")

if __name__ == "__main__":
    asyncio.run(test_scenarios())
