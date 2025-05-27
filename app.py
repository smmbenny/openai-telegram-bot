import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = "asst_wwnwUQESgFERUYhFsEA9Ck0T"

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "assistants=v2"
}

# Сохраняем thread_id на пользователя
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

    response = requests.post("https://api.openai.com/v1/threads", headers=HEADERS)
    data = response.json()
    print("🧵 Thread создан:", data)

    if "id" not in data:
        raise Exception(f"❌ Ошибка создания thread: {data}")

    thread_id = data["id"]
    user_threads[user_id] = thread_id
    return thread_id

def ask_openai(prompt, user_id="debug-user"):
    try:
        print(f"👉 Запрос от пользователя {user_id}: {prompt}")
        thread_id = get_or_create_thread(user_id)

        # Отправка сообщения
        msg = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS,
            json={"role": "user", "content": prompt}
        ).json()
        print("✉️ Сообщение:", msg)

        # Запуск run
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
        print("🏃 Запуск run:", run)

        if "id" not in run:
            return f"❌ Ошибка запуска run: {run}"

        run_id = run["id"]

        # Ожидание завершения run
        while True:
            status = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=HEADERS
            ).json()
            print("⏳ Статус:", status)
            if status["status"] == "completed":
                break
            elif status["status"] == "failed":
                return f"❌ Ошибка run: {status}"
            time.sleep(1)

        # Получение ответа
        response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS
        ).json()
        print("📬 Ответ OpenAI:", response)

        return response["data"][0]["content"][0]["text"]["value"]

    except Exception as e:
        print(f"❌ Ошибка в ask_openai: {e}")
        return f"Произошла ошибка: {e}"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Входящий запрос:", data)

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
        send_message(chat_id, f"Произошла ошибка. {e}")
        print(f"❌ Ошибка в webhook:
