"""Interactive authentication flow for hh.ru."""

import click

from openhunt.browser.session import browser_context, check_auth, LOGIN_URL


def login() -> None:
    """Open a headed browser for the user to log in manually."""
    with browser_context(headless=False) as page:
        if check_auth(page):
            click.echo("Вы уже авторизованы на hh.ru.")
            return

        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        click.echo("Браузер открыт. Пожалуйста, авторизуйтесь на hh.ru.")
        click.echo("После входа окно закроется автоматически.")

        # Wait up to 5 minutes for the user to complete login
        try:
            page.wait_for_url(
                lambda url: "hh.ru" in url and "/account/" not in url,
                timeout=300_000,
            )
        except Exception:
            click.echo("Время ожидания истекло. Попробуйте снова: openhunt login")
            return

        click.echo("Авторизация успешна! Сессия сохранена.")
