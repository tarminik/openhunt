"""Resume actions on hh.ru."""

import re

import click

from openhunt.browser import selectors
from openhunt.browser.session import browser_context, check_auth, human_delay


RESUMES_URL = "https://hh.ru/applicant/resumes"


def raise_resume() -> None:
    """Raise all resumes in search on hh.ru."""
    with browser_context(headless=True) as (context, page):
        if not check_auth(page):
            click.echo("Сессия истекла. Выполните 'openhunt login' для авторизации.")
            return

        page.goto(RESUMES_URL, wait_until="domcontentloaded")
        human_delay(1.0, 2.0)

        buttons = page.query_selector_all(selectors.RESUME_RAISE_BUTTON)
        if not buttons:
            # No raise button — check if there's a cooldown message
            cooldown = page.get_by_text(selectors.RESUME_COOLDOWN_TEXT)
            if cooldown.count() > 0:
                text = cooldown.first.inner_text().strip().replace("\xa0", " ")
                match = re.search(r"можно (.+)", text)
                when = match.group(1) if match else ""
                click.echo(f"Резюме уже поднято. Следующее поднятие: {when}")
            else:
                click.echo("Кнопки «Поднять в поиске» не найдены.")
            return

        raised = 0
        max_attempts = len(buttons)
        for _ in range(max_attempts):
            buttons = page.query_selector_all(selectors.RESUME_RAISE_BUTTON)
            btn = None
            for b in buttons:
                if selectors.RESUME_RAISE_TEXT in b.inner_text().strip():
                    btn = b
                    break
            if btn is None:
                break
            btn.click()
            human_delay(1.5, 2.5)
            raised += 1
            click.echo("  Резюме поднято!")

        if raised == 0:
            click.echo("Все резюме уже подняты.")
        else:
            click.echo(f"\nГотово! Поднято резюме: {raised}")
