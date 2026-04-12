"""Parse, fill, and submit hh.ru employer questionnaires.

A questionnaire lives at /applicant/vacancy_response?vacancyId=... and contains:
- a [data-qa='employer-asking-for-test'] block with one or more questions
- each question is a [data-qa='task-body'] containing question text and answer inputs
- the same submit button as the regular response popup

All option-based question types share the same DOM wrapper (label[data-qa='cell']);
they differ only in the inner <input type='radio'> vs <input type='checkbox'>.
A standalone <textarea> inside a task-body (not nested in any option label) marks
either a pure text question or a "Свой вариант" free-text field for option questions.
"""

from dataclasses import dataclass, field
from typing import Literal

import click
from playwright.sync_api import ElementHandle, Page

from openhunt import answers
from openhunt.answers import normalize
from openhunt.browser import selectors
from openhunt.browser.session import human_delay


@dataclass
class CollectResult:
    """Result of collect_and_fill(): which questions were filled, which are pending."""

    filled: bool                  # True if all questions were filled from memory
    pending: list["Question"] = field(default_factory=list)  # questions without answers

QuestionType = Literal[
    "text",
    "single_choice",
    "single_choice_other",
    "multi_choice",
    "multi_choice_other",
]

# Sentinel stored in answers.json to mean "the user chose the free-text branch
# of an *_other question". Filler resolves this to value='open' (synthetic
# radio) when present, or to the first option whose label looks like
# "Свой вариант" / "Другое". Storing the sentinel — instead of overloading the
# label of one specific option — keeps the answer portable across the two
# DOM variants of *_other we observed in recon.
OTHER_SENTINEL = "__OTHER__"


class QuestionnaireParseError(RuntimeError):
    """Raised when a task-body element has an unexpected structure.

    Failing closed on DOM drift is intentional: hh.ru changes its markup
    occasionally, and we'd rather abort the questionnaire flow with a clear
    message than guess at a partial answer and submit garbage.
    """


@dataclass
class QuestionOption:
    """One selectable option (radio or checkbox) inside a question."""

    text: str   # human-readable label (e.g. "Удаленка")
    value: str  # per-vacancy hh.ru option id (e.g. "322211230")


@dataclass
class Question:
    """A single question parsed from a questionnaire page.

    `input_name` is shared by all option inputs of this question (Playwright uses
    it to locate the radio/checkbox group). `text_input_name` is set when the
    question has a textarea — either as the only answer (`text`) or as a free-text
    fallback for `*_other` types. `has_open_radio` indicates the synthetic
    `value='open'` radio (which the parser hides from `options`).
    """

    text: str
    type: QuestionType
    options: list[QuestionOption] = field(default_factory=list)
    input_name: str | None = None
    text_input_name: str | None = None
    has_open_radio: bool = False

    @property
    def has_free_text(self) -> bool:
        return self.text_input_name is not None


# --- Parsing ---


def _parse_task_body(task_body: ElementHandle) -> Question:
    """Parse a single [data-qa='task-body'] element into a Question.

    Raises QuestionnaireParseError on any structural anomaly: missing question
    text, missing input attributes, mixed radio+checkbox in one task, or a
    task-body that has neither options nor a textarea. The caller decides how
    to surface the error to the user.
    """
    q_el = task_body.query_selector(selectors.QUESTIONNAIRE_QUESTION_TEXT)
    if not q_el:
        raise QuestionnaireParseError("task-body is missing question text element")
    text = q_el.inner_text().strip().replace("\xa0", " ")
    if not text:
        raise QuestionnaireParseError("task-body has empty question text")

    # Collect options from each label[data-qa='cell']
    options: list[QuestionOption] = []
    input_name: str | None = None
    input_type: str | None = None  # "radio" or "checkbox"
    has_open_radio = False  # special "Свой вариант" radio with value="open"

    for cell in task_body.query_selector_all(selectors.QUESTIONNAIRE_OPTION_CELL):
        inp = cell.query_selector("input[type='radio'], input[type='checkbox']")
        if not inp:
            # Cells without an input are presentation-only (separators, etc.)
            continue
        i_type = inp.get_attribute("type") or ""
        i_name = inp.get_attribute("name") or ""
        i_value = inp.get_attribute("value") or ""

        if not i_name:
            raise QuestionnaireParseError(
                f"option input in question {text!r} is missing the 'name' attribute"
            )
        if not i_value:
            raise QuestionnaireParseError(
                f"option input in question {text!r} is missing the 'value' attribute"
            )

        text_el = cell.query_selector(selectors.QUESTIONNAIRE_OPTION_TEXT)
        opt_text = text_el.inner_text().strip().replace("\xa0", " ") if text_el else ""

        # The synthetic value="open" radio marks an "other" free-text branch and
        # has no real option of its own — skip it but remember its presence.
        if i_value == "open":
            has_open_radio = True
            continue

        if input_name is None:
            input_name = i_name
            input_type = i_type
        else:
            # Defensive: hh.ru never mixes types in one question, but if it
            # ever does, we can't safely autofill — bail out loudly.
            if i_type != input_type:
                raise QuestionnaireParseError(
                    f"question {text!r} mixes radio and checkbox inputs"
                )
            if i_name != input_name:
                raise QuestionnaireParseError(
                    f"question {text!r} has options with different input names "
                    f"({input_name!r} vs {i_name!r})"
                )
        options.append(QuestionOption(text=opt_text, value=i_value))

    # Look for a textarea that is NOT inside any option label — that's the
    # free-text answer (either standalone "text" question or "*_other" branch).
    text_input_name: str | None = None
    for ta in task_body.query_selector_all("textarea"):
        in_cell = ta.evaluate("el => !!el.closest(\"[data-qa='cell']\")")
        if in_cell:
            continue
        ta_name = ta.get_attribute("name") or ""
        if not ta_name:
            raise QuestionnaireParseError(
                f"textarea in question {text!r} is missing the 'name' attribute"
            )
        text_input_name = ta_name
        break

    # Classify
    if not options:
        if text_input_name is None:
            raise QuestionnaireParseError(
                f"question {text!r} has neither options nor a textarea"
            )
        return Question(text=text, type="text", text_input_name=text_input_name)

    has_other = text_input_name is not None or has_open_radio
    if input_type == "checkbox":
        qtype: QuestionType = "multi_choice_other" if has_other else "multi_choice"
    else:
        qtype = "single_choice_other" if has_other else "single_choice"

    return Question(
        text=text,
        type=qtype,
        options=options,
        input_name=input_name,
        text_input_name=text_input_name,
        has_open_radio=has_open_radio,
    )


def extract_questions(page: Page) -> list[Question]:
    """Extract all questions from the current questionnaire page.

    Returns an empty list if the page is not a questionnaire (no container marker).
    Raises QuestionnaireParseError if the container is present but any task-body
    has an unrecognized structure — the caller should treat this as a hard skip
    of the vacancy and surface the error to the user.

    Note: hh.ru does NOT actually nest task-body elements inside the container —
    the container only holds the intro text. We use the container as a presence
    marker but search for tasks at the page level.
    """
    if not page.query_selector(selectors.QUESTIONNAIRE_CONTAINER):
        return []

    questions: list[Question] = []
    for tb in page.query_selector_all(selectors.QUESTIONNAIRE_TASK):
        questions.append(_parse_task_body(tb))
    return questions


def get_intro_text(page: Page) -> str:
    """Return the employer's intro text above the questions, or empty string."""
    el = page.query_selector(selectors.QUESTIONNAIRE_DESCRIPTION)
    if not el:
        return ""
    return el.inner_text().strip().replace("\xa0", " ")


# --- Option text matching (storage uses labels, not per-vacancy IDs) ---


def find_option_by_text(options: list[QuestionOption], wanted: str) -> QuestionOption | None:
    """Find the option whose text matches `wanted` (exact, then normalized)."""
    for o in options:
        if o.text == wanted:
            return o
    wanted_norm = normalize(wanted)
    for o in options:
        if normalize(o.text) == wanted_norm:
            return o
    return None


# --- Filling ---


class CannotFillError(Exception):
    """Raised when the saved answer cannot be applied to the current question
    (e.g. the stored option label is no longer present among current options)."""


def _check_input(page: Page, name: str, value: str) -> None:
    """Click the radio/checkbox input identified by name+value.

    Uses page.check() which is robust to overlay/visual wrappers.
    """
    page.check(f"input[name='{name}'][value='{value}']")
    human_delay(0.2, 0.4)


def _fill_textarea(page: Page, name: str, text: str) -> None:
    page.fill(f"textarea[name='{name}']", text)
    human_delay(0.2, 0.4)


def _click_other_branch(page: Page, question: Question) -> None:
    """Activate the "Свой вариант" / free-text branch of an *_other question.

    Resolution order:
      1. The synthetic value='open' radio (if hh.ru rendered one).
      2. The first option whose label looks like "Свой вариант" or "Другое".
      3. CannotFillError — we don't know which option to click.
    """
    if question.input_name is None:
        raise CannotFillError("question has no input name; cannot click 'other'")

    if question.has_open_radio:
        _check_input(page, question.input_name, "open")
        return

    for opt in question.options:
        low = opt.text.lower()
        if "свой" in low or "друг" in low:
            _check_input(page, question.input_name, opt.value)
            return

    raise CannotFillError(
        f"question {question.text!r} has no recognizable 'other' option"
    )


def _select_choice_option(page: Page, question: Question, wanted: str) -> None:
    """Click the option whose label matches `wanted`, or raise CannotFillError."""
    if question.input_name is None:
        raise CannotFillError("question has no input name")
    opt = find_option_by_text(question.options, wanted)
    if not opt:
        raise CannotFillError(
            f"option '{wanted}' not found among {[o.text for o in question.options]}"
        )
    _check_input(page, question.input_name, opt.value)


def apply_answer(page: Page, question: Question, answer: dict) -> None:
    """Apply a stored/just-asked answer payload to the question on the page.

    Raises CannotFillError if the answer cannot be mapped to current options
    (e.g. options have changed since the answer was saved). The OTHER_SENTINEL
    value (in `option` or inside `options`) means "use the question's free-text
    branch" — see `_click_other_branch`.
    """
    qtype = question.type

    if qtype == "text":
        text = answer.get("text", "")
        if question.text_input_name:
            _fill_textarea(page, question.text_input_name, text)
        return

    if qtype in ("single_choice", "single_choice_other"):
        wanted = answer.get("option")
        if not wanted:
            raise CannotFillError("missing 'option' in answer")
        if wanted == OTHER_SENTINEL:
            if qtype != "single_choice_other":
                raise CannotFillError(
                    "OTHER sentinel used for a question without an 'other' branch"
                )
            _click_other_branch(page, question)
        else:
            _select_choice_option(page, question, wanted)

        free_text = answer.get("free_text")
        if free_text and question.text_input_name:
            _fill_textarea(page, question.text_input_name, free_text)
        return

    if qtype in ("multi_choice", "multi_choice_other"):
        wanted_list = answer.get("options", [])
        if not isinstance(wanted_list, list):
            raise CannotFillError("'options' must be a list")
        if question.input_name is None:
            raise CannotFillError("question has no input name")

        for wanted in wanted_list:
            if wanted == OTHER_SENTINEL:
                if qtype != "multi_choice_other":
                    raise CannotFillError(
                        "OTHER sentinel used for a question without an 'other' branch"
                    )
                _click_other_branch(page, question)
            else:
                _select_choice_option(page, question, wanted)

        free_text = answer.get("free_text")
        if free_text and question.text_input_name:
            _fill_textarea(page, question.text_input_name, free_text)
        return

    raise CannotFillError(f"unknown question type: {qtype}")


# --- Interactive ask ---


def _ask_text(question: Question) -> dict:
    answer = click.prompt("  Ваш ответ", type=str)
    return {"text": answer.strip()}


def _print_options(options: list[QuestionOption]) -> None:
    for i, o in enumerate(options, 1):
        click.echo(f"    {i}. {o.text}")


def _ask_single(question: Question) -> dict:
    _print_options(question.options)
    while True:
        raw = click.prompt("  Номер опции", type=str).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(question.options):
            chosen = question.options[int(raw) - 1]
            return {"option": chosen.text}
        click.echo("  Введите число от 1 до %d." % len(question.options))


def _ask_single_other(question: Question) -> dict:
    _print_options(question.options)
    n = len(question.options)
    other_idx = n + 1
    click.echo(f"    {other_idx}. Свой вариант (со своим текстом)")
    while True:
        raw = click.prompt("  Номер опции", type=str).strip()
        if not raw.isdigit():
            click.echo("  Введите число.")
            continue
        idx = int(raw)
        if 1 <= idx <= n:
            return {"option": question.options[idx - 1].text}
        if idx == other_idx:
            free = click.prompt("  Свой вариант (текст)", type=str).strip()
            # Store the OTHER_SENTINEL — filler resolves it to the right
            # control at fill time (value='open' or matching label).
            return {"option": OTHER_SENTINEL, "free_text": free}
        click.echo(f"  Введите число от 1 до {other_idx}.")


def _parse_indices(raw: str, n: int) -> list[int] | None:
    """Parse '1,3,4' or '1 3 4' into a list of 1-based indices, or None on error."""
    parts = raw.replace(",", " ").split()
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if not nums or any(i < 1 or i > n for i in nums):
        return None
    return nums


def _ask_multi(question: Question) -> dict:
    _print_options(question.options)
    while True:
        raw = click.prompt("  Номера опций (через запятую)", type=str).strip()
        idxs = _parse_indices(raw, len(question.options))
        if idxs is None:
            click.echo(f"  Введите числа от 1 до {len(question.options)} через запятую.")
            continue
        chosen = [question.options[i - 1].text for i in idxs]
        return {"options": chosen}


def _ask_multi_other(question: Question) -> dict:
    _print_options(question.options)
    while True:
        raw = click.prompt(
            "  Номера опций (через запятую, Enter если только свой вариант)",
            type=str,
            default="",
        ).strip()
        if raw:
            idxs = _parse_indices(raw, len(question.options))
            if idxs is None:
                click.echo(f"  Введите числа от 1 до {len(question.options)} через запятую.")
                continue
            chosen: list[str] = [question.options[i - 1].text for i in idxs]
        else:
            chosen = []
        free = click.prompt("  Дополнительный текст (Enter если не нужен)", type=str, default="").strip()
        result: dict = {"options": chosen}
        if free:
            # Append the OTHER_SENTINEL so the filler also clicks the
            # value='open'/"Свой вариант" control, not just the listed options.
            result["options"] = [*chosen, OTHER_SENTINEL]
            result["free_text"] = free
        return result


def ask_user_for_answer(question: Question) -> dict:
    """Interactively prompt the user for an answer to the given question."""
    click.echo(f"\n  ❓ {question.text}")
    if question.type == "text":
        return _ask_text(question)
    if question.type == "single_choice":
        return _ask_single(question)
    if question.type == "single_choice_other":
        return _ask_single_other(question)
    if question.type == "multi_choice":
        return _ask_multi(question)
    if question.type == "multi_choice_other":
        return _ask_multi_other(question)
    raise CannotFillError(f"unknown question type: {question.type}")


def ask_offline_answer(record: dict) -> dict:
    """Prompt the user for an answer to a question stored in memory (no browser).

    Constructs a lightweight Question from the stored record and reuses the
    same interactive prompting logic as ``ask_user_for_answer``.
    """
    stored_options = record.get("options") or []
    q = Question(
        text=record["text"],
        type=record["type"],
        options=[QuestionOption(text=o["text"], value="") for o in stored_options],
    )
    return ask_user_for_answer(q)


# --- Submit ---


def submit_questionnaire(page: Page) -> bool:
    """Click the submit button and check for the post-apply success state.

    Returns True on success, False otherwise.
    """
    btn = page.query_selector(selectors.QUESTIONNAIRE_SUBMIT)
    if not btn:
        click.echo("  ! Кнопка отправки анкеты не найдена.")
        return False
    btn.click()
    human_delay(1.5, 2.5)

    # Success indicators are the same as for the regular response popup.
    success = (
        page.get_by_text(selectors.RESPONSE_DELIVERED_TEXT, exact=True)
        .or_(page.get_by_text(selectors.RESPONSE_SENT_TEXT, exact=True))
    )
    try:
        success.first.wait_for(state="visible", timeout=5000)
        return True
    except Exception:
        return False


# --- Main flow ---


def fill_questionnaire(page: Page, interactive: bool = True) -> bool:
    """Fill the entire questionnaire on the current page.

    For each question:
      1. Look up an answer in memory; if found, apply it.
      2. Otherwise, if interactive=True, ask the user, save the answer, apply it.
      3. If interactive=False and no answer is in memory, return False (skip).

    If a stored answer fails to apply (option labels changed), falls back to
    asking the user (when interactive) or returns False.

    Does NOT submit — call submit_questionnaire() separately so the caller can
    add a confirmation step or dry-run.
    """
    questions = extract_questions(page)
    if not questions:
        click.echo("  ! Анкета не найдена на странице.")
        return False

    intro = get_intro_text(page)
    if intro:
        click.echo(f"  Вопросы от работодателя ({len(questions)} шт.):")

    for i, q in enumerate(questions, 1):
        click.echo(f"\n  [{i}/{len(questions)}] {q.text[:100]}")
        record = answers.find_answer(q.text)

        # Stored type must match — otherwise re-ask (option set may have changed entirely).
        if record and record.get("type") == q.type:
            try:
                apply_answer(page, q, record["answer"])
                answers.touch_used(record["id"])
                click.echo("    ✓ из памяти")
                continue
            except CannotFillError as e:
                click.echo(f"    ! сохранённый ответ не подошёл: {e}")
                if not interactive:
                    return False

        if not interactive:
            click.echo("    ~ нет сохранённого ответа, пропуск")
            return False

        new_answer = ask_user_for_answer(q)
        try:
            apply_answer(page, q, new_answer)
        except CannotFillError as e:
            click.echo(f"    ! не удалось заполнить: {e}")
            return False
        answers.save_answer(q.text, q.type, new_answer)
        click.echo("    ✓ сохранено в память")

    return True


def _options_for_storage(q: Question) -> list[dict] | None:
    """Convert Question options to the storage format for answers.json."""
    if not q.options:
        return None
    return [{"text": o.text} for o in q.options]


def collect_and_fill(page: Page) -> CollectResult:
    """Parse questions, fill from memory if possible, save pending ones.

    Never prompts the user. Returns a CollectResult indicating whether all
    questions were filled (caller should submit) or some are pending (caller
    should skip the vacancy).
    """
    questions = extract_questions(page)
    if not questions:
        click.echo("  ! Анкета не найдена на странице.")
        return CollectResult(filled=False)

    intro = get_intro_text(page)
    if intro:
        click.echo(f"  Вопросы от работодателя ({len(questions)} шт.):")

    pending: list[Question] = []

    for i, q in enumerate(questions, 1):
        click.echo(f"\n  [{i}/{len(questions)}] {q.text[:100]}")
        record = answers.find_answer(q.text)

        if record and record.get("answer") is not None and record.get("type") == q.type:
            try:
                apply_answer(page, q, record["answer"])
                answers.touch_used(record["id"])
                click.echo("    ✓ из памяти")
                continue
            except CannotFillError as e:
                click.echo(f"    ! сохранённый ответ не подошёл: {e}")

        # No usable answer — save as pending and continue parsing the rest.
        answers.save_pending(q.text, q.type, options=_options_for_storage(q))
        pending.append(q)
        click.echo("    ~ сохранён для ответа позже")

    if pending:
        return CollectResult(filled=False, pending=pending)
    return CollectResult(filled=True)
