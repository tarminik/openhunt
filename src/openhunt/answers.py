"""Local memory of answers to employer questionnaire questions.

Stored in ~/.openhunt/memory/answers.json. The format is intentionally simple:
each saved question keeps the original text, a normalized form for lookup, the
question type and the answer payload (shape depends on the type).

Lookup strategy (cheap → expensive):
    1. exact text match
    2. normalized text match (lowercased, punctuation stripped)
    3. (future) LLM-based similarity match

Answer payload shapes:
    text                 → {"text": "..."}
    single_choice        → {"option": "Удаленка"}
    single_choice_other  → {"option": "Свой вариант", "free_text": "..."}
    multi_choice         → {"options": ["a", "b"]}
    multi_choice_other   → {"options": [...], "free_text": "..."}

Option values are *labels* (cell-text-content), not hh.ru per-vacancy IDs —
the same logical answer must be reusable across vacancies.
"""

import hashlib
import json
import os
import re
import shutil
import time
from typing import Any

import click

from openhunt.config import OPENHUNT_DIR

ANSWERS_PATH = OPENHUNT_DIR / "memory" / "answers.json"
SCHEMA_VERSION = 1

QuestionType = str  # "text" | "single_choice" | "multi_choice" | "*_other"


class CorruptAnswersFileError(RuntimeError):
    """Raised when answers.json exists but cannot be parsed.

    The corrupt file is preserved on disk (renamed with a .corrupt suffix) so
    the user can recover it manually instead of losing data silently.
    """

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[?!.,;:()\[\]\"'«»\-—–]+")


def normalize(text: str) -> str:
    """Normalize a question for lookup: lowercase, strip punctuation, collapse whitespace."""
    s = text.replace("\xa0", " ").lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def question_id(normalized_text: str) -> str:
    """Stable short ID derived from the normalized question text."""
    digest = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    return f"q_{digest[:12]}"


def _ensure_dir() -> None:
    ANSWERS_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)


def _empty_db() -> dict:
    return {"version": SCHEMA_VERSION, "questions": {}}


def _quarantine_corrupt(reason: str) -> None:
    """Move a corrupt answers.json out of the way so it isn't overwritten silently.

    Renames to <path>.corrupt-<timestamp> and informs the user via click.echo so
    they can recover the data manually.
    """
    backup = ANSWERS_PATH.with_name(
        f"{ANSWERS_PATH.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    try:
        shutil.move(str(ANSWERS_PATH), str(backup))
    except OSError:
        # If we can't even move the file, refuse to continue rather than risk
        # overwriting it on the next save.
        raise CorruptAnswersFileError(
            f"answers.json is corrupt ({reason}) and could not be moved aside"
        )
    click.echo(
        f"  ! answers.json повреждён ({reason}); сохранён как {backup.name}",
        err=True,
    )


def _load() -> dict:
    if not ANSWERS_PATH.exists():
        return _empty_db()
    try:
        with open(ANSWERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        _quarantine_corrupt(f"JSON parse error: {e}")
        return _empty_db()
    except OSError as e:
        # I/O failure: surface it instead of silently swallowing — the user
        # needs to know their saved answers were not loaded.
        raise CorruptAnswersFileError(f"cannot read answers.json: {e}") from e

    # Schema validation
    if not isinstance(data, dict):
        _quarantine_corrupt("top-level value is not an object")
        return _empty_db()

    version = data.get("version")
    if version != SCHEMA_VERSION:
        # Until we have real migrations, an unknown version is fatal — refuse
        # to silently truncate the user's data on next save.
        raise CorruptAnswersFileError(
            f"unsupported answers.json schema version {version!r} "
            f"(expected {SCHEMA_VERSION}); refusing to overwrite"
        )

    questions = data.get("questions")
    if not isinstance(questions, dict):
        _quarantine_corrupt("'questions' field is missing or not an object")
        return _empty_db()

    return data


def _save(data: dict) -> None:
    """Persist data atomically: write to temp file, fsync, then os.replace."""
    _ensure_dir()
    tmp_path = ANSWERS_PATH.with_name(f"{ANSWERS_PATH.name}.tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.chmod(0o600)
        os.replace(tmp_path, ANSWERS_PATH)
    except OSError:
        # Best-effort cleanup of the temp file on failure
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def find_answer(question_text: str) -> dict | None:
    """Look up a stored answer for the given question text.

    Returns the full question record (including type and answer payload), or None.
    Tries exact match first, then normalized match.
    """
    data = _load()
    questions: dict = data.get("questions", {})

    # Try exact match by text
    for record in questions.values():
        if record.get("text") == question_text:
            return record

    # Fall back to normalized match
    norm = normalize(question_text)
    for record in questions.values():
        if record.get("normalized") == norm:
            return record

    return None


def save_answer(
    question_text: str,
    qtype: QuestionType,
    answer: dict[str, Any],
) -> dict:
    """Save (or update) an answer for the given question.

    If a record with the same normalized text exists, its answer/type are
    updated and used_count is incremented; otherwise a new record is created.
    Returns the saved record.
    """
    data = _load()
    questions: dict = data.setdefault("questions", {})
    norm = normalize(question_text)
    qid = question_id(norm)
    now = time.time()

    existing = questions.get(qid)
    if existing:
        existing["text"] = question_text
        existing["normalized"] = norm
        existing["type"] = qtype
        existing["answer"] = answer
        existing["updated_at"] = now
        existing["used_count"] = int(existing.get("used_count", 0)) + 1
        record = existing
    else:
        record = {
            "id": qid,
            "text": question_text,
            "normalized": norm,
            "type": qtype,
            "answer": answer,
            "created_at": now,
            "updated_at": now,
            "used_count": 1,
        }
        questions[qid] = record

    data["version"] = SCHEMA_VERSION
    _save(data)
    return record


def touch_used(question_id_value: str) -> None:
    """Increment usage counter for an existing record without changing the answer."""
    data = _load()
    questions: dict = data.get("questions", {})
    record = questions.get(question_id_value)
    if not record:
        return
    record["used_count"] = int(record.get("used_count", 0)) + 1
    record["updated_at"] = time.time()
    _save(data)


def list_answers() -> list[dict]:
    """Return all stored answer records, newest first."""
    data = _load()
    questions: dict = data.get("questions", {})
    records = list(questions.values())
    records.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
    return records


def delete_answer(question_id_value: str) -> bool:
    """Remove an answer by ID. Returns True if removed."""
    data = _load()
    questions: dict = data.get("questions", {})
    if question_id_value in questions:
        del questions[question_id_value]
        _save(data)
        return True
    return False
