import click

from openhunt import __version__


@click.group()
@click.version_option(__version__)
@click.option("--verbose", "-v", is_flag=True, help="Расширенный вывод для отладки.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """openhunt — автоматизация поиска работы на hh.ru."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@main.command()
def login() -> None:
    """Авторизоваться на hh.ru (откроется браузер)."""
    from openhunt.browser.auth import login as do_login

    do_login()


@main.command()
@click.option("--query", "-q", type=str, help="Поисковый запрос.")
@click.option("--saved", "-s", type=str, help="Имя сохранённого запроса.")
@click.option("--recommended", "-r", is_flag=True, help="Откликаться на рекомендованные вакансии.")
@click.option("--resume", type=str, help="ID резюме на hh.ru (если не указан, используется сохранённый).")
@click.option("--limit", "-l", type=int, default=10, show_default=True, help="Максимум откликов.")
@click.option("--dry-run", is_flag=True, help="Показать вакансии без отправки откликов.")
@click.option(
    "--letter",
    type=click.Choice(["off", "template", "llm", "auto"], case_sensitive=False),
    default=None,
    help=(
        "Стратегия сопроводительного письма: "
        "off — не заполнять (шаблон если обязательно), "
        "template — всегда шаблон, "
        "llm — генерация через LLM, "
        "auto — пропустить если необязательно, LLM/шаблон если обязательно. "
        "По умолчанию: llm если LLM настроен, иначе template. "
        "Сохранить: openhunt letter strategy <режим>."
    ),
)
def apply(query: str | None, saved: str | None, recommended: bool, resume: str | None, limit: int, dry_run: bool, letter: str | None) -> None:
    """Автоматически откликнуться на вакансии.

    Укажите источник вакансий (обязательно один из):
    --query, --saved или --recommended.
    """
    from openhunt.browser.actions.apply import LetterStrategy, apply_to_vacancies
    from openhunt.config import get_cover_letter, get_default_resume, get_letter_strategy, get_llm_config, get_saved_queries

    if resume is None:
        resume = get_default_resume()
    if not resume:
        raise click.UsageError(
            "Укажите --resume или сохраните ID: openhunt resume set <ID>"
        )

    # Resolve the query source
    sources = sum([query is not None, saved is not None, recommended])
    if sources == 0:
        raise click.UsageError("Укажите --query, --saved или --recommended.")
    if sources > 1:
        raise click.UsageError("Укажите только один из: --query, --saved, --recommended.")

    if saved:
        queries = get_saved_queries()
        if saved not in queries:
            raise click.UsageError(f"Запрос '{saved}' не найден. Используйте 'openhunt query list'.")
        query = queries[saved]

    # Resolve letter strategy: CLI flag > saved config > backward-compatible default
    if letter is not None:
        letter_strategy = LetterStrategy(letter)
    else:
        saved_strategy = get_letter_strategy()
        if saved_strategy is not None:
            try:
                letter_strategy = LetterStrategy(saved_strategy)
            except ValueError:
                letter_strategy = None
        else:
            letter_strategy = None
        if letter_strategy is None:
            letter_strategy = LetterStrategy.LLM if get_llm_config() is not None else LetterStrategy.TEMPLATE

    apply_to_vacancies(
        query=query,
        recommended=recommended,
        resume_id=resume,
        limit=limit,
        cover_letter=get_cover_letter(),
        letter_strategy=letter_strategy,
        dry_run=dry_run,
    )


@main.group()
def resume() -> None:
    """Управление резюме."""


@resume.command("set")
@click.argument("resume_id")
def resume_set(resume_id: str) -> None:
    """Сохранить ID резюме по умолчанию."""
    from openhunt.config import set_default_resume

    if not resume_id.strip():
        raise click.UsageError("ID резюме не может быть пустым.")
    set_default_resume(resume_id.strip())
    click.echo(f"Резюме сохранено: {resume_id.strip()}")


@resume.command("sync")
def resume_sync() -> None:
    """Скачать профиль резюме с hh.ru (опыт, навыки, образование) для генерации писем."""
    from openhunt.browser.actions.profile import sync_resume_profile
    from openhunt.browser.session import browser_context, check_auth
    from openhunt.config import get_default_resume

    resume_id = get_default_resume()
    if not resume_id:
        raise click.UsageError(
            "Сначала сохраните ID резюме: openhunt resume set <ID>"
        )

    with browser_context(headless=True) as page:
        if not check_auth(page):
            click.echo("Сессия истекла. Выполните 'openhunt login' для авторизации.")
            return

        sync_resume_profile(page, resume_id)
        click.echo("Профиль синхронизирован.")


@resume.command("show")
def resume_show() -> None:
    """Показать сохранённый ID резюме."""
    from openhunt.config import get_default_resume

    resume_id = get_default_resume()
    if resume_id:
        click.echo(resume_id)
    else:
        click.echo("Резюме не задано. Сохраните: openhunt resume set <ID>")


@resume.command("raise")
def resume_raise() -> None:
    """Поднять резюме в поиске на hh.ru (обновить дату, чтобы быть выше в выдаче)."""
    from openhunt.browser.actions.resume import raise_resume

    raise_resume()


@main.group()
def letter() -> None:
    """Управление сопроводительным письмом."""


@letter.command("show")
def letter_show() -> None:
    """Показать текущий шаблон сопроводительного письма."""
    from openhunt.config import get_cover_letter

    click.echo(get_cover_letter())


@letter.command("set")
@click.argument("text")
def letter_set(text: str) -> None:
    """Задать свой шаблон: openhunt letter set "текст письма"."""
    from openhunt.config import set_cover_letter

    if not text.strip():
        raise click.UsageError("Текст письма не может быть пустым.")
    set_cover_letter(text.strip())
    click.echo("Шаблон сохранён.")


@letter.command("reset")
def letter_reset() -> None:
    """Вернуть шаблон по умолчанию."""
    from openhunt.config import reset_cover_letter

    reset_cover_letter()
    click.echo("Шаблон сброшен на значение по умолчанию.")


@letter.command("strategy")
@click.argument(
    "mode",
    required=False,
    default=None,
    type=click.Choice(["off", "template", "llm", "auto"], case_sensitive=False),
)
def letter_strategy_cmd(mode: str | None) -> None:
    """Показать или задать стратегию письма.

    Без аргумента — показать текущую стратегию.
    С аргументом — задать новую.
    """
    from openhunt.config import get_letter_strategy, set_letter_strategy

    if mode is None:
        current = get_letter_strategy()
        if current:
            click.echo(f"Стратегия: {current}")
        else:
            click.echo("Стратегия не задана (используется по умолчанию).")
        return

    set_letter_strategy(mode.lower())
    click.echo(f"Стратегия сохранена: {mode.lower()}")


@main.group()
def query() -> None:
    """Управление сохранёнными поисковыми запросами."""


@query.command("save")
@click.argument("name")
@click.argument("query_text")
def query_save(name: str, query_text: str) -> None:
    """Сохранить запрос: openhunt query save NAME "запрос"."""
    from openhunt.config import save_query

    save_query(name, query_text)
    click.echo(f"Запрос '{name}' сохранён.")


@query.command("list")
def query_list() -> None:
    """Показать все сохранённые запросы."""
    from openhunt.config import get_saved_queries

    queries = get_saved_queries()
    if not queries:
        click.echo("Нет сохранённых запросов.")
        return
    for name, q in queries.items():
        click.echo(f"  {name}: {q}")


@main.group()
def llm() -> None:
    """Настройка LLM-провайдера для генерации сопроводительных писем."""


@llm.command("setup")
@click.option(
    "--provider", "-p", required=True,
    type=click.Choice(["openrouter", "codex", "custom"]),
    help="LLM-провайдер.",
)
@click.option("--api-key", "-k", type=str, default=None, help="API-ключ (не нужен для codex).")
@click.option("--model", "-m", required=True, help="Название модели.")
@click.option("--base-url", "-u", type=str, default=None, help="Base URL (только для custom).")
def llm_setup(provider: str, api_key: str | None, model: str, base_url: str | None) -> None:
    """Настроить LLM-провайдер."""
    from openhunt.config import set_llm_config

    if provider == "custom" and not base_url:
        raise click.UsageError("Для custom-провайдера укажите --base-url.")
    if provider != "codex" and not api_key:
        raise click.UsageError("Укажите --api-key для этого провайдера.")
    if provider == "codex" and api_key:
        click.echo("Codex использует OAuth, --api-key игнорируется.")
        api_key = None
    set_llm_config(provider, api_key, model, base_url)
    click.echo(f"LLM настроен: {provider}, модель {model}")
    if provider == "codex":
        from openhunt.config import get_codex_tokens

        if not get_codex_tokens():
            click.echo("Для авторизации выполните: openhunt codex login")


@llm.command("show")
def llm_show() -> None:
    """Показать текущие настройки LLM."""
    from openhunt.config import get_codex_tokens, get_llm_config

    config = get_llm_config()
    if not config:
        click.echo("LLM не настроен. Используйте: openhunt llm setup")
        return
    click.echo(f"  Провайдер: {config['provider']}")
    if config.get("api_key"):
        key = config["api_key"]
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
        click.echo(f"  API-ключ:  {masked}")
    elif config["provider"] == "codex":
        status = "авторизован" if get_codex_tokens() else "не авторизован"
        click.echo(f"  OAuth:     {status}")
    click.echo(f"  Модель:    {config['model']}")
    if config.get("base_url"):
        click.echo(f"  Base URL:  {config['base_url']}")


@llm.command("reset")
def llm_reset() -> None:
    """Удалить настройки LLM (вернуться к шаблону)."""
    from openhunt.config import reset_llm_config

    reset_llm_config()
    click.echo("Настройки LLM удалены. Будет использоваться шаблон.")


@query.command("delete")
@click.argument("name")
def query_delete(name: str) -> None:
    """Удалить сохранённый запрос."""
    from openhunt.config import delete_query

    if delete_query(name):
        click.echo(f"Запрос '{name}' удалён.")
    else:
        click.echo(f"Запрос '{name}' не найден.")


@main.group()
def codex() -> None:
    """Управление авторизацией OpenAI Codex (LLM-провайдер через OAuth)."""


@codex.command("login")
def codex_login_cmd() -> None:
    """Авторизоваться в OpenAI Codex (OAuth, откроется браузер)."""
    from openhunt.auth import codex_login

    codex_login()


@codex.command("logout")
def codex_logout_cmd() -> None:
    """Удалить сохранённые токены Codex."""
    from openhunt.config import reset_codex_tokens

    reset_codex_tokens()
    click.echo("Токены Codex удалены.")


@codex.command("status")
def codex_status_cmd() -> None:
    """Показать статус авторизации Codex."""
    from openhunt.config import get_codex_tokens

    tokens = get_codex_tokens()
    if not tokens:
        click.echo("Не авторизован. Выполните: openhunt codex login")
        return

    from openhunt.auth import _is_token_expired

    if _is_token_expired(tokens["access_token"]):
        click.echo("Токен истёк, будет обновлён автоматически при использовании.")
    else:
        click.echo("Авторизован, токен действителен.")


if __name__ == "__main__":
    main()
