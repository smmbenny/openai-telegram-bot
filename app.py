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

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code != 200:
        print(f"❌ Ошибка отправки в Telegram: {response.text}")

def ask_openai(prompt, user_id="debug-user"):
    try:
        print("👉 Запрос от пользователя:", prompt)

        # Создание thread
        thread_response = requests.post("https://api.openai.com/v1/threads", headers=HEADERS)
        thread_data = thread_response.json()
        print("🧵 Thread создан:", thread_data)

        if "id" not in thread_data:
            return f"❌ Ошибка при создании thread: {thread_data}"

        thread_id = thread_data["id"]

        # Отправка сообщения
        message_response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/messages",
            headers=HEADERS,
            json={"role": "user", "content": prompt}
        )
        message_data = message_response.json()
        print("✉️ Сообщение отправлено:", message_data)

        if message_response.status_code != 200:
            return f"❌ Ошибка отправки сообщения: {message_data}"

        # Принудительно запускаем file_search
        run_response = requests.post(
            f"https://api.openai.com/v1/threads/{thread_id}/runs",
            headers=HEADERS,
            json={
                "assistant_id": ASSISTANT_ID,
                "instructions": "Ты консультант по услугам Benefitsar. Всегда используй знания из подключённых документов для ответов.",
                "tool_resources": {
                    "file_search": {
                        "vector_store_ids": [VECTOR_STORE_ID]
                    }
                },
                "tool_choice": "file_search"
            }
        )
        run_data = run_response.json()
        print("🏃 Запуск run:", run_data)

        # 🔍 Логируем наличие required_action
        if "required_action" not in run_data:
            print("⚠️ file_search НЕ активировался — required_action отсутствует")
        else:
            print("✅ file_search активирован:", run_data["required_action"])

        if "id" not in run_data:
            return f"❌ Ошибка запуска run: {run_data}"

        run_id = run_data["id"]

        # Ожидание завершения run
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
    return "Bot is running with Assistants API v2 and forced file_search.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
