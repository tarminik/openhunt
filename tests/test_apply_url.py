"""Tests for URL construction and filtering in apply module."""

from urllib.parse import quote

from openhunt.browser.actions.apply import SEARCH_URL, RECOMMENDED_URL, _compile_exclude_patterns


def test_simple_query():
    url = SEARCH_URL.format(query=quote("python developer", safe=""), page=0)
    assert url == "https://hh.ru/search/vacancy?text=python%20developer&page=0"


def test_special_chars_hash():
    url = SEARCH_URL.format(query=quote("C# developer", safe=""), page=0)
    assert "C%23" in url
    assert "#" not in url.split("?")[1]


def test_special_chars_ampersand():
    url = SEARCH_URL.format(query=quote("R&D engineer", safe=""), page=0)
    assert "R%26D" in url


def test_cyrillic_query():
    url = SEARCH_URL.format(query=quote("бекенд разработчик", safe=""), page=0)
    assert "page=0" in url
    assert " " not in url


def test_hh_operators():
    q = "NAME:(python OR golang) AND NOT стажёр"
    url = SEARCH_URL.format(query=quote(q, safe=""), page=2)
    assert "page=2" in url
    assert "(" not in url.split("?")[1]


def test_pagination():
    for p in [0, 1, 5, 10]:
        url = SEARCH_URL.format(query=quote("test", safe=""), page=p)
        assert f"page={p}" in url


def test_recommended_url():
    resume_id = "abc123def456"
    url = RECOMMENDED_URL.format(resume_id=resume_id, page=0)
    assert f"resume={resume_id}" in url
    assert "page=0" in url
    assert "/search/vacancy?" in url


def test_recommended_pagination():
    for p in [0, 1, 5]:
        url = RECOMMENDED_URL.format(resume_id="test_id", page=p)
        assert f"page={p}" in url
        assert "resume=test_id" in url


# --- Exclude pattern filtering ---


def test_exclude_pattern_matches_case_insensitive():
    patterns = _compile_exclude_patterns(["стажёр"])
    assert any(p.search("Стажёр Python") for p in patterns)
    assert any(p.search("стажёр") for p in patterns)
    assert not any(p.search("Senior Python Developer") for p in patterns)


def test_exclude_pattern_regex_or():
    patterns = _compile_exclude_patterns(["стажёр|intern"])
    assert any(p.search("Python Intern") for p in patterns)
    assert any(p.search("Стажёр разработчик") for p in patterns)
    assert not any(p.search("Senior Developer") for p in patterns)


def test_exclude_multiple_patterns():
    patterns = _compile_exclude_patterns(["стажёр", "Яндекс"])
    title1 = "Стажёр Python"
    title2 = "Разработчик в Яндекс"
    title3 = "Senior Developer в VK"
    assert any(p.search(title1) for p in patterns)
    assert any(p.search(title2) for p in patterns)
    assert not any(p.search(title3) for p in patterns)


def test_exclude_empty_patterns():
    patterns = _compile_exclude_patterns([])
    assert patterns == []
