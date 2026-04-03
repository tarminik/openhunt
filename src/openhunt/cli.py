import click

from openhunt import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """openhunt — автоматизация поиска работы на hh.ru."""


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
def apply(query: str | None, saved: str | None, recommended: bool, resume: str | None, limit: int) -> None:
    """Автоматически откликнуться на вакансии."""
    from openhunt.browser.actions.apply import apply_to_vacancies
    from openhunt.config import get_cover_letter, get_default_resume, get_saved_queries

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

    apply_to_vacancies(
        query=query,
        recommended=recommended,
        resume_id=resume,
        limit=limit,
        cover_letter=get_cover_letter(),
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
    """Поднять резюме в поиске на hh.ru."""
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


@query.command("delete")
@click.argument("name")
def query_delete(name: str) -> None:
    """Удалить сохранённый запрос."""
    from openhunt.config import delete_query

    if delete_query(name):
        click.echo(f"Запрос '{name}' удалён.")
    else:
        click.echo(f"Запрос '{name}' не найден.")


if __name__ == "__main__":
    main()
