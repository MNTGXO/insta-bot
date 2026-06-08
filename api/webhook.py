import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ENDPOINT = "https://instagram-downloader.mn-bots.workers.dev/"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def process_message(chat_id, text):
    match = re.search(r"(https?://(?:www\.)?instagram\.com/[^\s]+)", text)
    if not match:
        return

    instagram_url = match.group(1)
    
    # 1. Send status placeholder
    status_msg_id = None
    try:
        status_res = requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": "🔎 *Processing link... Please wait.*",
            "parse_mode": "Markdown"
        }).json()
        status_msg_id = status_res.get("result", {}).get("message_id")
    except Exception:
        pass

    try:
        # 2. Query worker endpoint
        response = requests.get(API_ENDPOINT, params={"url": instagram_url}, timeout=30)
        data = response.json()

        if not data.get("success") or not data.get("media"):
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ *Error:* Could not extract media or content is private.report in @mnbots_support"
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

        # 4. Delete progress status
        if status_msg_id:
            requests.post(f"{TELEGRAM_API}/deleteMessage", json={"chat_id": chat_id, "message_id": status_msg_id})

    except Exception:
        if status_msg_id:
            requests.post(f"{TELEGRAM_API}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": status_msg_id,
                "text": "❌ *An operational error occurred while transferring media.*"
            })

@app.route('/', methods=['POST'])
def webhook():
    payload = request.get_json(silent=True) or {}
    
    if "message" in payload:
        message = payload["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text.startswith("/start"):
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": "👋 **Send me any public Instagram link and I'll download it instantly!.Join @mnbots**",
                "parse_mode": "Markdown"
            })
        elif text:
            process_message(chat_id, text)

    return jsonify({"status": "ok"}), 200

@app.route('/', methods=['GET'])
def index():
    return "Bot is running fine! powered by mnbots", 200
