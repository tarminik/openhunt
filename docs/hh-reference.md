# hh.ru Reference

Technical notes about how hh.ru works — useful when implementing browser automation.

## Search Query Language

hh.ru supports a rich query language with boolean operators, field search, and exact matching.

Full documentation: https://hh.ru/article/25295

### Operators

| Operator | Description |
|----------|-------------|
| `AND` (or space) | Conjunction — all words must be present |
| `OR` | Disjunction — any of the words |
| `NOT` | Exclusion — word must not be present |
| `!` | Exact word, disables synonyms: `!python` |
| `""` | Exact phrase: `"senior developer"` |
| `~N` | Words within N words of each other: `"python senior"~3` |
| `*` | Prefix search: `гео*` → геолог, географ |
| `()` | Grouping for priority |

### Field Search (vacancies)

| Field | Searches in |
|-------|-------------|
| `NAME:` | Vacancy title |
| `COMPANY_NAME:` | Company name |
| `DESCRIPTION:` | Vacancy description |

Exact field match with `^`: `^NAME:программист` (title must be exactly "программист").

### Examples

```
# Python or backend, not intern
(python OR backend) AND NOT стажёр

# Exact title search
NAME:(python AND NOT junior)

# Specific company
COMPANY_NAME:Яндекс AND python

# Complex query
NAME:(!python OR !golang) AND DESCRIPTION:(fastapi OR django) AND NOT стажёр
```

Operator priority: `NOT` > `AND` > `OR`. Use parentheses to override.

## Key URLs

| Page | URL |
|------|-----|
| Recommended vacancies | `https://hh.ru/?hhtmFrom=main` |
| Search results | `https://hh.ru/search/vacancy?text=<query>` |
| Login page | `https://hh.ru/account/login` |
| Applications list | `https://hh.ru/applicant/negotiations` |
| Messages | `https://hh.ru/applicant/negotiations#702` |

## Useful Articles

- [Search query language](https://hh.ru/article/25295) — full reference for query operators
