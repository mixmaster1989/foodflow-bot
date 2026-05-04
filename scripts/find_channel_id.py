
import asyncio
import aiohttp
import json
import os

TOKEN = os.environ.get("RECEPTION_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or ""

async def get_updates():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if not data["ok"]:
                print(f"Error: {data['description']}")
                return

            updates = data["result"]
            if not updates:
                print("No updates found. Try sending a message to the channel or adding/removing the bot.")
                return

            for update in updates:
                # Look for my_chat_member or channel_post
                if "my_chat_member" in update:
                    chat = update["my_chat_member"]["chat"]
                    if chat["type"] == "channel":
                        print(f"Found Channel ID (from my_chat_member): {chat['id']} - Name: {chat.get('title')}")
                
                if "channel_post" in update:
                    chat = update["channel_post"]["chat"]
                    print(f"Found Channel ID (from channel_post): {chat['id']} - Name: {chat.get('title')}")

if __name__ == "__main__":
    asyncio.run(get_updates())
