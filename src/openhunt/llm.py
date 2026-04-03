"""LLM-powered cover letter generation."""

import click
from openai import OpenAI, OpenAIError

from openhunt.config import get_llm_config

PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
}

SYSTEM_PROMPT = (
    "Ты — помощник соискателя. Напиши короткое сопроводительное письмо (2-3 предложения) "
    "на русском языке для отклика на вакансию. Письмо должно быть профессиональным, "
    "конкретным и показывать интерес к позиции. Не используй шаблонные фразы вроде "
    '"с большим интересом". Отвечай только текстом письма, без приветствия и подписи.'
)

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


def generate_cover_letter(vacancy_title: str, vacancy_text: str) -> str | None:
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
        user_message = f"Вакансия: {vacancy_title}\n\n{vacancy_text}"

        response = client.chat.completions.create(
            model=llm_config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        if not response.choices:
            return None
        content = response.choices[0].message.content
        return content.strip() if content else None
    except (OpenAIError, Exception) as e:
        click.echo(f"  ! LLM ошибка: {e}")
        return None
