# 🍕 SLICE — NYC Cheap Eats Chatbot

A narrow-domain Q&A chatbot that recommends cheap places to eat in New York City for under $15.

**Live URL:** https://nyc-cheap-eats-1026658918129.us-central1.run.app  
**GitHub:** https://github.com/Kanchanbhale/nyc-cheap-eats-final

<img width="924" height="699" alt="Screenshot 2026-03-02 at 10 51 42 PM" src="https://github.com/user-attachments/assets/028a599d-6410-45a2-b401-1124a4e6e41b" />


## What this project demonstrates

- FastAPI backend + simple web UI
- Narrow domain with explicit scope boundaries
- Few-shot prompting with 6 examples
- Positive constraints about what the bot can answer
- Escape hatch when uncertain
- 4 out-of-scope categories
- Python backstop for deterministic safety and redirect handling
- Eval harness with:
  - 20 golden-reference MaaJ evals (10 in-domain, 5 out-of-scope, 5 adversarial/safety)
  - 10 rubric MaaJ evals
  - deterministic rule-based tests

## Setup

### 1) Install dependencies

```bash
uv sync
```

### 2) Authenticate with GCP (one-time)

```bash
gcloud auth login
gcloud config set project ieor-agentic-1
```


### 3) Environment

Create a `.env` file with:

```env
VERTEXAI_PROJECT=ieor-agentic-1
VERTEXAI_LOCATION=us-central1
```

## Run locally

To avoid port conflicts during local development:

```bash
uv run uvicorn app:app --reload --port 8001
```

Then open `http://127.0.0.1:8001`

## Run evals

```bash
uv run pytest evals/ -v
```

This runs:
- `evals/test_rules.py` — deterministic checks
- `evals/test_golden.py` — 20 golden-reference MaaJ evals
- `evals/test_rubric.py` — 10 rubric MaaJ evals

## Deploy to GCP Cloud Run

```bash
gcloud run deploy nyc-cheap-eats \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --project ieor-agentic-1
```


## Suggested project structure

```text
nyc-cheap-eats-final/
├── app.py
├── static/
│   └── index.html
├── evals/
│   ├── conftest.py
│   ├── test_rules.py
│   ├── test_golden.py
│   └── test_rubric.py
├── .env
├── Dockerfile
├── pyproject.toml
├── uv.lock
└── README.md
```

