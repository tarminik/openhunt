"""Resume profile sync from hh.ru."""

import click
from playwright.sync_api import Page

from openhunt.browser import selectors
from openhunt.browser.session import human_delay
from openhunt.memory import save_profile


RESUME_URL = "https://hh.ru/resume/{resume_id}"


def sync_resume_profile(page: Page, resume_id: str) -> str:
    """Navigate to the resume page, extract text content, and save to memory.

    Returns the extracted profile text.
    """
    page.goto(RESUME_URL.format(resume_id=resume_id), wait_until="domcontentloaded")
    human_delay(0.5, 1.5)

    # Extract structured resume sections
    block_selectors = [
        selectors.RESUME_POSITION,
        selectors.RESUME_EXPERIENCE,
        selectors.RESUME_SKILLS,
        selectors.RESUME_EDUCATION,
        selectors.RESUME_ABOUT,
    ]
    parts = []
    for sel in block_selectors:
        el = page.query_selector(sel)
        if el:
            text = el.inner_text().strip()
            if text:
                parts.append(text)
    profile_text = "\n\n".join(parts) if parts else page.inner_text("body").strip()

    profile_text = profile_text.replace("\xa0", " ")
    save_profile(resume_id, profile_text)
    return profile_text
