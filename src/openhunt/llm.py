"""LLM-powered cover letter generation."""

import hashlib

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
) -> str | None:
    """Generate using the standard chat completions API."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
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
) -> str | None:
    """Generate using the OpenAI Responses API (Codex)."""
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
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
