from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route("/generate", methods=["GET"])
def generate():
    text = (
        "Пост сгенерирован через код 🚀\n\n"
        "Это тестовый пост для домашнего задания.\n"
        "Источник: Flask + деплой.\n\n"
        f"Время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "— auto via code"
    )
    return jsonify({"text": text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
