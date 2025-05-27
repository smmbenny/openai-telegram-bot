import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = "asst_wwnwUQESgFERUYhFsEA9Ck0T"
ADMIN_USER_ID = 7346303154  # ID @iSMM02

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

# Память: user_id → thread_id
user_threads = {}
known_users = set()  # Для отслеживания новых пользователей

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code != 200:
        print(f"❌ Ошибка отправки в Telegram: {response.text}")

def get_or_create_thread(user_id):
    if user_id in user_threads:
        return user_threads[user_id]

    response = requests.post("https://api.openai.com/v1/threads", headers=HEADERS)
    data = response.json()
    if "id" not in data:
        raise Exception(f"❌ Ошибка создания thread: {data}")
    thread_id = data["id"]
    user_threads[user_id] = thread_id
    return thread_id

def notify_admin_if_new_user(user_data):
    user_id = user_data["id"]
    if user_id not in known_users:
        known_users.add(user_id)

        first_name = user_data.get("first_name", "Без имени")
        username = user_data.get("username", "—")
        msg = (
            f"🆕 Новый пользователь в @ai_ben_bot:\n"
            f"ID: {user_id}\n"
            f"Имя: {first_name}\n"
            f"Username: @{username}" if username != "—" else f"Username: —"
        )
        send_message(ADMIN_USER_ID, msg)

def ask_openai(prompt, user_id="debug-user"):
    try:
        thread_id = get_or_create_thread(user_id)

        requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS,
            json={"role": "user", "content": prompt}
        )

        run = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=HEADERS,
            json={
                "assistant_id": ASSISTANT_ID,
                "instructions": (
                    "Ты ассистент сервиса Benefitsar. Используй только знания из подключённых файлов. "
                    "Если информации нет — прямо скажи об этом."
                )
            }
        ).json()

        if "id" not in run:
            return f"❌ Ошибка запуска run: {run}"
        run_id = run["id"]

        while True:
            status = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=HEADERS
            ).json()
            if status["status"] == "completed":
                break
            elif status["status"] == "failed":
                return f"❌ Run завершился с ошибкой: {status}"
            time.sleep(1)

        response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS
        ).json()

        return response["data"][0]["content"][0]["text"]["value"]

    except Exception as e:
        return f"❌ OpenAI API error: {e}"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    message = data.get("message")
    if not message:
        return {"ok": True}

    user_data = message["from"]
    text = message.get("text")
    if not text:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    user_id = user_data["id"]

    try:
        notify_admin_if_new_user(user_data)
        reply = ask_openai(text, user_id)
        send_message(chat_id, reply)
    except Exception as e:
        send_message(chat_id, f"Произошла ошибка. {e}")
        print(f"❌ Ошибка в webhook: {e}")

    return {"ok": True}

@app.route("/", methods=["GET"])
def home():
    return "Bot is running with Assistants API v2 and admin notification.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
