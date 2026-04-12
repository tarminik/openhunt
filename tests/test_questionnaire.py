"""Tests for the questionnaire parser.

Uses real Playwright on synthetic HTML strings (no network) so the parser is
exercised against the same DOM API it sees in production.
"""

import pytest
from playwright.sync_api import sync_playwright

from openhunt.browser.actions.questionnaire import (
    OTHER_SENTINEL,
    CannotFillError,
    CollectResult,
    Question,
    QuestionnaireParseError,
    QuestionOption,
    apply_answer,
    ask_offline_answer,
    collect_and_fill,
    extract_questions,
    find_option_by_text,
    get_intro_text,
)


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        p = ctx.new_page()
        p.set_default_timeout(5000)
        yield p
        browser.close()


def _render(page, body_html: str) -> None:
    """Wrap fragment in a minimal page and load it via set_content."""
    page.set_content(
        "<!doctype html><html><body>"
        '<div data-qa="employer-asking-for-test">'
        '<div data-qa="test-description">Привет! Ответь, пожалуйста.</div>'
        "</div>"
        + body_html
        + "</body></html>"
    )


def _option_cell(name: str, value: str, label: str, input_type: str) -> str:
    return (
        '<label data-qa="cell">'
        f'<input type="{input_type}" name="{name}" value="{value}">'
        f'<span data-qa="cell-text-content">{label}</span>'
        "</label>"
    )


# --- presence / absence ---


def test_no_container_returns_empty(page):
    page.set_content("<html><body><p>vacancy page</p></body></html>")
    assert extract_questions(page) == []


def test_intro_text_extracted(page):
    _render(page, "")
    assert "Привет" in get_intro_text(page)


def test_container_without_questions(page):
    _render(page, "")
    assert extract_questions(page) == []


# --- single_choice ---


def test_single_choice_basic(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Сколько лет опыта?</div>'
        + _option_cell("task_1", "v1", "1-3", "radio")
        + _option_cell("task_1", "v2", "3-5", "radio")
        + _option_cell("task_1", "v3", "5+", "radio")
        + "</div>",
    )
    qs = extract_questions(page)
    assert len(qs) == 1
    q = qs[0]
    assert q.type == "single_choice"
    assert q.text == "Сколько лет опыта?"
    assert q.input_name == "task_1"
    assert q.text_input_name is None
    assert [(o.text, o.value) for o in q.options] == [("1-3", "v1"), ("3-5", "v2"), ("5+", "v3")]


# --- multi_choice ---


def test_multi_choice_basic(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Что использовал?</div>'
        + _option_cell("task_2", "a", "Django", "checkbox")
        + _option_cell("task_2", "b", "FastAPI", "checkbox")
        + "</div>",
    )
    qs = extract_questions(page)
    assert len(qs) == 1
    assert qs[0].type == "multi_choice"
    assert qs[0].input_name == "task_2"
    assert [o.text for o in qs[0].options] == ["Django", "FastAPI"]


# --- text ---


def test_text_question(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Зарплатные ожидания?</div>'
        '<textarea name="task_3_text"></textarea>'
        "</div>",
    )
    qs = extract_questions(page)
    assert len(qs) == 1
    assert qs[0].type == "text"
    assert qs[0].input_name is None
    assert qs[0].text_input_name == "task_3_text"
    assert qs[0].options == []


# --- single_choice_other ---


def test_single_choice_other_with_open_radio(page):
    """The synthetic value='open' radio should be skipped from options but mark
    the question as 'other'."""
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Готов?</div>'
        + _option_cell("task_4", "v1", "Да", "radio")
        + _option_cell("task_4", "v2", "Нет", "radio")
        + _option_cell("task_4", "open", "Свой вариант", "radio")
        + '<textarea name="task_4_text"></textarea>'
        "</div>",
    )
    qs = extract_questions(page)
    assert len(qs) == 1
    q = qs[0]
    assert q.type == "single_choice_other"
    # value="open" must NOT appear in options
    assert [o.text for o in q.options] == ["Да", "Нет"]
    assert q.text_input_name == "task_4_text"


def test_single_choice_other_without_open_radio(page):
    """A textarea alongside radio options is enough to mark the question as 'other'."""
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Город?</div>'
        + _option_cell("task_5", "v1", "Москва", "radio")
        + _option_cell("task_5", "v2", "Свой вариант", "radio")
        + '<textarea name="task_5_text"></textarea>'
        "</div>",
    )
    q = extract_questions(page)[0]
    assert q.type == "single_choice_other"
    assert [o.text for o in q.options] == ["Москва", "Свой вариант"]
    assert q.text_input_name == "task_5_text"


# --- multi_choice_other ---


def test_multi_choice_other(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Формат?</div>'
        + _option_cell("task_6", "v1", "ГПХ", "checkbox")
        + _option_cell("task_6", "v2", "ТД", "checkbox")
        + '<textarea name="task_6_text"></textarea>'
        "</div>",
    )
    q = extract_questions(page)[0]
    assert q.type == "multi_choice_other"
    assert q.input_name == "task_6"
    assert q.text_input_name == "task_6_text"
    assert [o.text for o in q.options] == ["ГПХ", "ТД"]


# --- multiple questions ---


def test_multiple_questions_mixed_types(page):
    body = (
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Опыт более 5 лет?</div>'
        + _option_cell("task_a", "1", "да", "radio")
        + _option_cell("task_a", "2", "нет", "radio")
        + "</div>"
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Зарплата?</div>'
        '<textarea name="task_b_text"></textarea>'
        "</div>"
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Стек?</div>'
        + _option_cell("task_c", "p", "Python", "checkbox")
        + _option_cell("task_c", "g", "Go", "checkbox")
        + "</div>"
    )
    _render(page, body)
    qs = extract_questions(page)
    assert [q.type for q in qs] == ["single_choice", "text", "multi_choice"]
    assert [q.text for q in qs] == ["Опыт более 5 лет?", "Зарплата?", "Стек?"]


def test_question_text_strips_nbsp(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Опыт\xa0Python\xa0более\xa05?</div>'
        + _option_cell("task_x", "1", "да", "radio")
        + "</div>",
    )
    q = extract_questions(page)[0]
    assert "\xa0" not in q.text
    assert q.text == "Опыт Python более 5?"


# --- find_option_by_text ---


def test_find_option_exact():
    options = [QuestionOption("Удаленка", "v1"), QuestionOption("Офис", "v2")]
    assert find_option_by_text(options, "Удаленка").value == "v1"


def test_find_option_normalized_match():
    options = [QuestionOption("Удаленка", "v1"), QuestionOption("Офис", "v2")]
    assert find_option_by_text(options, "удаленка!").value == "v1"


def test_find_option_missing():
    options = [QuestionOption("Удаленка", "v1")]
    assert find_option_by_text(options, "Гибрид") is None


# --- has_open_radio flag ---


def test_has_open_radio_set_when_synthetic_open_present(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Готов?</div>'
        + _option_cell("task_x", "v1", "Да", "radio")
        + _option_cell("task_x", "open", "Свой вариант", "radio")
        + '<textarea name="task_x_text"></textarea>'
        "</div>",
    )
    q = extract_questions(page)[0]
    assert q.type == "single_choice_other"
    assert q.has_open_radio is True


def test_has_open_radio_false_for_textarea_only_other(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Город?</div>'
        + _option_cell("task_y", "v1", "Москва", "radio")
        + _option_cell("task_y", "v2", "Свой вариант", "radio")
        + '<textarea name="task_y_text"></textarea>'
        "</div>",
    )
    q = extract_questions(page)[0]
    assert q.has_open_radio is False


# --- Parser fail-closed (DOM drift / structural anomalies) ---


def test_parse_error_missing_question_text(page):
    _render(page, '<div data-qa="task-body"></div>')
    with pytest.raises(QuestionnaireParseError, match="missing question text"):
        extract_questions(page)


def test_parse_error_empty_question_text(page):
    _render(
        page,
        '<div data-qa="task-body"><div data-qa="task-question"> </div></div>',
    )
    with pytest.raises(QuestionnaireParseError, match="empty question text"):
        extract_questions(page)


def test_parse_error_input_missing_name(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Q?</div>'
        '<label data-qa="cell">'
        '<input type="radio" value="v1">'
        '<span data-qa="cell-text-content">A</span>'
        "</label>"
        "</div>",
    )
    with pytest.raises(QuestionnaireParseError, match="missing the 'name' attribute"):
        extract_questions(page)


def test_parse_error_input_missing_value(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Q?</div>'
        '<label data-qa="cell">'
        '<input type="radio" name="task_z">'
        '<span data-qa="cell-text-content">A</span>'
        "</label>"
        "</div>",
    )
    with pytest.raises(QuestionnaireParseError, match="missing the 'value' attribute"):
        extract_questions(page)


def test_parse_error_mixed_radio_checkbox(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Q?</div>'
        + _option_cell("task_m", "v1", "A", "radio")
        + _option_cell("task_m", "v2", "B", "checkbox")
        + "</div>",
    )
    with pytest.raises(QuestionnaireParseError, match="mixes radio and checkbox"):
        extract_questions(page)


def test_parse_error_no_options_no_textarea(page):
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Q?</div>'
        '<p>some unrelated content</p>'
        "</div>",
    )
    with pytest.raises(QuestionnaireParseError, match="neither options nor"):
        extract_questions(page)


# --- apply_answer with OTHER_SENTINEL (filler logic) ---


def test_apply_answer_text_via_real_dom(page):
    page.set_content(
        "<html><body>"
        '<textarea name="task_t_text"></textarea>'
        "</body></html>"
    )
    q = Question(text="Q?", type="text", text_input_name="task_t_text")
    apply_answer(page, q, {"text": "hello world"})
    val = page.eval_on_selector("textarea[name='task_t_text']", "el => el.value")
    assert val == "hello world"


def test_apply_answer_single_choice_clicks_right_radio(page):
    page.set_content(
        "<html><body><form>"
        '<input type="radio" name="task_s" value="v1">'
        '<input type="radio" name="task_s" value="v2">'
        '<input type="radio" name="task_s" value="v3">'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="single_choice",
        options=[
            QuestionOption("A", "v1"),
            QuestionOption("B", "v2"),
            QuestionOption("C", "v3"),
        ],
        input_name="task_s",
    )
    apply_answer(page, q, {"option": "B"})
    checked = page.eval_on_selector_all(
        "input[name='task_s']",
        "els => els.find(e => e.checked)?.value",
    )
    assert checked == "v2"


def test_apply_answer_other_sentinel_uses_open_radio(page):
    """When the synthetic value='open' radio exists, sentinel must click IT,
    not any of the labelled options."""
    page.set_content(
        "<html><body><form>"
        '<input type="radio" name="task_o" value="v1">'
        '<input type="radio" name="task_o" value="v2">'
        '<input type="radio" name="task_o" value="open">'
        '<textarea name="task_o_text"></textarea>'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="single_choice_other",
        options=[QuestionOption("Да", "v1"), QuestionOption("Нет", "v2")],
        input_name="task_o",
        text_input_name="task_o_text",
        has_open_radio=True,
    )
    apply_answer(page, q, {"option": OTHER_SENTINEL, "free_text": "мой ответ"})

    checked = page.eval_on_selector_all(
        "input[name='task_o']",
        "els => els.find(e => e.checked)?.value",
    )
    assert checked == "open"
    val = page.eval_on_selector("textarea[name='task_o_text']", "el => el.value")
    assert val == "мой ответ"


def test_apply_answer_other_sentinel_falls_back_to_labelled_other(page):
    """Without value='open', the sentinel must resolve to the option whose
    label contains 'свой' or 'друг'."""
    page.set_content(
        "<html><body><form>"
        '<input type="radio" name="task_p" value="v1">'
        '<input type="radio" name="task_p" value="v2">'
        '<textarea name="task_p_text"></textarea>'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="single_choice_other",
        options=[
            QuestionOption("Москва", "v1"),
            QuestionOption("Свой вариант", "v2"),
        ],
        input_name="task_p",
        text_input_name="task_p_text",
        has_open_radio=False,
    )
    apply_answer(page, q, {"option": OTHER_SENTINEL, "free_text": "Берлин"})

    checked = page.eval_on_selector_all(
        "input[name='task_p']",
        "els => els.find(e => e.checked)?.value",
    )
    assert checked == "v2"
    val = page.eval_on_selector("textarea[name='task_p_text']", "el => el.value")
    assert val == "Берлин"


def test_apply_answer_other_sentinel_fails_when_no_other_option(page):
    page.set_content(
        "<html><body><form>"
        '<input type="radio" name="task_q" value="v1">'
        '<input type="radio" name="task_q" value="v2">'
        '<textarea name="task_q_text"></textarea>'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="single_choice_other",
        options=[QuestionOption("Да", "v1"), QuestionOption("Нет", "v2")],
        input_name="task_q",
        text_input_name="task_q_text",
        has_open_radio=False,
    )
    with pytest.raises(CannotFillError, match="no recognizable 'other'"):
        apply_answer(page, q, {"option": OTHER_SENTINEL, "free_text": "x"})


def test_apply_answer_sentinel_rejected_for_non_other_question(page):
    """Storing OTHER_SENTINEL for a plain single_choice question is a bug —
    filler must refuse rather than guess."""
    page.set_content(
        "<html><body><form>"
        '<input type="radio" name="task_r" value="v1">'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="single_choice",
        options=[QuestionOption("A", "v1")],
        input_name="task_r",
    )
    with pytest.raises(CannotFillError, match="OTHER sentinel"):
        apply_answer(page, q, {"option": OTHER_SENTINEL})


def test_apply_answer_multi_choice_with_sentinel(page):
    page.set_content(
        "<html><body><form>"
        '<input type="checkbox" name="task_mc" value="v1">'
        '<input type="checkbox" name="task_mc" value="v2">'
        '<input type="checkbox" name="task_mc" value="open">'
        '<textarea name="task_mc_text"></textarea>'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="multi_choice_other",
        options=[QuestionOption("ГПХ", "v1"), QuestionOption("ТД", "v2")],
        input_name="task_mc",
        text_input_name="task_mc_text",
        has_open_radio=True,
    )
    apply_answer(
        page,
        q,
        {"options": ["ГПХ", OTHER_SENTINEL], "free_text": "ИП"},
    )
    checked_values = set(
        page.eval_on_selector_all(
            "input[name='task_mc']",
            "els => els.filter(e => e.checked).map(e => e.value)",
        )
    )
    assert checked_values == {"v1", "open"}
    val = page.eval_on_selector("textarea[name='task_mc_text']", "el => el.value")
    assert val == "ИП"


def test_apply_answer_missing_option_raises(page):
    page.set_content(
        "<html><body><form>"
        '<input type="radio" name="task_m" value="v1">'
        "</form></body></html>"
    )
    q = Question(
        text="Q?",
        type="single_choice",
        options=[QuestionOption("A", "v1")],
        input_name="task_m",
    )
    with pytest.raises(CannotFillError, match="not found"):
        apply_answer(page, q, {"option": "B"})


# --- collect_and_fill ---


def _render_single_choice_questionnaire(page):
    """Render a simple questionnaire with one single-choice question."""
    _render(
        page,
        '<div data-qa="task-body">'
        '<div data-qa="task-question">Формат работы?</div>'
        + _option_cell("q1", "v1", "Удаленка", "radio")
        + _option_cell("q1", "v2", "Офис", "radio")
        + "</div>",
    )


def test_collect_and_fill_all_answered(page, tmp_path, monkeypatch):
    """When all answers are in memory, collect_and_fill fills and returns filled=True."""
    monkeypatch.setattr("openhunt.answers.ANSWERS_PATH", tmp_path / "answers.json")
    from openhunt.answers import save_answer

    save_answer("Формат работы?", "single_choice", {"option": "Удаленка"})
    _render_single_choice_questionnaire(page)

    result = collect_and_fill(page)
    assert result.filled is True
    assert result.pending == []
    # Verify the radio was actually checked
    checked = page.eval_on_selector("input[name='q1'][value='v1']", "el => el.checked")
    assert checked is True


def test_collect_and_fill_saves_pending(page, tmp_path, monkeypatch):
    """When no answer in memory, saves pending and returns filled=False."""
    monkeypatch.setattr("openhunt.answers.ANSWERS_PATH", tmp_path / "answers.json")
    _render_single_choice_questionnaire(page)

    result = collect_and_fill(page)
    assert result.filled is False
    assert len(result.pending) == 1
    assert result.pending[0].text == "Формат работы?"

    # Verify it was saved to memory as pending
    from openhunt.answers import list_pending

    pending = list_pending()
    assert len(pending) == 1
    assert pending[0]["answer"] is None
    assert pending[0]["options"] == [{"text": "Удаленка"}, {"text": "Офис"}]


def test_collect_and_fill_stale_answer_saves_pending(page, tmp_path, monkeypatch):
    """When stored answer doesn't match options, saves as pending."""
    monkeypatch.setattr("openhunt.answers.ANSWERS_PATH", tmp_path / "answers.json")
    from openhunt.answers import save_answer

    # Save an answer with an option that doesn't exist on this page
    save_answer("Формат работы?", "single_choice", {"option": "Гибрид"})
    _render_single_choice_questionnaire(page)

    result = collect_and_fill(page)
    assert result.filled is False
    assert len(result.pending) == 1


def test_collect_and_fill_no_container(page, tmp_path, monkeypatch):
    """When page has no questionnaire, returns filled=False with no pending."""
    monkeypatch.setattr("openhunt.answers.ANSWERS_PATH", tmp_path / "answers.json")
    page.set_content("<html><body><p>not a questionnaire</p></body></html>")

    result = collect_and_fill(page)
    assert result.filled is False
    assert result.pending == []


# --- ask_offline_answer ---


def test_ask_offline_answer_text(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "Пять лет")
    record = {"text": "Сколько лет опыта?", "type": "text", "options": []}
    answer = ask_offline_answer(record)
    assert answer == {"text": "Пять лет"}


def test_ask_offline_answer_single_choice(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "1")
    record = {
        "text": "Формат?",
        "type": "single_choice",
        "options": [{"text": "Удаленка"}, {"text": "Офис"}],
    }
    answer = ask_offline_answer(record)
    assert answer == {"option": "Удаленка"}
