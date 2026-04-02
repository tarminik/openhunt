"""Browser session management with Playwright persistent context."""

import random
import time
from contextlib import contextmanager

from playwright.sync_api import sync_playwright, BrowserContext, Page

from openhunt.config import BROWSER_DIR, ensure_dirs
from openhunt.browser import selectors


BASE_URL = "https://hh.ru"
LOGIN_URL = "https://hh.ru/account/login"


def human_delay(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    """Sleep for a random duration to mimic human behavior."""
    time.sleep(random.uniform(min_sec, max_sec))


@contextmanager
def browser_context(headless: bool = True):
    """Create a persistent browser context.

    Usage:
        with browser_context(headless=True) as (context, page):
            page.goto("https://hh.ru")
    """
    ensure_dirs()
    pw = sync_playwright().start()
    context = None
    try:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            locale="ru-RU",
        )
        page = context.pages[0] if context.pages else context.new_page()
        yield context, page
    finally:
        if context is not None:
            context.close()
        pw.stop()


def check_auth(page: Page) -> bool:
    """Navigate to hh.ru and check if the user is logged in."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    if "/account/login" in page.url:
        return False
    # USER_MENU element exists in DOM but may be hidden (mobile menu),
    # so use query_selector (checks presence) not wait_for_selector (checks visibility)
    return page.query_selector(selectors.USER_MENU) is not None
