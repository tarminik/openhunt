# Ideas & Roadmap

## User Scenarios (job seeker on hh.ru)

### Resume Management
- Raise resume visibility (every 4 hours, one button)
- Edit resume for specific positions
- Manage multiple resumes
- Toggle search status ("looking" / "not looking")

### Job Search
- Search by keywords and filters
- Browse recommended vacancies
- Save interesting vacancies
- Custom filtering beyond hh.ru built-in filters (LLM-based relevance scoring)

### Applications
- Simple apply (one button, no cover letter)
- Apply with cover letter (LLM-generated)
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

### Phase 1: Foundation
- [ ] Project setup, CI, linting
- [ ] Persistent browser session (login once, reuse)
- [ ] Anti-bot measures (delays, human-like behavior)
- [ ] Basic CLI commands

### Phase 2: Quick Wins
- [ ] Raise resume (scheduled, periodic)
- [ ] View application statuses
- [ ] Read new messages
- [ ] Simple apply to a vacancy by URL

### Phase 3: Core Automation
- [ ] Search and filter vacancies
- [ ] Mass apply with criteria
- [ ] Cover letter generation (LLM)

### Phase 4: Communication
- [ ] Classify incoming messages (invitation, rejection, question)
- [ ] Auto-reply to standard messages (LLM-assisted)
- [ ] Notification system

### Phase 5: TUI
- [ ] Interactive vacancy browser
- [ ] Chat interface
- [ ] Status dashboard

### Phase 6: Intelligence
- [ ] Custom relevance scoring (LLM matches vacancy to resume)
- [ ] Resume tailoring per vacancy
- [ ] Salary analysis
- [ ] Interview preparation assistant

## Ideas to Explore
- Telegram bot integration for notifications
- Multiple job site support (SuperJob, Habr Career, etc.)
- Analytics dashboard (response rates, etc.)
- Resume A/B testing
