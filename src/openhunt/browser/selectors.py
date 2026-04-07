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
VACANCY_TITLE = "[data-qa='vacancy-title']"
VACANCY_DESCRIPTION = ".vacancy-section.vacancy-section_magritte"
APPLY_BUTTON = "[data-qa='vacancy-response-link-top']"

# --- Apply popup (modal dialog after clicking apply) ---
RESPONSE_POPUP_CLOSE = "[data-qa='response-popup-close']"
RESPONSE_POPUP_SUBMIT = "[data-qa='vacancy-response-submit-popup']"
RESPONSE_POPUP_LETTER_INPUT = "[data-qa='vacancy-response-popup-form-letter-input']"
RESPONSE_POPUP_RESUME_SELECT = "[data-qa~='resume-select']"

# --- Post-apply inline form (simple vacancies without popup) ---
RESPONSE_LETTER_SUBMIT = "[data-qa='vacancy-response-letter-submit']"
RESPONSE_LETTER_INFORMER = "[data-qa='vacancy-response-letter-informer']"
RESPONSE_LETTER_TEXTAREA = "[data-qa='vacancy-response-letter-informer'] textarea"

# --- Questionnaire form (employer questions on /applicant/vacancy_response) ---
# All option types share the same wrapper structure (label[data-qa='cell']);
# they differ only in <input type='radio'> vs <input type='checkbox'> inside.
QUESTIONNAIRE_CONTAINER = "[data-qa='employer-asking-for-test']"
QUESTIONNAIRE_DESCRIPTION = "[data-qa='test-description']"
QUESTIONNAIRE_TASK = "[data-qa='task-body']"
QUESTIONNAIRE_QUESTION_TEXT = "[data-qa='task-question']"
QUESTIONNAIRE_OPTION_CELL = "[data-qa='cell']"
QUESTIONNAIRE_OPTION_TEXT = "[data-qa='cell-text-content']"
# Submit button is shared with the popup form (RESPONSE_POPUP_SUBMIT)
QUESTIONNAIRE_SUBMIT = RESPONSE_POPUP_SUBMIT

# --- Resume page (/applicant/resumes) ---
RESUME_CARD = "[data-qa='resume']"
RESUME_RAISE_BUTTON = "[data-qa~='resume-update-button']"

# --- User profile (header menu) ---
USER_FULLNAME = "[data-qa='profile-activator-fullname']"

# --- Resume detail page (/resume/<id>) ---
RESUME_POSITION = "[data-qa='resume-position-card']"
RESUME_EXPERIENCE = "[data-qa='resume-list-card-experience']"
RESUME_SKILLS = "[data-qa='skills-card']"
RESUME_EDUCATION = "[data-qa='resume-list-card-education']"
RESUME_ABOUT = "[data-qa='resume-about-card']"

# --- UI text constants ---
APPLY_BUTTON_TEXT = "Откликнуться"
RESPONSE_DELIVERED_TEXT = "Резюме доставлено"
RESPONSE_SENT_TEXT = "Отклик отправлен"
QUESTIONNAIRE_TEXT = "Ответьте на вопросы"
QUESTIONNAIRE_ALT_TEXT = "ответить на несколько вопросов"
RELOCATION_CONFIRM_TEXT = "Все равно откликнуться"
RESUME_RAISE_TEXT = "Поднять в поиске"
RESUME_COOLDOWN_TEXT = "Поднять вручную можно"
