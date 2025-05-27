import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = "asst_wwnwUQESgFERUYhFsEA9Ck0T"
VECTOR_STORE_ID = "vs_683409c567248191b68fcd34617b51c9"

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

# Память: user_id → thread_id
user_threads = {}

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code != 200:
        print(f"❌ Ошибка отправки в Telegram: {response.text}")

def get_or_create_thread(user_id):
    if user_id in user_threads:
        print(f"📌 Используем thread_id для user_id {user_id}")
        return user_threads[user_id]

    # Создание нового thread
    thread_response = requests.post("https://api.openai.com/v1/threads", headers=HEADERS)
    thread_data = thread_response.json()
    print("🧵 Thread создан:", thread_data)

    if "id" not in thread_data:
        raise Exception(f"❌ Ошибка создания thread: {thread_data}")

    thread_id = thread_data["id"]
    user_threads[user_id] = thread_id

    # Привязка Vector Store к thread
    attach_response = requests.post(
        f"https://api.openai.com/v1/threads/{thread_id}/attachments",
        headers=HEADERS,
        json={"vector_store_id": VECTOR_STORE_ID}
    )
    attach_data = attach_response.json()
    print("📎 Vector Store привязан:", attach_data)

    return thread_id

def ask_openai(prompt, user_id="debug-user"):
    try:
        print(f"👉 Запрос от пользователя {user_id}: {prompt}")
        thread_id = get_or_create_thread(user_id)

        # Отправка сообщения в thread
        message_response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS,
            json={"role": "user", "content": prompt}
        )
        message_data = message_response.json()
        print("✉️ Сообщение отправлено:", message_data)

        if message_response.status_code != 200:
            return f"❌ Ошибка отправки сообщения: {message_data}"

        # Запуск ассистента (без tool_choice)
        run_response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=HEADERS,
            json={"assistant_id": ASSISTANT_ID}
        )
        run_data = run_response.json()
        print("🏃 Запуск run:", run_data)

        if "id" not in run_data:
            return f"❌ Ошибка запуска run: {run_data}"

        run_id = run_data["id"]

        # Ожидание завершения
        while True:
            status_response = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=HEADERS
            )
            status_data = status_response.json()
            print("⏳ Статус run:", status_data)

            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                return f"❌ Run завершился с ошибкой: {status_data}"
            time.sleep(1)

        # Получение ответа
        messages_response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS
        )
        messages_data = messages_response.json()
        print("📬 Ответ OpenAI:", messages_data)

        last_message = messages_data["data"][0]["content"][0]["text"]["value"]
        return last_message

    except Exception as e:
        print(f"❌ Ошибка в ask_openai: {e}")
        return f"❌ OpenAI API error: {e}"

@app.route("/webhook", methods=["POST"])
def webhook():
    print("📥 Входящий запрос от Telegram")
    data = request.get_json()
    print("📩 JSON:", data)

    message = data.get("message")
    if not message:
        return {"ok": True}

    text = message.get("text")
    if not text:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]

    try:
        reply = ask_openai(text, user_id)
        send_message(chat_id, reply)
    except Exception as e:
        print(f"❌ Ошибка в webhook:", e)
        send_message(chat_id, f"Произошла ошибка. {e}")

    return {"ok": True}

@app.route("/", methods=["GET"])
def home():
    return "Bot is running with Assistants API v2, memory, and Vector Store attachment.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
