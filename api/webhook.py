import re
import json
import httpx
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Best practice: Set this in Vercel Environment Variables
API_ENDPOINT = "https://instagram-downloader.mn-bots.workers.dev/"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def process_message(chat_id, text):
    """Parses incoming text, requests media from the API, and sends it back."""
    match = re.search(r"(https?://(?:www\.)?instagram\.com/[^\s]+)", text)
    if not match:
        return

    instagram_url = match.group(1)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Send status message to user
        status_res = await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🔎 *Processing link... Please wait.*",
            "parse_mode": "Markdown"
        })
        status_msg_id = status_res.json().get("result", {}).get("message_id")

        try:
            # 2. Query your worker extraction endpoint
            response = await client.get(API_ENDPOINT, params={"url": instagram_url})
            data = response.json()

            if not data.get("success") or not data.get("media"):
                await client.post(f"{TELEGRAM_API}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ *Error:* Could not extract media from this URL."
                })
                return

            # 3. Loop and natively send out assets
            for item in data["media"]:
                media_url = item.get("url")
                media_type = item.get("type")

                if not media_url:
                    continue

                if media_type == "video":
                    await client.post(f"{TELEGRAM_API}/sendVideo", json={"chat_id": chat_id, "video": media_url})
                elif media_type == "image":
                    await client.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": chat_id, "photo": media_url})

            # 4. Clean up status message
            if status_msg_id:
                await client.post(f"{TELEGRAM_API}/deleteMessage", json={"chat_id": chat_id, "message_id": status_msg_id})

        except Exception:
            if status_msg_id:
                await client.post(f"{TELEGRAM_API}/editMessageText", json={
                    "chat_id": chat_id,
                    "message_id": status_msg_id,
                    "text": "❌ *An error occurred while downloading.*"
                })

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handles the incoming POST request webhook sent by Telegram."""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
            if "message" in payload and "text" in payload["message"]:
                chat_id = payload["message"]["chat"]["id"]
                text = payload["message"]["text"]
                
                # Handle /start command safely
                if text.startswith("/start"):
                    import asyncio
                    asyncio.run(httpx.AsyncClient().post(f"{TELEGRAM_API}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "👋 Send me any public Instagram link and I'll fetch it instantly!"
                    }))
                else:
                    import asyncio
                    asyncio.run(process_message(chat_id, text))
                    
        except Exception as e:
            print(f"Error executing function payload: {e}")

        # Always return 200 OK immediately to Telegram so it doesn't retry spamming the webhook
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                  
