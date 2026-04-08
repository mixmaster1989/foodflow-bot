import sys
import os
sys.path.append(os.getcwd())

import asyncio
import aiohttp
from config import settings

PILOT_USERS = {
    33587682: "Василий",
    295543071: "Ольга"
}

MESSAGE_TEMPLATE = """
🌟 <b>Добро пожаловать в пилот KBJU Core!</b>

Мы запустили новое ядро расчёта. Теперь, если продукт есть в нашем "золотом кэше", вы увидите пометку <b>💎 [ЭТАЛОН]</b>. Это значит, данные на 100% точны и проверены.

<b>Ваши новые возможности:</b>
📥 <code>/etalon</code> — посмотреть весь список эталонных продуктов.

<b>Как это работает:</b>
Просто пишите еду как обычно (например, <i>"банан 200г"</i>). Если это эталон — расчет будет мгновенным.

<b>Обратная связь:</b>
Если заметите странные цифры или ошибку в эталоне — пишите сразу <b>Игорю (@igor_tg_handle_placeholder)</b>, он в курсе и на связи!

Спасибо, что помогаете нам стать лучше! 🚀
"""

async def send_message(user_id, name):
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    text = f"Привет, {name}!" + MESSAGE_TEMPLATE
    
    payload = {
        "chat_id": user_id,
        "text": text,
        "parse_mode": "HTML"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    print(f"✅ Message sent to {name} ({user_id})")
                else:
                    data = await response.json()
                    print(f"❌ Failed to send to {name} ({user_id}): {data}")
        except Exception as e:
            print(f"❌ Error sending to {name}: {e}")

async def main():
    tasks = [send_message(uid, name) for uid, name in PILOT_USERS.items()]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
