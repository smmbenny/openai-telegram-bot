import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4-1106-preview"  # GPT-4.1 через OpenAI API

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def ask_openai(prompt):
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        json_data = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты ассистент сервиса Benefitsar. Отвечай кратко, деловым тоном. Помогай выбрать услугу, объясняй акции, отрабатывай возражения."
                },
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=json_data,
            timeout=10  # Ограничение по времени ответа
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ Ошибка при запросе к OpenAI: {e}")
        return "Произошла ошибка при обращении к ассистенту. Попробуйте позже."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Пришёл запрос от Telegram:", data)

    message = data.get("message")
    if not message:
        print("❌ Нет поля 'message'")
        return {"ok": True}

    text = message.get("text")
    if not text:
        print("❌ Нет текста в сообщении (возможно, стикер или фото)")
        return {"ok": True}

    chat_id = message["chat"]["id"]
    print(f"💬 Запрос: {text}")

    try:
        reply = ask_openai(text)
        print(f"🤖 Ответ: {reply}")
        send_message(chat_id, reply)
    except Exception as e:
        print(f"❌ Ошибка при обработке запроса: {e}")
        send_message(chat_id, "Произошла ошибка. Попробуйте ещё раз позже.")

    return {"ok": True}

@app.route("/", methods=["GET"])
def home():
    return "Bot is running with GPT-4.1", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
