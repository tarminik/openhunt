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


def _extract_vacancy_info(page: Page) -> tuple[str, str]:
    """Extract vacancy title and description text from the current page."""
    title_el = page.query_selector(selectors.VACANCY_TITLE)
    title = title_el.inner_text().strip() if title_el else ""

    desc_el = page.query_selector(selectors.VACANCY_DESCRIPTION)
    description = desc_el.inner_text().strip() if desc_el else ""

    return title, description


def _generate_or_fallback(
    vacancy_title: str, vacancy_text: str, fallback: str
) -> str:
    """Try LLM generation, fall back to template on failure."""
    from openhunt.llm import generate_cover_letter

    generated = generate_cover_letter(vacancy_title, vacancy_text)
    if generated:
        return generated
    click.echo("  ! LLM не сгенерировал письмо, используется шаблон.")
    return fallback


def _fill_cover_letter(page: Page, cover_letter: str) -> None:
    """Fill the cover letter field if present and visible in the current popup."""
    letter_input = page.query_selector(selectors.RESPONSE_POPUP_LETTER_INPUT)
    if letter_input and letter_input.is_visible():
        letter_input.fill(cover_letter)
        human_delay(0.3, 0.6)


def _page_has_success_text(page: Page) -> bool:
    """Check if the page contains a success message without reading the full body text."""
    return (
        page.get_by_text(selectors.RESPONSE_DELIVERED_TEXT).count() > 0
        or page.get_by_text(selectors.RESPONSE_SENT_TEXT).count() > 0
    )


def _page_has_questionnaire_text(page: Page) -> bool:
    """Check if the page contains a questionnaire prompt without reading the full body text."""
    return (
        page.get_by_text(selectors.QUESTIONNAIRE_TEXT).count() > 0
        or page.get_by_text(selectors.QUESTIONNAIRE_ALT_TEXT).count() > 0
    )


def _try_apply(
    page: Page,
    vacancy_url: str,
    resume_id: str,
    cover_letter: str,
    use_llm: bool = False,
    dry_run: bool = False,
) -> str:
    """Try to apply to a single vacancy.

    hh.ru has several apply flows:
    1. Simple: click apply → resume sent immediately ("Резюме доставлено")
    2. Popup (optional letter): click apply → modal with resume + optional letter → submit
    3. Popup (required letter): click apply → modal with required letter → fill template → submit
    4. Questionnaire: click apply → form with employer questions → skip

    Returns:
        "applied" — successfully applied (or would apply in dry-run)
        "already_applied" — already applied to this vacancy
        "questionnaire" — has required questions from employer
        "error" — unexpected error
    """
    page.goto(vacancy_url, wait_until="domcontentloaded")
    human_delay(0.5, 1.5)

    # Extract vacancy info early (before clicking apply changes the page).
    # The actual LLM call is deferred until we know a letter field is present.
    vacancy_title, vacancy_text = "", ""
    if use_llm or dry_run:
        vacancy_title, vacancy_text = _extract_vacancy_info(page)

    # Find the apply button
    apply_btn = page.query_selector(selectors.APPLY_BUTTON)
    if not apply_btn:
        return "already_applied"

    btn_text = apply_btn.inner_text().strip()
    if btn_text != selectors.APPLY_BUTTON_TEXT:
        return "already_applied"

    if dry_run:
        return "applied"

    apply_btn.click()
    human_delay(1.5, 2.5)

    _dismiss_relocation_dialog(page)

    _select_resume_in_popup(page, resume_id)

    # --- Flow 1: Simple apply (resume sent immediately, no popup) ---
    if _page_has_success_text(page):
        return "applied"

    # --- Flow 4: Questionnaire page ---
    if _page_has_questionnaire_text(page):
        page.go_back()
        return "questionnaire"

    # --- Flows 2 & 3: Popup modal (optional or required letter) ---
    popup_submit = page.query_selector(selectors.RESPONSE_POPUP_SUBMIT)
    if popup_submit:
        # Generate LLM letter only when a letter field is actually present
        if use_llm and (vacancy_title or vacancy_text):
            cover_letter = _generate_or_fallback(
                vacancy_title, vacancy_text, cover_letter
            )
        _fill_cover_letter(page, cover_letter)
        popup_submit.click()
        human_delay(1.0, 2.0)

        # Verify submission succeeded
        if _page_has_success_text(page):
            return "applied"
        # Popup still open — submission failed (e.g. validation error)
        close_btn = page.query_selector(selectors.RESPONSE_POPUP_CLOSE)
        if close_btn:
            close_btn.click()
            human_delay(0.3, 0.5)
        return "error"

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
    cover_letter: str = "",
    use_llm: bool = False,
    dry_run: bool = False,
) -> None:
    """Main apply loop."""
    with browser_context(headless=True) as (context, page):
        if not check_auth(page):
            click.echo("Сессия истекла. Выполните 'openhunt login' для авторизации.")
            return

        applied = 0
        skipped = {"already_applied": 0, "questionnaire": 0, "error": 0}
        page_num = 0

        if dry_run:
            click.echo("[dry-run] Пробный запуск — отклики не отправляются.\n")

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
                    result = _try_apply(page, link, resume_id, cover_letter, use_llm, dry_run)
                except Exception as e:
                    click.echo(f"  ! Ошибка: {e}")
                    result = "error"

                if result == "applied":
                    applied += 1
                    if dry_run:
                        click.echo(f"  [{applied}/{limit}] Откликнулся бы: {link}")
                    else:
                        click.echo(f"  [{applied}/{limit}] Откликнулся: {link}")
                        human_delay(2.0, 4.0)
                else:
                    skipped[result] += 1
                    reason = {
                        "already_applied": "уже откликались",
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
        if dry_run:
            click.echo(f"  Доступно для отклика: {applied}")
        else:
            click.echo(f"  Откликов отправлено: {applied}")
        if total_skipped > 0:
            click.echo(f"  Пропущено: {total_skipped}")
            if skipped["already_applied"]:
                click.echo(f"    Уже откликались: {skipped['already_applied']}")
            if skipped["questionnaire"]:
                click.echo(f"    Требуется анкета: {skipped['questionnaire']}")
            if skipped["error"]:
                click.echo(f"    Ошибки: {skipped['error']}")
