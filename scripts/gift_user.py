import sqlite3
import datetime
import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv('/home/user1/foodflow-bot_new/.env')
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    print('BOT_TOKEN not found')
    exit(1)

conn = sqlite3.connect('/home/user1/foodflow-bot_new/foodflow.db')
cursor = conn.cursor()

user_id = 7108317408
now = datetime.datetime.now()
expires = now + datetime.timedelta(days=3)

cursor.execute('UPDATE users SET is_premium=1 WHERE id=?', (user_id,))
cursor.execute('SELECT id FROM subscriptions WHERE user_id=?', (user_id,))
row = cursor.fetchone()
if row:
    cursor.execute('UPDATE subscriptions SET tier="pro", starts_at=?, expires_at=?, is_active=1, payment_source="admin_grant" WHERE id=?', (now, expires, row[0]))
else:
    cursor.execute('INSERT INTO subscriptions (user_id, tier, starts_at, expires_at, is_active, payment_source) VALUES (?, "pro", ?, ?, 1, "admin_grant")', (user_id, now, expires))
conn.commit()
conn.close()
print('DB updated for user', user_id)

text = 'Привет, Андрей! 👋 Добро пожаловать в FoodFlow — твой умный ИИ-дневник питания! 🍏\n\nВ качестве приветственного бонуса я дарю тебе <b>3 ДНЯ ТАРИФА PRO</b>! 🎁\n\nЧто теперь можно делать:\n📸 Отправлять мне <b>фото еды</b> (а я сам оценю КБЖУ и вес)\n🎤 Записывать приемы пищи <b>голосовыми сообщениями</b>\n🧾 <b>Сканировать магазинные чеки</b> и ценники\n\nИспытай магию ИИ прямо сейчас: просто отправь мне фото своего перекуса или надиктуй голосом, что съел. Приятного пользования! ✨'

url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
data = json.dumps({'chat_id': user_id, 'text': text, 'parse_mode': 'HTML'}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as f:
        print('Telegram response:', f.read().decode('utf-8'))
        print('SUCCESS')
except Exception as e:
    print('Error sending message:', e)
