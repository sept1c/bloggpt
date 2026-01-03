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

# Create OpenAI client only if key exists
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class TopicIn(BaseModel):
    topic: str


def get_recent_news(topic: str, limit: int = 5) -> List[str]:
    """
    Returns a list of recent news titles by topic.
    Soft-fails: never raises on Currents errors (so Zapier won't break).
    """
    if not CURRENTS_API_KEY:
        return ["(CURRENTS_API_KEY не задан — новости не подтягиваем)"]

    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "language": "en",
        "keywords": topic,
        "apiKey": CURRENTS_API_KEY,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception:
        return ["(Currents недоступен: network/timeout)"]

    if r.status_code != 200:
        return [f"(Currents недоступен: {r.status_code})"]

    news = r.json().get("news", []) or []
    titles = [a.get("title", "").strip() for a in news if a.get("title")]
    return titles[:limit] if titles else ["Свежих новостей не найдено."]


def gen_post_text(topic: str) -> str:
    """
    Generates a Telegram post text using OpenAI.
    Raises HTTPException if OPENAI_API_KEY is missing (caller may fallback).
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

Не используй таблицы. Не добавляй лишние пояснения.
""".strip()

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.5,
    )

    text = completion.choices[0].message.content.strip()
    if not text:
        raise HTTPException(status_code=500, detail="Пустой ответ от модели")
    return text


def fallback_post(topic: str, reason: str) -> str:
    return (
        "Пост (fallback) ✅\n\n"
        f"Тема: {topic}\n\n"
        "Короткий чеклист:\n"
        "- Топливо / воздух / АКБ\n"
        "- Ошибки контроллера и датчики\n"
        "- Стартер / соленоид / пуск\n\n"
        f"Причина fallback: {reason}\n\n"
        "— auto via code\n"
        "#DER #ДГУ"
    )


@app.get("/")
def root():
    return {"message": "Service is running"}


@app.get("/heartbeat")
def heartbeat():
    return {"status": "OK"}

@app.get("/news-test")
def news_test(topic: str = Query("diesel generator")):
    news = get_recent_news(topic)
    return {
        "topic": topic,
        "count": len(news),
        "news": news
    }

# ✅ Main endpoint for Zapier (simple GET)
@app.get("/generate")
def generate(topic: str = Query("diesel generator troubleshooting")):
    try:
        text = gen_post_text(topic)
        return {"text": text}
    except Exception as e:
        # Never break Zapier: always return "text"
        reason = f"{type(e).__name__}: {str(e)[:180]}"
        return {"text": fallback_post(topic, reason)}


# ✅ Optional POST endpoint (like in lecturer project)
@app.post("/generate-post")
def generate_post(body: TopicIn):
    try:
        text = gen_post_text(body.topic)
        return {"text": text}
    except Exception as e:
        reason = f"{type(e).__name__}: {str(e)[:180]}"
        return {"text": fallback_post(body.topic, reason)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
