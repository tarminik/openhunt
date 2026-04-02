# Memory System

The memory system enables openhunt to learn from the user over time and move toward fully autonomous operation.

## Core Idea

When openhunt encounters something it doesn't know how to handle (a questionnaire question, a chat message), it follows this pattern:

1. **First encounter** — ask the user, save the answer
2. **Same or similar question again** — answer automatically from memory
3. **Over time** — fewer and fewer questions reach the user

## Data Sources

Memory is populated from:

- **Questionnaire answers** — user answers employer questions, openhunt remembers them
- **Chat interactions** — patterns from employer conversations
- **User-provided data** — the user can proactively load information:
  - Interview transcriptions
  - Free-form notes about experience, preferences, salary expectations
  - Answers to common questions ("why are you leaving?", "salary expectations?", etc.)

## How It Works

### Questionnaire Automation

```
Employer asks: "Do you have experience with Docker?"
                    ↓
Memory lookup: similar question found? 
    → YES: auto-fill with stored answer
    → NO:  ask user → store answer → fill
```

Similarity matching is done via LLM — questions like "Docker experience?", "Have you worked with containers?", "Знакомы ли вы с Docker?" should all match the same stored answer.

### Chat Automation

Similar pattern but with more context:
- Classify message type (invitation, question, rejection, etc.)
- For known patterns — auto-reply from memory
- For unknown — ask user, learn from response

### Storage

```
~/.openhunt/
├── memory/
│   ├── answers.json       # question-answer pairs from questionnaires
│   ├── chat_patterns.json # learned chat response patterns
│   └── user_data/         # user-provided documents, notes, transcripts
```

## Design Considerations

- Memory is **local only** — never sent anywhere except to the configured LLM
- User can review, edit, and delete any stored memory
- Similarity matching requires LLM — this module depends on LLM integration
- Memory should be exportable/importable (backup, migration)
