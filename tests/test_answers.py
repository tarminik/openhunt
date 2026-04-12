"""Tests for the answers (questionnaire memory) storage."""

import json

import pytest

from openhunt.answers import (
    CorruptAnswersFileError,
    SCHEMA_VERSION,
    delete_answer,
    find_answer,
    list_answered,
    list_answers,
    list_pending,
    normalize,
    question_id,
    save_answer,
    save_pending,
    touch_used,
)


@pytest.fixture(autouse=True)
def isolated_answers(tmp_path, monkeypatch):
    """Redirect answers.json to a temp file for each test."""
    fake_path = tmp_path / "memory" / "answers.json"
    monkeypatch.setattr("openhunt.answers.ANSWERS_PATH", fake_path)


# --- normalize ---


def test_normalize_lowercase_and_punct():
    assert normalize("Какой формат работы?") == "какой формат работы"


def test_normalize_collapses_whitespace_and_nbsp():
    # \xa0 is the non-breaking space hh.ru loves to use
    assert normalize("Опыт\xa0с  Python\t\nболее\xa05 лет?") == "опыт с python более 5 лет"


def test_normalize_strips_quotes_and_dashes():
    assert normalize('Зарплата – «комфорт» (минимум).') == "зарплата комфорт минимум"


def test_normalize_idempotent():
    once = normalize("Сколько лет опыта??")
    assert normalize(once) == once


# --- question_id ---


def test_question_id_stable_for_same_input():
    a = question_id(normalize("Какой формат работы?"))
    b = question_id(normalize("Какой формат работы?"))
    assert a == b
    assert a.startswith("q_")


def test_question_id_differs_for_different_questions():
    a = question_id(normalize("Какой формат работы?"))
    b = question_id(normalize("Какой опыт работы?"))
    assert a != b


# --- save / find ---


def test_find_empty():
    assert find_answer("Anything?") is None


def test_save_and_find_exact():
    save_answer("Сколько лет опыта?", "text", {"text": "5"})
    record = find_answer("Сколько лет опыта?")
    assert record is not None
    assert record["answer"] == {"text": "5"}
    assert record["type"] == "text"
    assert record["used_count"] == 1


def test_find_normalized_match():
    """A trivially-different surface form should still match the stored entry."""
    save_answer("Сколько лет опыта?", "text", {"text": "5"})
    # Different punctuation, casing, NBSP — same normalized form
    record = find_answer("СКОЛЬКО\xa0лет опыта?!")
    assert record is not None
    assert record["answer"] == {"text": "5"}


def test_save_overwrites_and_increments_used_count():
    save_answer("Q1?", "text", {"text": "first"})
    save_answer("Q1?", "text", {"text": "second"})
    record = find_answer("Q1?")
    assert record["answer"] == {"text": "second"}
    assert record["used_count"] == 2


def test_save_choice_answer():
    save_answer(
        "Какой формат работы?",
        "single_choice",
        {"option": "Удаленка"},
    )
    record = find_answer("Какой формат работы?")
    assert record["type"] == "single_choice"
    assert record["answer"] == {"option": "Удаленка"}


def test_save_multi_choice_with_other():
    save_answer(
        "Какой опыт?",
        "multi_choice_other",
        {"options": ["Веб", "Мобильные"], "free_text": "ещё немного embedded"},
    )
    record = find_answer("Какой опыт?")
    assert record["type"] == "multi_choice_other"
    assert record["answer"]["options"] == ["Веб", "Мобильные"]
    assert record["answer"]["free_text"] == "ещё немного embedded"


# --- list / delete / touch ---


def test_list_answers_orders_newest_first():
    save_answer("Q1?", "text", {"text": "a"})
    save_answer("Q2?", "text", {"text": "b"})
    save_answer("Q3?", "text", {"text": "c"})
    records = list_answers()
    assert [r["text"] for r in records[:3]] == ["Q3?", "Q2?", "Q1?"]


def test_delete_answer():
    save_answer("Q1?", "text", {"text": "a"})
    record = find_answer("Q1?")
    assert delete_answer(record["id"]) is True
    assert find_answer("Q1?") is None
    assert delete_answer(record["id"]) is False  # already gone


def test_touch_used_increments():
    save_answer("Q1?", "text", {"text": "a"})
    record = find_answer("Q1?")
    qid = record["id"]
    touch_used(qid)
    touch_used(qid)
    assert find_answer("Q1?")["used_count"] == 3  # 1 from save + 2 touches


def test_touch_used_unknown_is_noop():
    touch_used("q_does_not_exist")  # must not raise


# --- persistence across "loads" ---


def test_data_persists_across_loads(tmp_path, monkeypatch):
    save_answer("Q1?", "text", {"text": "first"})
    # Re-import and re-load by reaching into a fresh find call
    record = find_answer("Q1?")
    assert record["answer"]["text"] == "first"


# --- Schema validation / corrupt file handling ---


def _path():
    """Helper: return the current ANSWERS_PATH (after monkeypatch)."""
    from openhunt import answers as a
    return a.ANSWERS_PATH


def test_corrupt_json_is_quarantined_and_db_is_empty():
    """A truncated JSON should be moved aside and treated as a fresh empty DB."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json")

    # Find triggers _load → _quarantine_corrupt
    assert find_answer("anything") is None
    # Original file is gone, a .corrupt-* sibling exists
    assert not p.exists()
    siblings = list(p.parent.glob(f"{p.name}.corrupt-*"))
    assert len(siblings) == 1


def test_unsupported_schema_version_is_fatal():
    """An unknown schema version must NOT be silently overwritten."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"version": 999, "questions": {}}))

    with pytest.raises(CorruptAnswersFileError):
        find_answer("anything")
    # File preserved (not quarantined) so the user can downgrade or migrate
    assert p.exists()


def test_top_level_not_object_is_quarantined():
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([1, 2, 3]))

    assert find_answer("anything") is None
    assert not p.exists()


def test_questions_field_wrong_type_is_quarantined():
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"version": SCHEMA_VERSION, "questions": "oops"}))

    assert find_answer("anything") is None
    assert not p.exists()


def test_save_after_quarantine_creates_fresh_file():
    """After a corrupt file is moved aside, save_answer should write a clean DB."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("garbage")

    save_answer("Q1?", "text", {"text": "hello"})
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["version"] == SCHEMA_VERSION
    assert any(r["text"] == "Q1?" for r in data["questions"].values())


def test_atomic_write_no_temp_file_left_behind():
    """After save, no .tmp.* file should remain in the parent directory."""
    save_answer("Q1?", "text", {"text": "hi"})
    p = _path()
    leftovers = [f.name for f in p.parent.glob(f"{p.name}.tmp.*")]
    assert leftovers == []


# --- save_pending ---


def test_save_pending_creates_record_without_answer():
    record = save_pending("Сколько лет опыта?", "text")
    assert record["answer"] is None
    assert record["type"] == "text"
    assert record["used_count"] == 0


def test_save_pending_with_options():
    record = save_pending(
        "Формат работы?",
        "single_choice",
        options=[{"text": "Удаленка"}, {"text": "Офис"}],
    )
    assert record["answer"] is None
    assert record["options"] == [{"text": "Удаленка"}, {"text": "Офис"}]


def test_save_pending_does_not_overwrite_existing_answer():
    save_answer("Q1?", "text", {"text": "hello"})
    record = save_pending("Q1?", "text")
    assert record["answer"] == {"text": "hello"}


def test_save_pending_updates_options_on_existing_pending():
    save_pending("Q1?", "single_choice", options=[{"text": "A"}])
    record = save_pending("Q1?", "single_choice", options=[{"text": "A"}, {"text": "B"}])
    assert record["options"] == [{"text": "A"}, {"text": "B"}]


def test_save_pending_keeps_richer_options():
    """If existing pending has more options, don't replace with fewer."""
    save_pending("Q1?", "single_choice", options=[{"text": "A"}, {"text": "B"}, {"text": "C"}])
    record = save_pending("Q1?", "single_choice", options=[{"text": "A"}])
    assert len(record.get("options", [])) == 3


def test_save_pending_persists():
    save_pending("Q1?", "text")
    record = find_answer("Q1?")
    # find_answer returns records regardless of answer state
    assert record is not None
    assert record["answer"] is None


# --- list_pending / list_answered ---


def test_list_pending_returns_only_unanswered():
    save_pending("Pending1?", "text")
    save_pending("Pending2?", "text")
    save_answer("Answered?", "text", {"text": "yes"})
    pending = list_pending()
    assert len(pending) == 2
    assert all(r["answer"] is None for r in pending)


def test_list_pending_oldest_first():
    save_pending("First?", "text")
    save_pending("Second?", "text")
    pending = list_pending()
    assert pending[0]["text"] == "First?"
    assert pending[1]["text"] == "Second?"


def test_list_answered_returns_only_answered():
    save_pending("Pending?", "text")
    save_answer("Answered1?", "text", {"text": "a"})
    save_answer("Answered2?", "text", {"text": "b"})
    answered = list_answered()
    assert len(answered) == 2
    assert all(r["answer"] is not None for r in answered)


def test_list_answered_newest_first():
    save_answer("First?", "text", {"text": "a"})
    save_answer("Second?", "text", {"text": "b"})
    answered = list_answered()
    assert answered[0]["text"] == "Second?"
    assert answered[1]["text"] == "First?"


# --- source field ---


def test_save_answer_with_source():
    record = save_answer("Q1?", "text", {"text": "hi"}, source="llm")
    assert record["source"] == "llm"


def test_save_answer_with_options():
    record = save_answer(
        "Q1?", "single_choice", {"option": "A"},
        options=[{"text": "A"}, {"text": "B"}],
    )
    assert record["options"] == [{"text": "A"}, {"text": "B"}]


def test_backward_compat_old_records_without_source():
    """Old records without 'source' or 'options' fields should still work."""
    save_answer("Q1?", "text", {"text": "hi"})
    record = find_answer("Q1?")
    assert record is not None
    assert record.get("source") is None
    assert record.get("options") is None
