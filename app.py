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
    "Content-Type": "application/json"
}

# Память в оперативной памяти (в будущем можно заменить на БД)
user_threads = {}

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def ask_openai(prompt, chat_id):
    try:
        # Получаем или создаём thread_id для пользователя
        thread_id = user_threads.get(chat_id)

        if not thread_id:
            thread_response = requests.post("https://api.openai.com/v1/threads", headers=HEADERS)
            thread_id = thread_response.json()["id"]
            user_threads[chat_id] = thread_id  # сохраняем thread_id в памяти
            print(f"🧠 Новый thread_id для {chat_id}: {thread_id}")
        else:
            print(f"📌 Используем thread_id из памяти: {thread_id}")

        # Добавляем сообщение
        requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS,
            json={"role": "user", "content": prompt}
        )

        # Запускаем ассистента
        run_response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=HEADERS,
            json={"assistant_id": ASSISTANT_ID}
        ).json()

        run_id = run_response["id"]

        # Ждём завершения run
        while True:
            status_response = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=HEADERS
            ).json()
            if status_response["status"] == "completed":
                break
            elif status_response["status"] == "failed":
                return "Ассистент не смог обработать запрос."
            time.sleep(1)

        # Получаем последнее сообщение
        messages_response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS
        ).json()
        last_message = messages_response["data"][0]["content"][0]["text"]["value"]

        return last_message

    except Exception as e:
        print(f"❌ Ошибка Assistants API: {e}")
        return "Произошла ошибка при обращении к ассистенту."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Получен запрос:", data)

    message = data.get("message")
    if not message:
        return {"ok": True}

    text = message.get("text")
    if not text:
        return {"ok": True}

    chat_id = message["chat"]["id"]

    try:
        reply = ask_openai(text, chat_id)
        send_message(chat_id, reply)
    except Exception as e:
        print(f"❌ Ошибка обработки запроса: {e}")
        send_message(chat_id, "Произошла ошибка. Попробуйте ещё раз.")

    return {"ok": True}

@app.route("/", methods=["GET"])
def home():
    return "Bot is running with memory via Assistants API", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
