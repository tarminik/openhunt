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
@click.option("--resume", type=str, required=True, help="ID резюме на hh.ru.")
@click.option("--limit", "-l", type=int, default=10, show_default=True, help="Максимум откликов.")
def apply(query: str | None, saved: str | None, recommended: bool, resume: str, limit: int) -> None:
    """Автоматически откликнуться на вакансии."""
    from openhunt.browser.actions.apply import apply_to_vacancies
    from openhunt.config import get_saved_queries

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
    )


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
