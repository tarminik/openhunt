# Analytics System

## Core Idea

hh.ru already provides basic stats (total applications, invitations, rejections, etc.) at `/applicant/negotiations`. We don't duplicate that.

Our analytics is the layer **on top** — things hh.ru doesn't do:
- LLM analysis of why some vacancies result in invitations and others in rejections
- Resume improvement recommendations based on patterns
- Comparison of different resumes' conversion rates
- Breakdown by search query (which queries produce better results)

## Data Sources

- **hh.ru** — scrape application statuses from `/applicant/negotiations` (basic counts, per-application outcomes)
- **Local logs** — which search query or source ("recommended") was used for each application, which resume was used, timestamp

Local logging should be added to the apply flow early — hh.ru doesn't track which query led to which application.

Storage: `~/.openhunt/data/applications.jsonl`

## LLM-Powered Insights

### Resume Recommendations

Compare the user's resume against:
- Vacancies that resulted in invitations (what matched?)
- Vacancies that resulted in rejections (what was missing?)

Find patterns and suggest specific improvements:
- Missing keywords / skills
- Experience framing
- Title/summary optimization

### Multi-Resume Comparison

If the user has multiple resumes, compare their conversion rates.
Identify which resume performs better for which types of vacancies.

### Query Effectiveness

Which search queries lead to higher invitation rates?
Suggest better queries based on the data.
