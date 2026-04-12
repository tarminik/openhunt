"""LLM-powered cover letter generation and questionnaire answering."""

import hashlib
import json

import click
from openai import OpenAI, OpenAIError

from openhunt.config import get_llm_config

PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
}

CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"

SYSTEM_PROMPT = """\
Напиши сопроводительное письмо на русском языке для отклика на вакансию.

Структура:
1. Приветствие и кто ты + на какую позицию откликаешься.
2. Почему заинтересовала именно эта вакансия — упомяни конкретную деталь: задачу, продукт, стек или домен.
3. Релевантный опыт — 2-3 пункта с цифрами из резюме (latency, RPS, проценты, сроки). Только то, что совпадает с вакансией.
4. Чем будешь полезен — конкретно, в привязке к задачам из вакансии.

Правила:
- Формула: Интерес → Релевантность → Цифры → Польза.
- НЕ пересказывай резюме целиком. Выбери только релевантные достижения.
- Используй цифры и факты, не общие слова.
- Без шаблонных фраз: «с большим интересом», «стрессоустойчивый», «готов оперативно включиться».
- Компактно — не больше 8-10 строк. Достижения можно оформить списком.
- Пиши от первого лица."""

_client: OpenAI | None = None
_client_config_key: tuple | None = None


def reset_client() -> None:
    """Reset the cached OpenAI client, forcing recreation on next call."""
    global _client, _client_config_key
    _client = None
    _client_config_key = None


def _get_client() -> OpenAI | None:
    """Return a cached OpenAI client, recreating only when config changes."""
    global _client, _client_config_key

    llm_config = get_llm_config()
    if not llm_config:
        return None

    provider = llm_config.get("provider", "custom")

    if provider == "codex":
        return _get_codex_client()

    base_url = llm_config.get("base_url") or PROVIDER_URLS.get(provider)
    if not base_url:
        click.echo("  ! LLM: не указан base_url для кастомного провайдера.")
        return None

    config_key = (base_url, llm_config["api_key"])
    if _client is not None and _client_config_key == config_key:
        return _client

    try:
        _client = OpenAI(base_url=base_url, api_key=llm_config["api_key"])
        _client_config_key = config_key
        return _client
    except Exception as e:
        click.echo(f"  ! LLM ошибка: {e}")
        return None


def _get_codex_client() -> OpenAI | None:
    """Return an OpenAI client configured for Codex with a valid OAuth token."""
    global _client, _client_config_key

    from openhunt.auth import get_valid_codex_token

    token = get_valid_codex_token()
    if not token:
        click.echo("  ! Codex: нет валидного токена. Выполните 'openhunt codex login'.")
        return None

    # Token changes on refresh, so always check (full hash, not prefix — JWT prefixes are stable)
    config_key = ("codex", hashlib.sha256(token.encode()).hexdigest())
    if _client is not None and _client_config_key == config_key:
        return _client

    try:
        _client = OpenAI(base_url=CODEX_BASE_URL, api_key=token)
        _client_config_key = config_key
        return _client
    except Exception as e:
        click.echo(f"  ! Codex ошибка: {e}")
        return None


def _build_user_message(
    vacancy_title: str,
    vacancy_text: str,
    profile_text: str = "",
    user_name: str = "",
) -> str:
    parts = []
    if user_name:
        parts.append(f"Имя соискателя: {user_name}")
    if profile_text:
        parts.append(f"Профиль соискателя:\n{profile_text}")
    parts.append(f"Вакансия: {vacancy_title}\n\n{vacancy_text}")
    return "\n\n".join(parts)


def _generate_via_chat_completions(
    client: OpenAI, model: str, user_message: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> str | None:
    """Generate using the standard chat completions API."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1024,
        temperature=0.7,
    )
    if not response.choices:
        return None
    content = response.choices[0].message.content
    return content.strip() if content else None


def _generate_via_responses(
    client: OpenAI, model: str, user_message: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> str | None:
    """Generate using the OpenAI Responses API (Codex)."""
    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=[{"role": "user", "content": user_message}],
        max_output_tokens=1024,
        temperature=0.7,
        store=False,
    )
    # Responses API returns output items
    for item in response.output:
        if item.type == "message":
            for content in item.content:
                if content.type == "output_text":
                    return content.text.strip()
    return None


def generate_cover_letter(
    vacancy_title: str,
    vacancy_text: str,
    profile_text: str = "",
    user_name: str = "",
) -> str | None:
    """Generate a cover letter using the configured LLM provider.

    Returns the generated text, or None on any error (caller should fall back to template).
    """
    llm_config = get_llm_config()
    if not llm_config:
        return None

    client = _get_client()
    if not client:
        return None

    try:
        user_message = _build_user_message(
            vacancy_title, vacancy_text, profile_text, user_name,
        )
        provider = llm_config.get("provider", "custom")
        model = llm_config["model"]

        if provider == "codex":
            return _generate_via_responses(client, model, user_message)
        return _generate_via_chat_completions(client, model, user_message)
    except (OpenAIError, Exception) as e:
        click.echo(f"  ! LLM ошибка: {e}")
        return None


# --- Questionnaire answering ---

QUESTIONNAIRE_SYSTEM_PROMPT = """\
Ты помощник соискателя. Тебе дан профиль соискателя и список вопросов от работодателей.

Для каждого вопроса определи:
1. Можешь ли ты ответить на основе профиля и здравого смысла (профессиональные, фактические вопросы).
2. Или это требует личного решения соискателя (зарплата, переезд, дата выхода, личные обстоятельства).

Примеры вопросов, которые ты МОЖЕШЬ ответить:
- "Какие HTTP-методы вы знаете?" — профессиональный факт
- "Опыт работы с Python?" — есть в профиле
- "Какой формат работы предпочитаете?" — если в профиле указано

Примеры вопросов, которые НЕ МОЖЕШЬ (needs_human=true):
- "Ожидания по зарплате?" — личное решение
- "Когда можете приступить к работе?" — зависит от обстоятельств
- "Готовы ли к командировкам?" — личный выбор

Формат ответа — строго JSON массив:
[
  {
    "id": "q_...",
    "needs_human": false,
    "answer": {"text": "ваш ответ"}
  },
  {
    "id": "q_...",
    "needs_human": true,
    "answer": null
  }
]

Правила для ответов:
- text: {"text": "ваш ответ"}
- single_choice / single_choice_other: {"option": "текст опции из списка"}
- multi_choice / multi_choice_other: {"options": ["опция1", "опция2"]}
- Для *_other типов, если нужен свободный текст: {"option": "__OTHER__", "free_text": "..."}
- Выбирай ТОЛЬКО из указанных опций. Не выдумывай опции.
- Отвечай кратко, профессионально, от первого лица.
- Если вопрос с выбором и ни одна опция не подходит по профилю — needs_human=true.
- Верни ТОЛЬКО JSON массив, без markdown-обёрток."""


def _build_questions_message(
    questions: list[dict],
    profile_text: str = "",
    user_name: str = "",
) -> str:
    """Build the user message for question answering."""
    parts = []
    if user_name:
        parts.append(f"Имя соискателя: {user_name}")
    if profile_text:
        parts.append(f"Профиль соискателя:\n{profile_text}")

    parts.append("Вопросы:")
    for q in questions:
        entry = f"\nID: {q['id']}\nТип: {q['type']}\nВопрос: {q['text']}"
        opts = q.get("options")
        if opts:
            labels = ", ".join(o["text"] for o in opts)
            entry += f"\nВарианты: {labels}"
        parts.append(entry)

    return "\n\n".join(parts)


def _parse_answers_response(raw: str, questions: list[dict]) -> list[dict]:
    """Parse the LLM JSON response, falling back to needs_human on errors."""
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return [{"id": q["id"], "needs_human": True, "answer": None} for q in questions]

    if not isinstance(items, list):
        return [{"id": q["id"], "needs_human": True, "answer": None} for q in questions]

    # Index by id for lookup
    by_id = {item["id"]: item for item in items if isinstance(item, dict) and "id" in item}
    results = []
    for q in questions:
        item = by_id.get(q["id"])
        if item and not item.get("needs_human") and item.get("answer") is not None:
            results.append({
                "id": q["id"],
                "needs_human": False,
                "answer": item["answer"],
            })
        else:
            results.append({"id": q["id"], "needs_human": True, "answer": None})
    return results


def answer_questions(
    questions: list[dict],
    profile_text: str = "",
    user_name: str = "",
) -> list[dict]:
    """Classify and answer pending questions using LLM.

    Returns a list of dicts: [{"id": "q_...", "needs_human": bool, "answer": dict | None}].
    Questions the LLM cannot answer get needs_human=True, answer=None.
    On any LLM error, all questions are marked as needs_human.
    """
    if not questions:
        return []

    llm_config = get_llm_config()
    if not llm_config:
        return [{"id": q["id"], "needs_human": True, "answer": None} for q in questions]

    client = _get_client()
    if not client:
        return [{"id": q["id"], "needs_human": True, "answer": None} for q in questions]

    user_message = _build_questions_message(questions, profile_text, user_name)
    provider = llm_config.get("provider", "custom")
    model = llm_config["model"]

    try:
        if provider == "codex":
            raw = _generate_via_responses(
                client, model, user_message, QUESTIONNAIRE_SYSTEM_PROMPT,
            )
        else:
            raw = _generate_via_chat_completions(
                client, model, user_message, QUESTIONNAIRE_SYSTEM_PROMPT,
            )
    except (OpenAIError, Exception) as e:
        click.echo(f"  ! LLM ошибка: {e}")
        return [{"id": q["id"], "needs_human": True, "answer": None} for q in questions]

    if not raw:
        return [{"id": q["id"], "needs_human": True, "answer": None} for q in questions]

    return _parse_answers_response(raw, questions)
