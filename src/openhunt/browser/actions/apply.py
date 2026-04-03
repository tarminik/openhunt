"""Auto-apply to vacancies on hh.ru."""

from urllib.parse import quote

import click
from playwright.sync_api import Page

from openhunt.browser import selectors
from openhunt.browser.session import browser_context, check_auth, human_delay


SEARCH_URL = "https://hh.ru/search/vacancy?text={query}&page={page}"
RECOMMENDED_URL = "https://hh.ru/search/vacancy?resume={resume_id}&hhtmFrom=main&page={page}"


def _get_vacancy_links(page: Page) -> list[str]:
    """Extract vacancy URLs from the current page."""
    elements = page.query_selector_all(selectors.VACANCY_TITLE_LINK)
    links = []
    for el in elements:
        href = el.get_attribute("href")
        if href:
            if href.startswith("/"):
                href = f"https://hh.ru{href}"
            links.append(href)
    return links



def _dismiss_relocation_dialog(page: Page) -> None:
    """Handle the 'applying to a vacancy in another country' dialog if it appears."""
    confirm = page.get_by_text(selectors.RELOCATION_CONFIRM_TEXT)
    if confirm.count() > 0:
        confirm.first.click()
        human_delay(1.5, 2.5)


def _select_resume_in_popup(page: Page, resume_id: str) -> None:
    """Select the correct resume in the response popup if a resume selector is present.

    When a user has multiple resumes, hh.ru may show a dropdown or clickable
    items to pick which resume to attach.  Tries <select> first, then falls
    back to clickable items scoped to the dialog.
    """
    dialog = page.query_selector("[role='dialog']")

    # Try 1: <select> dropdown
    select_el = page.query_selector(selectors.RESPONSE_POPUP_RESUME_SELECT)
    if select_el:
        options = select_el.query_selector_all("option")
        for option in options:
            value = option.get_attribute("value") or ""
            if resume_id in value:
                select_el.select_option(value=value)
                human_delay(0.3, 0.6)
                return

    # Try 2: clickable items / radio buttons scoped to dialog
    scope = dialog if dialog else page
    resume_item = scope.query_selector(f"[data-qa*='{resume_id}']")
    if resume_item:
        resume_item.click()
        human_delay(0.3, 0.6)
        return

    # No resume selector found at all — single-resume account, nothing to do
    if not select_el and not dialog:
        return

    click.echo(
        f"  ! Предупреждение: резюме {resume_id} не найдено в селекторе,"
        " используется по умолчанию"
    )


def _try_apply(page: Page, vacancy_url: str, resume_id: str) -> str:
    """Try to apply to a single vacancy.

    hh.ru has several apply flows:
    1. Simple: click apply → resume sent immediately ("Резюме доставлено")
    2. Popup (optional letter): click apply → modal with resume + optional letter → submit
    3. Popup (required letter): click apply → modal with required letter → skip
    4. Questionnaire: click apply → form with employer questions → skip

    Returns:
        "applied" — successfully applied
        "already_applied" — already applied to this vacancy
        "cover_letter" — requires a mandatory cover letter
        "questionnaire" — has required questions from employer
        "error" — unexpected error
    """
    page.goto(vacancy_url, wait_until="domcontentloaded")
    human_delay(0.5, 1.5)

    # Find the apply button
    apply_btn = page.query_selector(selectors.APPLY_BUTTON)
    if not apply_btn:
        return "already_applied"

    btn_text = apply_btn.inner_text().strip()
    if btn_text != selectors.APPLY_BUTTON_TEXT:
        return "already_applied"

    apply_btn.click()
    human_delay(1.5, 2.5)

    _dismiss_relocation_dialog(page)

    _select_resume_in_popup(page, resume_id)

    # --- Flow 1: Simple apply (resume sent immediately, no popup) ---
    body = page.inner_text("body")
    if selectors.RESPONSE_DELIVERED_TEXT in body or selectors.RESPONSE_SENT_TEXT in body:
        return "applied"

    # --- Flow 4: Questionnaire page ---
    if selectors.QUESTIONNAIRE_TEXT in body or selectors.QUESTIONNAIRE_ALT_TEXT in body:
        page.go_back()
        return "questionnaire"

    # --- Flows 2 & 3: Popup modal ---
    popup_submit = page.query_selector(selectors.RESPONSE_POPUP_SUBMIT)
    if popup_submit:
        # Check if cover letter is required
        dialog = page.query_selector("[role='dialog']")
        if dialog and dialog.is_visible():
            dialog_text = dialog.inner_text()
            if selectors.COVER_LETTER_REQUIRED_TEXT in dialog_text.lower() and selectors.COVER_LETTER_KEYWORD_TEXT in dialog_text.lower():
                # Close the popup and skip
                close_btn = page.query_selector(selectors.RESPONSE_POPUP_CLOSE)
                if close_btn:
                    close_btn.click()
                    human_delay(0.3, 0.5)
                return "cover_letter"

        # Optional or no cover letter — submit
        popup_submit.click()
        human_delay(1.0, 2.0)
        return "applied"

    # --- Fallback: post-apply page with letter submit ---
    if page.query_selector(selectors.RESPONSE_LETTER_SUBMIT):
        return "applied"

    # Unknown state
    page.go_back()
    return "error"


def apply_to_vacancies(
    query: str | None,
    recommended: bool,
    resume_id: str,
    limit: int,
) -> None:
    """Main apply loop."""
    with browser_context(headless=True) as (context, page):
        if not check_auth(page):
            click.echo("Сессия истекла. Выполните 'openhunt login' для авторизации.")
            return

        applied = 0
        skipped = {"already_applied": 0, "cover_letter": 0, "questionnaire": 0, "error": 0}
        page_num = 0

        if recommended:
            click.echo("Отклики на рекомендованные вакансии...")
        else:
            click.echo(f"Поиск: {query}")

        while applied < limit:
            # Build the listing URL
            if recommended:
                serp_url = RECOMMENDED_URL.format(resume_id=resume_id, page=page_num)
            else:
                serp_url = SEARCH_URL.format(query=quote(query, safe=""), page=page_num)

            page.goto(serp_url, wait_until="domcontentloaded")
            human_delay(1.0, 2.0)

            # Collect all vacancy links and check for next page before navigating away
            vacancy_links = _get_vacancy_links(page)
            if not vacancy_links:
                click.echo("Вакансий больше не найдено.")
                break
            has_next = page.query_selector(selectors.PAGER_NEXT) is not None

            for link in vacancy_links:
                if applied >= limit:
                    break

                try:
                    result = _try_apply(page, link, resume_id)
                except Exception as e:
                    click.echo(f"  ! Ошибка: {e}")
                    result = "error"

                if result == "applied":
                    applied += 1
                    click.echo(f"  [{applied}/{limit}] Откликнулся: {link}")
                    human_delay(2.0, 4.0)
                else:
                    skipped[result] += 1
                    reason = {
                        "already_applied": "уже откликались",
                        "cover_letter": "требуется сопроводительное",
                        "questionnaire": "требуется анкета",
                        "error": "ошибка",
                    }.get(result, result)
                    click.echo(f"  ~ Пропуск ({reason}): {link}")

            if applied >= limit:
                break

            if not has_next:
                click.echo("Достигнута последняя страница результатов.")
                break
            page_num += 1
            human_delay(1.0, 2.0)

        # Report
        total_skipped = sum(skipped.values())
        click.echo(f"\nГотово!")
        click.echo(f"  Откликов отправлено: {applied}")
        if total_skipped > 0:
            click.echo(f"  Пропущено: {total_skipped}")
            if skipped["already_applied"]:
                click.echo(f"    Уже откликались: {skipped['already_applied']}")
            if skipped["cover_letter"]:
                click.echo(f"    Требуется сопроводительное: {skipped['cover_letter']}")
            if skipped["questionnaire"]:
                click.echo(f"    Требуется анкета: {skipped['questionnaire']}")
            if skipped["error"]:
                click.echo(f"    Ошибки: {skipped['error']}")
