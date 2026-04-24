"""Auto-apply to vacancies on hh.ru."""

import re
import time
from enum import Enum, StrEnum
from pathlib import Path
from urllib.parse import quote

import click
from playwright.sync_api import Page

from openhunt.browser import selectors
from openhunt.browser.session import browser_context, check_auth, human_delay


class LetterStrategy(StrEnum):
    OFF = "off"
    TEMPLATE = "template"
    LLM = "llm"
    AUTO = "auto"


class QuestionnaireStrategy(StrEnum):
    """How to handle vacancies that require answering employer questions."""

    SKIP = "skip"               # current default — skip and report
    INTERACTIVE = "interactive"  # fill via memory, prompt user for unknowns
    AUTO = "auto"               # fill from memory if all ready, save pending otherwise


class ApplyResult(Enum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    QUESTIONNAIRE = "questionnaire"
    EXCLUDED = "excluded"
    ERROR = "error"


SEARCH_URL = "https://hh.ru/search/vacancy?text={query}&page={page}"
RECOMMENDED_URL = "https://hh.ru/search/vacancy?resume={resume_id}&hhtmFrom=main&page={page}"
GOTO_TIMEOUT = 15_000  # 15 seconds for vacancy page loads


def _get_vacancy_links(page: Page) -> list[tuple[str, str]]:
    """Extract vacancy (URL, title) pairs from the current page."""
    elements = page.query_selector_all(selectors.VACANCY_TITLE_LINK)
    links = []
    for el in elements:
        href = el.get_attribute("href")
        if href:
            if href.startswith("/"):
                href = f"https://hh.ru{href}"
            title = el.inner_text().strip().replace("\xa0", " ")
            links.append((href, title))
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

    if select_el:
        click.echo(
            f"  ! Предупреждение: резюме {resume_id} не найдено в списке опций,"
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
    vacancy_title: str,
    vacancy_text: str,
    fallback: str,
    profile_text: str = "",
    user_name: str = "",
) -> str:
    """Try LLM generation, fall back to template on failure."""
    from openhunt.llm import generate_cover_letter

    generated = generate_cover_letter(vacancy_title, vacancy_text, profile_text, user_name)
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


def _try_fill_inline_letter(
    page: Page,
    cover_letter: str,
    letter_strategy: "LetterStrategy",
    vacancy_title: str = "",
    vacancy_text: str = "",
    profile_text: str = "",
    user_name: str = "",
) -> None:
    """Fill and submit the inline cover letter form shown after instant apply."""
    if letter_strategy == LetterStrategy.OFF:
        return

    textarea = page.query_selector(selectors.RESPONSE_LETTER_TEXTAREA)
    submit = page.query_selector(selectors.RESPONSE_LETTER_SUBMIT)
    if not textarea or not submit or not textarea.is_visible():
        return

    if letter_strategy in (LetterStrategy.LLM, LetterStrategy.AUTO):
        if vacancy_title or vacancy_text:
            cover_letter = _generate_or_fallback(
                vacancy_title, vacancy_text, cover_letter, profile_text, user_name
            )

    textarea.fill(cover_letter)
    human_delay(0.3, 0.6)
    submit.click()
    human_delay(1.0, 2.0)


def _letter_field_is_visible(page: Page) -> bool:
    """Check if the cover letter textarea is present and visible in the popup."""
    el = page.query_selector(selectors.RESPONSE_POPUP_LETTER_INPUT)
    return el is not None and el.is_visible()


def _has_visible_text(page: Page, text: str, exact: bool = True) -> bool:
    """Check if the page contains visible text matching the given string."""
    loc = page.get_by_text(text, exact=exact)
    return loc.count() > 0 and loc.first.is_visible()


def _page_has_success_text(page: Page) -> bool:
    """Check if the page contains a visible success message."""
    return (
        _has_visible_text(page, selectors.RESPONSE_DELIVERED_TEXT)
        or _has_visible_text(page, selectors.RESPONSE_SENT_TEXT)
    )


def _page_has_questionnaire_text(page: Page) -> bool:
    """Check if the page contains a visible questionnaire prompt."""
    return (
        _has_visible_text(page, selectors.QUESTIONNAIRE_TEXT)
        or _has_visible_text(page, selectors.QUESTIONNAIRE_ALT_TEXT, exact=False)
    )


def _wait_for_apply_result(page: Page, timeout: int = 5000) -> str | None:
    """Wait for one of the mutually exclusive post-apply states to appear.

    Uses Playwright's locator.or_() to race between expected outcomes,
    avoiding false negatives on slow-rendering pages.

    Returns:
        "success" — success text visible
        "questionnaire" — questionnaire prompt visible
        "popup" — popup submit button visible
        "inline_letter" — inline letter submit visible
        None — none appeared within timeout
    """
    success_loc = (
        page.get_by_text(selectors.RESPONSE_DELIVERED_TEXT, exact=True)
        .or_(page.get_by_text(selectors.RESPONSE_SENT_TEXT, exact=True))
    )
    questionnaire_loc = (
        page.get_by_text(selectors.QUESTIONNAIRE_TEXT, exact=True)
        .or_(page.get_by_text(selectors.QUESTIONNAIRE_ALT_TEXT, exact=False))
    )
    popup_submit_loc = page.locator(selectors.RESPONSE_POPUP_SUBMIT)
    inline_letter_loc = page.locator(selectors.RESPONSE_LETTER_SUBMIT)

    combined = (
        success_loc
        .or_(questionnaire_loc)
        .or_(popup_submit_loc)
        .or_(inline_letter_loc)
    )

    try:
        combined.first.wait_for(state="visible", timeout=timeout)
    except Exception:
        return None

    # Determine which state matched by checking each individually.
    # Order matters: check the most definitive states first.
    if success_loc.first.is_visible():
        return "success"
    if questionnaire_loc.first.is_visible():
        return "questionnaire"
    if popup_submit_loc.first.is_visible():
        return "popup"
    if inline_letter_loc.first.is_visible():
        return "inline_letter"

    return None


def _try_apply(
    page: Page,
    vacancy_url: str,
    resume_id: str,
    cover_letter: str,
    letter_strategy: LetterStrategy = LetterStrategy.TEMPLATE,
    dry_run: bool = False,
    profile_text: str = "",
    user_name: str = "",
    questionnaires_dump_dir: Path | None = None,
    questionnaires_strategy: "QuestionnaireStrategy" = QuestionnaireStrategy.SKIP,
) -> ApplyResult:
    """Try to apply to a single vacancy.

    hh.ru has several apply flows:
    1. Simple: click apply → resume sent immediately ("Резюме доставлено")
    2. Popup (optional letter): click apply → modal with resume + optional letter → submit
    3. Popup (required letter): click apply → modal with required letter → fill template → submit
    4. Questionnaire: click apply → form with employer questions → skip

    Returns:
        ApplyResult.APPLIED — successfully applied (or would apply in dry-run)
        ApplyResult.ALREADY_APPLIED — already applied to this vacancy
        ApplyResult.QUESTIONNAIRE — has required questions from employer
        ApplyResult.ERROR — unexpected error
    """
    page.goto(vacancy_url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
    human_delay(0.5, 1.5)

    # Extract vacancy info early (before clicking apply changes the page).
    # Only needed for strategies that may use LLM generation.
    vacancy_title, vacancy_text = "", ""
    if letter_strategy in (LetterStrategy.LLM, LetterStrategy.AUTO) or dry_run:
        vacancy_title, vacancy_text = _extract_vacancy_info(page)

    # Find the apply button
    apply_btn = page.query_selector(selectors.APPLY_BUTTON)
    if not apply_btn:
        return ApplyResult.ALREADY_APPLIED

    btn_text = apply_btn.inner_text().strip()
    if btn_text != selectors.APPLY_BUTTON_TEXT:
        return ApplyResult.ALREADY_APPLIED

    if dry_run:
        return ApplyResult.APPLIED

    apply_btn.click()
    human_delay(1.5, 2.5)

    _dismiss_relocation_dialog(page)

    _select_resume_in_popup(page, resume_id)

    # Wait for one of the expected post-apply states to render.
    apply_state = _wait_for_apply_result(page)

    # --- Flow 1: Simple apply (resume sent immediately, no popup) ---
    # After instant apply, hh.ru may show an inline letter form.
    if apply_state == "success":
        _try_fill_inline_letter(
            page, cover_letter, letter_strategy,
            vacancy_title, vacancy_text, profile_text, user_name,
        )
        return ApplyResult.APPLIED

    # --- Flow 4: Questionnaire page ---
    if apply_state == "questionnaire":
        if questionnaires_dump_dir is not None:
            _dump_questionnaire(page, vacancy_url, questionnaires_dump_dir)

        if questionnaires_strategy == QuestionnaireStrategy.INTERACTIVE:
            from openhunt.browser.actions.questionnaire import (
                fill_questionnaire,
                submit_questionnaire,
            )

            try:
                filled = fill_questionnaire(page, interactive=True)
            except (KeyboardInterrupt, click.Abort):
                # User aborted: propagate so the outer apply loop also stops,
                # rather than silently moving on to the next vacancy.
                raise
            except Exception as e:
                click.echo(f"  ! Ошибка при заполнении анкеты: {e}")
                filled = False

            if not filled:
                # Direct navigation back to the vacancy — page.go_back() is
                # unreliable on /applicant/vacancy_response (observed timeouts).
                page.goto(vacancy_url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
                return ApplyResult.QUESTIONNAIRE

            if submit_questionnaire(page):
                return ApplyResult.APPLIED
            click.echo("  ! Анкета заполнена, но отправка не подтверждена.")
            return ApplyResult.ERROR

        if questionnaires_strategy == QuestionnaireStrategy.AUTO:
            from openhunt.browser.actions.questionnaire import (
                collect_and_fill,
                submit_questionnaire,
            )

            try:
                result = collect_and_fill(page)
            except Exception as e:
                click.echo(f"  ! Ошибка при разборе анкеты: {e}")
                page.goto(vacancy_url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
                return ApplyResult.QUESTIONNAIRE

            if not result.filled:
                page.goto(vacancy_url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
                return ApplyResult.QUESTIONNAIRE

            if submit_questionnaire(page):
                return ApplyResult.APPLIED
            click.echo("  ! Анкета заполнена, но отправка не подтверждена.")
            return ApplyResult.ERROR

        # Skip mode: get back to the vacancy without using the unreliable
        # page.go_back() (which times out from the questionnaire page).
        page.goto(vacancy_url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
        return ApplyResult.QUESTIONNAIRE

    # --- Flows 2 & 3: Popup modal (optional or required letter) ---
    popup_submit = page.query_selector(selectors.RESPONSE_POPUP_SUBMIT)
    if apply_state == "popup" and popup_submit:
        letter_visible = _letter_field_is_visible(page)

        if letter_strategy == LetterStrategy.TEMPLATE:
            if letter_visible:
                _fill_cover_letter(page, cover_letter)
            popup_submit.click()
            human_delay(1.0, 2.0)

        elif letter_strategy == LetterStrategy.LLM:
            if letter_visible:
                if vacancy_title or vacancy_text:
                    cover_letter = _generate_or_fallback(
                        vacancy_title, vacancy_text, cover_letter, profile_text, user_name
                    )
                _fill_cover_letter(page, cover_letter)
            popup_submit.click()
            human_delay(1.0, 2.0)

        elif letter_strategy in (LetterStrategy.OFF, LetterStrategy.AUTO):
            # Try submitting without a letter first
            popup_submit.click()
            human_delay(1.0, 2.0)

            if not _page_has_success_text(page):
                # Popup stayed open → letter is required → fill and retry
                if letter_visible:
                    if letter_strategy == LetterStrategy.AUTO and (vacancy_title or vacancy_text):
                        cover_letter = _generate_or_fallback(
                            vacancy_title, vacancy_text, cover_letter, profile_text, user_name
                        )
                    _fill_cover_letter(page, cover_letter)
                    popup_submit = page.query_selector(selectors.RESPONSE_POPUP_SUBMIT)
                    if popup_submit:
                        popup_submit.click()
                        human_delay(1.0, 2.0)

        # Verify submission succeeded
        if _page_has_success_text(page):
            return ApplyResult.APPLIED
        # Popup still open — submission failed
        close_btn = page.query_selector(selectors.RESPONSE_POPUP_CLOSE)
        if close_btn:
            close_btn.click()
            human_delay(0.3, 0.5)
        return ApplyResult.ERROR

    # --- Fallback: post-apply page with inline letter form ---
    if apply_state == "inline_letter" or page.query_selector(selectors.RESPONSE_LETTER_SUBMIT):
        _try_fill_inline_letter(
            page, cover_letter, letter_strategy,
            vacancy_title, vacancy_text, profile_text, user_name,
        )
        return ApplyResult.APPLIED

    # Some flows render success text or inline forms with a delay — retry once
    human_delay(1.5, 2.5)
    if _page_has_success_text(page):
        return ApplyResult.APPLIED
    if page.query_selector(selectors.RESPONSE_LETTER_SUBMIT):
        _try_fill_inline_letter(
            page, cover_letter, letter_strategy,
            vacancy_title, vacancy_text, profile_text, user_name,
        )
        return ApplyResult.APPLIED

    # Unknown state — next iteration's page.goto(next_vacancy_url) handles
    # navigation; page.go_back() is unreliable on hh.ru and hangs until timeout.
    return ApplyResult.ERROR


_VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")


def _vacancy_id_from_url(url: str) -> str:
    """Extract vacancy ID from a hh.ru vacancy URL, or return 'unknown'."""
    m = _VACANCY_ID_RE.search(url)
    return m.group(1) if m else "unknown"


def _dump_questionnaire(page: Page, vacancy_url: str, dump_dir: Path) -> None:
    """Save questionnaire page (URL, HTML, screenshot) for offline analysis.

    Used by recon mode to collect real questionnaire samples before designing
    the actual fill flow.
    """
    try:
        dump_dir.mkdir(parents=True, exist_ok=True)
        vid = _vacancy_id_from_url(vacancy_url)
        ts = time.strftime("%Y%m%d-%H%M%S")
        sample_dir = dump_dir / f"{vid}_{ts}"
        sample_dir.mkdir(parents=True, exist_ok=True)

        meta = (
            f"vacancy_url: {vacancy_url}\n"
            f"current_url: {page.url}\n"
            f"title:       {page.title()}\n"
            f"timestamp:   {ts}\n"
        )
        (sample_dir / "meta.txt").write_text(meta, encoding="utf-8")
        (sample_dir / "page.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(sample_dir / "screenshot.png"), full_page=True)
        click.echo(f"  ⊙ Анкета сохранена: {sample_dir}")
    except Exception as e:
        click.echo(f"  ! Не удалось сохранить анкету: {e}")


def _compile_exclude_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    """Compile exclude regex patterns (case-insensitive).

    Raises click.UsageError on invalid regex.
    """
    compiled = []
    for pat in patterns:
        try:
            compiled.append(re.compile(pat, re.IGNORECASE))
        except re.error as e:
            raise click.UsageError(f"Некорректный regex в --exclude: '{pat}' ({e})")
    return compiled


def apply_to_vacancies(
    query: str | None,
    recommended: bool,
    resume_id: str,
    limit: int,
    cover_letter: str = "",
    letter_strategy: LetterStrategy = LetterStrategy.TEMPLATE,
    dry_run: bool = False,
    exclude_patterns: list[str] | None = None,
    questionnaires_dump_dir: Path | None = None,
    questionnaires_strategy: QuestionnaireStrategy = QuestionnaireStrategy.SKIP,
) -> None:
    """Main apply loop."""
    compiled_excludes = _compile_exclude_patterns(exclude_patterns or [])

    with browser_context(headless=True) as page:
        if not check_auth(page):
            click.echo("Сессия истекла. Выполните 'openhunt login' для авторизации.")
            return

        # Silent auto-sync of resume profile if stale or missing
        profile_text = ""
        user_name = ""
        if letter_strategy in (LetterStrategy.LLM, LetterStrategy.AUTO):
            from openhunt.memory import get_profile, get_user_name, profile_needs_sync

            if profile_needs_sync(resume_id):
                from openhunt.browser.actions.profile import sync_resume_profile
                sync_resume_profile(page, resume_id)
            profile_text = get_profile(resume_id) or ""
            user_name = get_user_name() or ""

        applied = 0
        skipped = {ApplyResult.ALREADY_APPLIED: 0, ApplyResult.QUESTIONNAIRE: 0, ApplyResult.EXCLUDED: 0, ApplyResult.ERROR: 0}
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

            for link, title in vacancy_links:
                if applied >= limit:
                    break

                if compiled_excludes and any(pat.search(title) for pat in compiled_excludes):
                    skipped[ApplyResult.EXCLUDED] += 1
                    click.echo(f"  ~ Пропуск (исключён): {title}")
                    continue

                try:
                    result = _try_apply(
                        page, link, resume_id, cover_letter, letter_strategy, dry_run,
                        profile_text, user_name, questionnaires_dump_dir,
                        questionnaires_strategy,
                    )
                except (KeyboardInterrupt, click.Abort):
                    # User aborted (e.g. Ctrl+C in interactive questionnaire) —
                    # do not swallow it as a per-vacancy error.
                    raise
                except Exception as e:
                    click.echo(f"  ! Ошибка: {e}")
                    result = ApplyResult.ERROR

                if result == ApplyResult.APPLIED:
                    applied += 1
                    if dry_run:
                        click.echo(f"  [{applied}/{limit}] Откликнулся бы: {title}\n    {link}")
                    else:
                        click.echo(f"  [{applied}/{limit}] Откликнулся: {title}\n    {link}")
                        human_delay(2.0, 4.0)
                else:
                    skipped[result] += 1
                    reason = {
                        ApplyResult.ALREADY_APPLIED: "уже откликались",
                        ApplyResult.QUESTIONNAIRE: "требуется анкета",
                        ApplyResult.EXCLUDED: "исключён",
                        ApplyResult.ERROR: "ошибка",
                    }.get(result, str(result))
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
            if skipped[ApplyResult.ALREADY_APPLIED]:
                click.echo(f"    Уже откликались: {skipped[ApplyResult.ALREADY_APPLIED]}")
            if skipped[ApplyResult.QUESTIONNAIRE]:
                click.echo(f"    Требуется анкета: {skipped[ApplyResult.QUESTIONNAIRE]}")
            if skipped[ApplyResult.EXCLUDED]:
                click.echo(f"    Исключено по фильтру: {skipped[ApplyResult.EXCLUDED]}")
            if skipped[ApplyResult.ERROR]:
                click.echo(f"    Ошибки: {skipped[ApplyResult.ERROR]}")
