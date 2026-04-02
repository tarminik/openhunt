# Ideas & Roadmap

## User Scenarios (job seeker on hh.ru)

### Resume Management
- Raise resume visibility (every 4 hours, one button)
- Edit resume for specific positions
- Manage multiple resumes
- Toggle search status ("looking" / "not looking")

### Job Search
- Search by keywords and filters
- Browse recommended vacancies (https://hh.ru/?hhtmFrom=main — based on resume and past applications)
- Save interesting vacancies
- Custom filtering beyond hh.ru built-in filters (LLM-based relevance scoring)

### Applications
- Simple apply (one button, no cover letter)
- Apply with cover letter (template or LLM-generated)
- Fill employer questionnaires (each one is different — hardest to automate)
- Mass apply to matching vacancies

### Communication
- Read messages from employers
- Reply to interview invitations
- Negotiate terms
- Decline offers

### Tracking
- Application statuses (viewed, invited, rejected)
- Resume statistics (views, search appearances)
- Interaction history

## Automation Difficulty

| Easy | Medium | Hard |
|------|--------|------|
| Raise resume | Apply with cover letter (LLM) | Fill employer questionnaires |
| Simple apply | Mass apply with filters | Free-form chat |
| View application statuses | Reply to typical messages | Resume tailoring per vacancy |
| Read new messages | Custom vacancy filtering (LLM) | Salary negotiation |

## Phases

### Phase 1: Foundation + First Automation (current)
No LLM required — pure Playwright automation.
- [ ] Persistent browser session (login once, reuse)
- [ ] Anti-bot measures (delays, human-like behavior)
- [ ] `openhunt login` — interactive headed login
- [ ] `openhunt apply` — auto-apply to vacancies without required cover letter/questionnaire
  - By search query: `openhunt apply --query "python developer"`
  - From recommended: `openhunt apply --recommended`

### Phase 2: More Automation
- [ ] Raise resume (scheduled, periodic)
- [ ] View application statuses
- [ ] Read new messages
- [ ] Template-based cover letters (no LLM yet)

### Phase 3: LLM Integration
- [ ] Cover letter generation (LLM, personalized per vacancy)
- [ ] Auto-fill employer questionnaires (LLM)
- [ ] Chat with employers (LLM-assisted)
- [ ] Memory system (see docs/memory.md)

### Phase 4: TUI
- [ ] Interactive vacancy browser
- [ ] Chat interface
- [ ] Status dashboard

### Phase 5: Analytics
- [ ] Application logging (start collecting data ASAP — needed for all analytics)
- [ ] Conversion stats: applied → viewed → invitation → rejection
- [ ] Breakdown by query, vacancy type, company, salary range
- [ ] Resume recommendations based on invitation/rejection patterns (LLM)
- [ ] Visual stats dashboard (TUI or export)

### Phase 6: Intelligence
- [ ] Custom relevance scoring (LLM matches vacancy to resume)
- [ ] Resume tailoring per vacancy
- [ ] Interview preparation assistant
- [ ] Best time to apply analysis
- [ ] Multi-resume A/B testing (which resume converts better)

## Ideas to Explore
- Telegram bot integration for notifications
- Multiple job site support (SuperJob, Habr Career, etc.)
- Market analysis (salary trends, skill demand)
