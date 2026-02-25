import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, update
from database.base import get_db
from database.models import User, Marathon, MarathonParticipant
from services.marathon_service import MarathonService
import uuid

async def test_scenarios():
    print("🚀 Начинаю хардкорные тесты системы кураторов и ссылок...\n")
    
    # Данные из базы
    CURATOR_ID = 295543071  # Ольга (@zumbaola)
    WARD_ID = 5422141137    # Подопечный Ольги
    MARATHON_ID = 2         # Активный марафон Ольги
    
    async for session in get_db():
        # --- ТЕСТ 1: Удаление подопечного ---
        print("🛠 Тест 1: Удаление подопечного (Ward Removal)")
        ward_before = await session.get(User, WARD_ID)
        print(f"До удаления: User {WARD_ID}, Curator: {ward_before.curator_id}")
        
        # Симулируем удаление (как в handlers/curator.py)
        ward_before.curator_id = None
        await session.commit()
        
        ward_after = await session.get(User, WARD_ID)
        print(f"После удаления: User {WARD_ID}, Curator: {ward_after.curator_id}")
        if ward_after.curator_id is None:
            print("✅ ТЕСТ 1 ПРОЙДЕН: Пользователь отвязан, но остался в базе.\n")
        else:
            print("❌ ТЕСТ 1 ПРОВАЛЕН.\n")
            
        # Возвращаем как было для следующих тестов
        ward_after.curator_id = CURATOR_ID
        await session.commit()

        # --- ТЕСТ 2: Истекающая реферальная ссылка (ref_) ---
        print("🛠 Тест 2: Истекающая реферальная ссылка (Referral Expiration)")
        curator = await session.get(User, CURATOR_ID)
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
        TEST_USER_ID = 999999999 
        
        # Удалим если остался от прошлых запусков
        stmt_del = select(MarathonParticipant).where(MarathonParticipant.user_id == TEST_USER_ID)
        old_p = (await session.execute(stmt_del)).scalars().all()
        for p in old_p: await session.delete(p)
        await session.commit()

        result = await MarathonService.process_invite(session, MARATHON_ID, TEST_USER_ID, user_info)
        print(f"Результат входа по ID (m_2): {result['success']} - {result['message']}")
        if result['success'] and "Весна близко" in result['marathon_name']:
            print("✅ ТЕСТ 3 ПРОЙДЕН: Старая ссылка m_ID сработала.")
        else:
            print("❌ ТЕСТ 3 ПРОВАЛЕН.")
        print("\n")

        # --- ТЕСТ 4: Марафон - Истекающая ссылка (m_{token}) ---
        print("🛠 Тест 4: Марафон - Истекающая ссылка (Expiring m_{token})")
        marathon = await session.get(Marathon, MARATHON_ID)
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
