import os
from typing import List

import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from openai import OpenAI

app = FastAPI()

# ENV
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")

# OpenAI client (создаём только если ключ есть)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class TopicIn(BaseModel):
    topic: str


def get_recent_news(topic: str, limit: int = 5) -> List[str]:
    """
    Возвращает список заголовков последних новостей по теме.
    """
    if not CURRENTS_API_KEY:
        return ["(CURRENTS_API_KEY не задан — новости не подтягиваем)"]

    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "language": "en",
        "keywords": topic,
        "apiKey": CURRENTS_API_KEY,
    }

    r = requests.get(url, params=params, timeout=15)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Currents API error: {r.text}")

    news = r.json().get("news", []) or []
    titles = [a.get("title", "").strip() for a in news if a.get("title")]
    return titles[:limit] if titles else ["Свежих новостей не найдено."]


def gen_post_text(topic: str) -> str:
    """
    Генерирует готовый текст Telegram-поста.
    """
    if not client:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY не задан")

    titles = get_recent_news(topic)
    news_block = "\n".join([f"- {t}" for t in titles])

    prompt = f"""
Ты редактор Telegram-канала (короткие практичные посты).
Сгенерируй 1 пост на русском по теме: "{topic}".

Учитывай свежие заголовки (если релевантно):
{news_block}

Формат:
1) Заголовок (до 70 символов)
2) 5–7 строк текста (без воды)
3) 3 буллета "чеклист"
4) В конце подпись: — auto via code
5) Хэштеги: #DER #ДГУ

Не используй markdown-таблицы. Не добавляй лишние пояснения.
""".strip()

    # Responses API (актуальный стиль) :contentReference[oaicite:2]{index=2}
    resp = client.responses.create(
        model="gpt-4o-mini",  # модель актуальна :contentReference[oaicite:3]{index=3}
        input=[{"role": "user", "content": prompt}],
        max_output_tokens=500,
    )

    # Удобный текстовый вывод
    text = resp.output_text.strip()
    if not text:
        raise HTTPException(status_code=500, detail="Пустой ответ модели")

    return text


@app.get("/")
def root():
    return {"message": "Service is running"}


@app.get("/heartbeat")
def heartbeat():
    return {"status": "OK"}


# ✅ Удобно для Zapier: просто GET запрос
@app.get("/generate")
def generate(topic: str = Query("diesel generator troubleshooting")):
    text = gen_post_text(topic)
    return {"text": text}


# ✅ Если хочешь как в лекции POST с JSON
@app.post("/generate-post")
def generate_post(body: TopicIn):
    text = gen_post_text(body.topic)
    return {"text": text}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
