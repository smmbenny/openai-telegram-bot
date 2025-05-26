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

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def ask_openai(prompt):
    try:
        # 1. Создать thread
        thread = requests.post("https://api.openai.com/v1/threads", headers=HEADERS).json()
        thread_id = thread["id"]

        # 2. Отправить сообщение в thread
        requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS,
            json={"role": "user", "content": prompt}
        )

        # 3. Запустить ассистента
        run = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=HEADERS,
            json={"assistant_id": ASSISTANT_ID}
        ).json()
        run_id = run["id"]

        # 4. Подождать выполнения run
        while True:
            run_status = requests.get(
                f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
                headers=HEADERS
            ).json()
            if run_status["status"] == "completed":
                break
            elif run_status["status"] == "failed":
                return "Ассистент не смог обработать запрос."
            time.sleep(1)

        # 5. Получить ответ
        messages = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS
        ).json()["data"]

        last_message = messages[0]["content"][0]["text"]["value"]
        return last_message

    except Exception as e:
        print(f"❌ Ошибка Assistants API: {e}")
        return "Произошла ошибка при обращении к ассистенту."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Пришёл запрос от Telegram:", data)

    message = data.get("message")
    if not message:
        return {"ok": True}

    text = message.get("text")
    if not text:
        return {"ok": True}

    chat_id = message["chat"]["id"]

    try:
        reply = ask_openai(text)
        send_message(chat_id, reply)
    except Exception as e:
        print(f"❌ Ошибка обработки: {e}")
        send_message(chat_id, "Произошла ошибка. Попробуйте позже.")

    return {"ok": True}

@app.route("/", methods=["GET"])
def home():
    return "Bot is running via Assistants API", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
