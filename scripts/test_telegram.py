import asyncio
import os
from dotenv import load_dotenv
import httpx

# Load environment variables from .env file
load_dotenv()

async def send_test_notification():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
        return

    print(f"🚀 Sending test message to Chat ID: {chat_id}...")
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "✅ <b>Test Notification Successful!</b>\n\nYour Kakarot Trading Bot is now connected to Telegram. You will receive alerts for:\n• System Startup/Shutdown\n• Market Session changes\n• Token Expiry warnings\n• WebSocket status",
        "parse_mode": "HTML"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            if response.status_code == 200:
                print("✅ Success! Check your Telegram.")
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(send_test_notification())
