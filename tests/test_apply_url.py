"""Tests for URL construction in apply module."""

from urllib.parse import quote

from openhunt.browser.actions.apply import SEARCH_URL


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
