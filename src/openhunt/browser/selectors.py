"""Centralized hh.ru selectors.

All CSS/XPath selectors for hh.ru are defined here.
When hh.ru updates their markup, only this file needs to change.
"""

# --- Login / Auth ---
# Element visible only when logged in (may be hidden on mobile layout)
USER_MENU = "[data-qa='mainmenu_applicantProfilePage']"

# --- Search results page ---
VACANCY_CARD = "[data-qa='vacancy-serp__vacancy']"
VACANCY_TITLE_LINK = "[data-qa='serp-item__title']"
PAGER_NEXT = "[data-qa='pager-next']"

# --- Vacancy page ---
APPLY_BUTTON = "[data-qa='vacancy-response-link-top']"

# --- Apply popup (modal dialog after clicking apply) ---
RESPONSE_POPUP_CLOSE = "[data-qa='response-popup-close']"
RESPONSE_POPUP_SUBMIT = "[data-qa='vacancy-response-submit-popup']"
RESPONSE_POPUP_LETTER_INPUT = "[data-qa='vacancy-response-popup-form-letter-input']"

# --- Post-apply page (simple vacancies without popup) ---
RESPONSE_LETTER_SUBMIT = "[data-qa='vacancy-response-letter-submit']"

# --- Resume page (/applicant/resumes) ---
RESUME_CARD = "[data-qa='resume']"
RESUME_RAISE_BUTTON = "[data-qa~='resume-update-button']"
