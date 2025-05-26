import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4-1106-preview"  # Это GPT-4.1 через API

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def ask_openai(prompt):
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
        json=json_data
    )
    return response.json()["choices"][0]["message"]["content"]

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

