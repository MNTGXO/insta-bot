import os
import re
import json
import requests
from http.server import BaseHTTPRequestHandler

# Fetch Token from Vercel Environment Variables safely
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ENDPOINT = "https://instagram-downloader.mn-bots.workers.dev/"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def process_message(chat_id, text):
    """Parses text, fetches from extraction API, and sends files to Telegram synchronously."""
    match = re.search(r"(https?://(?:www\.)?instagram\.com/[^\s]+)", text)
    if not match:
        return

    instagram_url = match.group(1)
    
    # 1. Send initial progress alert
    try:
        status_res = requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🔎 *Processing link... Please wait.*",
            "parse_mode": "Markdown"
        }).json()
        status_msg_id = status_res.get("result", {}).get("message_id")
    except Exception:
        status_msg_id = None

    try:
        # 2. Extract media metadata from your worker backend
        response = requests.get(API_ENDPOINT, params={"url": instagram_url}, timeout=30)
        data = response.json()

        if not data.get("success") or not data.get("media"):
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ *Error:* Could not extract media or content is private."
            })
            return

        # 3. Direct upload stream loop
        for item in data["media"]:
            media_url = item.get("url")
            media_type = item.get("type")

            if not media_url:
                continue

            if media_type == "video":
                requests.post(f"{TELEGRAM_API}/sendVideo", json={"chat_id": chat_id, "video": media_url})
            elif media_type == "image":
                requests.post(f"{TELEGRAM_API}/sendPhoto", json={"chat_id": chat_id, "photo": media_url})

        # 4. Remove tracking status placeholder
        if status_msg_id:
            requests.post(f"{TELEGRAM_API}/deleteMessage", json={"chat_id": chat_id, "message_id": status_msg_id})

    except Exception:
        if status_msg_id:
            requests.post(f"{TELEGRAM_API}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": status_msg_id,
                "text": "❌ *An operational error occurred while transferring media.*"
            })

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Processes the clean incoming JSON webhook transmission."""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
            if "message" in payload and "text" in payload["message"]:
                chat_id = payload["message"]["chat"]["id"]
                text = payload["message"]["text"]
                
                if text.startswith("/start"):
                    requests.post(f"{TELEGRAM_API}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "👋 **Send me any public Instagram link and I'll extract it instantly!**",
                        "parse_mode": "Markdown"
                    })
                else:
                    process_message(chat_id, text)
                    
        except Exception as e:
            print(f"Execution payload error: {e}")

        # Instantly return 200 OK to keep the serverless pipeline flowing smoothly
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
