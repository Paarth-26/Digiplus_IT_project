# 🎯 Support Incident Triage Assistant

An AI-assisted support desk: log an incident, and it is automatically categorised, prioritised,
summarised, matched against a knowledge base, and given a draft resolution for an engineer to review.

**Stack:** FastAPI · SQLite · SQLAlchemy 2.0 · Groq (`llama-3.3-70b-versatile`) · Streamlit

---

## 📋 Overview

Support teams spend a large share of their time on the first few minutes of every ticket: working
out what it is, how urgent it is, whether it has been seen before, and where to start. This
application automates that first pass. When an incident is logged through the API or the UI, a
three-step AI pipeline runs against it — classifying the incident into a category and priority and
writing a short summary, then matching it against the knowledge base and recording a relevance score
and a written rationale for each match, then drafting a resolution grounded in whichever articles
matched. Every AI-derived field is advisory: an engineer reviews and edits the drafted resolution
before it is saved, and every AI step is designed to fail without taking the incident with it, so a
model outage degrades the product to a plain ticket tracker rather than breaking it.

---

## 🚀 Setup & Run Instructions

### 1. Create the virtual environment

```bash
py -m venv .venv
```

### 2. Install dependencies

```powershell
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
# macOS / Linux
./.venv/bin/python -m pip install -r requirements.txt
```

### 3. Configure your API key

Copy `.env.example` to `.env` and add a Groq API key (free at
[console.groq.com/keys](https://console.groq.com/keys)):

```powershell
copy .env.example .env
```

```
GROQ_API_KEY=gsk_your_key_here
```

The file is loaded at import time by `app/config.py`. Real environment variables take precedence
over `.env`, and `/health` reports whether the key was found — it never echoes the value.

### 4. Seed the database

Tables are created automatically on first startup. These two commands populate them:

```powershell
# Knowledge base — 10 hand-written IT support articles
.\.venv\Scripts\python.exe seed_kb.py --reset --source fallback

# Incidents — 15 real tickets from the HuggingFace dataset, then run AI triage on each
.\.venv\Scripts\python.exe seed_incidents.py --limit 15 --analyze
```

`--analyze` runs the full three-step pipeline over the seeded rows, so they arrive with categories,
priorities, summaries, KB links, and drafted resolutions already populated. Omit it for a faster,
zero-cost seed. Both scripts are idempotent — re-running skips rows that already exist.

### 5. Start the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8000 | API root |
| http://127.0.0.1:8000/docs | Interactive Swagger UI |
| http://127.0.0.1:8000/health | Health check + key status |

### 6. Start the frontend

In a **second terminal**, with the backend still running:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Opens at **http://localhost:8501**. It talks to the backend over HTTP using `requests`; point it
elsewhere with `API_BASE=http://host:port`.

---

## 🤖 AI Configuration

| Setting | Value | Override |
| --- | --- | --- |
| Provider | Groq | — |
| Model | `llama-3.3-70b-versatile` | `GROQ_MODEL` |
| Response format | `{"type": "json_object"}` | — |
| Temperature | 0.2 | — |
| Timeout | 30s | `GROQ_TIMEOUT` |
| Retries | 1 | `GROQ_MAX_RETRIES` |

All three steps request structured JSON and validate the result before anything is written to the
database. The pipeline lives in `app/pipeline.py`; the Groq calls themselves are in `app/ai.py`.

### Step 1 — Analyse and classify

The incident's title and description are sent to the model, which returns:

- **`category`** — one of `Network`, `Software`, `Hardware`, `Account/Access`, `Billing`, `Other`
- **`priority`** — one of `low`, `medium`, `high`, `critical`, judged on business impact and urgency
- **`summary`** — a neutral one-to-two sentence restatement of the problem

Values outside those vocabularies are **dropped rather than coerced** — a wrong-but-plausible
category is more damaging than an absent one, because it looks trustworthy. Casing is normalised
(`"hardware"` → `"Hardware"`), and partial results are kept: a valid category is saved even if the
priority came back unusable.

### Step 2 — Match against the knowledge base

The incident — using the Step 1 summary when available, alongside the raw title and description — is
sent with the full KB catalogue. The model returns up to **three** matches, each with:

- **`relevance_score`** — 0 to 1, where 1 means the article directly resolves the incident
- **`rationale`** — one sentence on what the article gives the engineer *for this specific incident*

**Returning fewer than three matches, including none, is a correct outcome.** The prompt explicitly
forbids padding the list, and states that sharing a topic word with the incident is not relevance.
Article IDs are validated against the catalogue that was actually sent, so a hallucinated ID can
never produce a link to a non-existent or unrelated article. Re-running replaces existing links
rather than appending, so repeated analysis cannot accumulate stale matches.

### Step 3 — Draft a resolution

The final step writes `ai_suggested_resolution` — a draft for an engineer to review and edit, never
a claim that the incident is fixed. It runs in one of two modes:

- **Grounded** — when Step 2 found matches, their content is supplied and the model is instructed to
  follow those documented steps, and to say what still needs checking where an article only partly
  applies.
- **Diagnostic** — when nothing matched, the model is told explicitly that **no documentation was
  found** and instructed *not* to imply a documented procedure exists. It instead proposes the next
  diagnostic steps and states what information should be gathered from the reporter.

This distinction matters in practice: across the seeded incidents roughly half the drafts are
grounded in real articles and half are diagnostic-only. The `kb_links` array on an incident is what
distinguishes them, and is worth surfacing anywhere a draft is shown.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/incidents` | Create an incident (`title`, `description` required, non-empty) and run the full AI pipeline. Returns **201**. |
| `GET` | `/incidents` | List incidents, newest first. Optional `?status=` and `?priority=` filters. |
| `GET` | `/incidents/{id}` | Full detail, including matched KB articles with relevance scores and rationales. |
| `PATCH` | `/incidents/{id}` | Update triage fields (`status`, `priority`, `category`). |
| `POST` | `/incidents/{id}/reanalyze` | Re-run the AI pipeline on an existing incident. |
| `POST` | `/incidents/{id}/resolve` | Resolve with `resolution_notes`; sets status and `resolved_at`. |
| `GET` | `/kb` | List knowledge base articles. Optional `?tag=` filter. |
| `GET` | `/health` | Liveness, database reachability, and whether the Groq key loaded. |

**Error conventions**

| Code | Meaning | Example |
| --- | --- | --- |
| `422` | Malformed request body (Pydantic validation) | empty `title`, unknown status value, unexpected field |
| `400` | Well-formed but semantically invalid | `?status=bogus`, empty PATCH, resolving an already-resolved incident |
| `404` | Unknown incident ID | `GET /incidents/99999` |
| `502` | AI pipeline produced nothing on an explicit `/reanalyze` | Groq unreachable or rate-limited |

Request bodies use `extra="forbid"`, so a typo'd or unsupported field is rejected explicitly rather
than silently ignored.

---

## 🏗️ Approach & Architecture

```
Streamlit UI (app.py) ──HTTP──> FastAPI (app/) ──> SQLite (incidents.db)
      :8501                        :8000                    │
                                     │                      │
                                     └──> app/pipeline.py ──┴──> Groq API
                                            analyse → match KB → draft
```

**Why FastAPI + SQLite.** FastAPI gives request validation, typed responses, and generated API docs
from the same Pydantic models used internally, which keeps the contract and the implementation from
drifting. SQLite needs no server process, so the whole project runs from a clone with one `pip
install` — appropriate for an assessment, and the SQLAlchemy layer means moving to Postgres is a
connection-string change rather than a rewrite.

**Why three sequential AI calls instead of one.** A single prompt returning classification, matches,
and a resolution together would be cheaper and faster, but it couples three failures into one. Each
step here is independent and individually non-fatal:

- The incident is **committed to the database before any AI runs**, so an outage can only leave
  triage fields null — it can never fail the creation.
- If classification fails, KB matching still runs on the raw title and description.
- If matching fails or finds nothing, the draft still runs in diagnostic mode.
- Each step validates its own output, so one malformed response cannot corrupt the others.

The steps are also genuinely sequential rather than parallel: matching is better with the Step 1
summary in hand, and drafting is better with the matched articles in hand. Every step is wrapped so
that the worst case is a null field plus a logged error, and the same `run_pipeline()` function backs
the API, the `/reanalyze` endpoint, and the seeder — so a seeded row is indistinguishable from one
created through the UI.

**Frontend.** Streamlit was chosen for speed of delivery, then styled well past its defaults with
injected CSS: a branded gradient header, card-style containers, coloured pill badges, KPI tiles, and
an indigo accent palette. Creating, viewing, and resolving all happen in `st.dialog` popups rather
than permanently-visible forms, feedback uses non-blocking toasts, and destructive actions require
explicit confirmation — resolving opens a dialog with the editable draft rather than firing on click.
The frontend holds no business logic and imports nothing from the backend package; it communicates
purely over HTTP, so either side can be restarted independently.

---

## 📊 Data Source Decision

**The dataset was inspected before it was used, and that inspection changed how it was used.**

The assignment's suggested source,
[`mindweave/help-desk-tickets`](https://huggingface.co/datasets/mindweave/help-desk-tickets), has a
`tickets` table with these 15 columns:

```
ticket_id, created_at, first_response_at, resolved_at, priority, status, channel,
category_id, assigned_agent_id, requester_department, affected_service,
summary, description, escalated, outage_related
```

There is **no resolution or fix-text column anywhere in the dataset**. The `description` field is
the `summary` sentence plus a "Reported by X from Y" clause, and the separate `comments` table
contains generic filler assigned independently of the ticket it attaches to — a printer ticket
receives agent notes about MFA re-registration. An initial run that seeded the knowledge base from
this data produced articles with realistic titles and no procedural content whatsoever.

The two tables were therefore sourced according to what each actually needs:

| Table | Source | Reasoning |
| --- | --- | --- |
| **`incidents`** | HuggingFace dataset — 15 real, unfabricated tickets | This is exactly what the dataset contains: realistic inbound support tickets. Used for its intended purpose. |
| **`kb_articles`** | 10 hand-written articles | A knowledge base must contain diagnostic steps and resolutions. The dataset has none, and the assignment does not require the KB to come from the same source. |

Seeding the KB from ticket titles would have produced articles that look plausible and contain no
usable guidance — which would have silently undermined the two features that depend on KB quality:
relevance matching and grounded resolution drafting. Both would have appeared to work while
returning meaningless output, which is a worse outcome than a smaller, honest knowledge base.

The hand-written articles cover password reset, VPN connectivity, printer offline, slow laptop,
email sync, software install permissions, Wi-Fi drops, disk space, lost MFA device, and screen
sharing.

Two consequences of this decision are deliberate:

- **`seed_incidents.py` has no fallback data.** If the dataset download fails, it exits non-zero
  rather than inventing tickets — fabricated incidents would be indistinguishable from real ones
  once stored. `seed_kb.py` keeps a fallback because the hand-written set *is* the intended content.
- **Incident topics only partly overlap the KB**, which is realistic and useful: it exercises the
  "no confident match" path rather than letting every incident find an article.

---

## ⚠️ Assumptions & Limitations

- **No authentication or authorisation.** Every endpoint is public and CORS allows all origins for
  local development. `CORS_ORIGINS` can restrict this, but real deployment needs auth first.
- **Testing was done during development rather than as a committed suite.** The API, AI failure
  paths, KB matching, resolution drafting, CORS, and the Streamlit UI were each exercised with
  purpose-written harnesses — including Streamlit's `AppTest` for dialog and filter-state behaviour —
  but these are not checked in as a `pytest` suite, which is the main gap in the submission.
- **KB match quality is bounded by having only 10 articles.** Incidents involving BitLocker, Intune,
  SSO, or voicemail have no corresponding article and correctly return no match. That is the system
  declining to force a weak match, not a failure — but it means match coverage reflects KB size more
  than model capability.
- **Incident creation makes up to three sequential Groq calls**, so it takes roughly 1–3 seconds and
  the request blocks for that time. Each step is independently non-fatal, but the failure surface
  scales with the step count.
- **Groq's free tier has a daily token quota** that heavy testing or demoing can exhaust. When that
  happens the API returns 429, incidents **still save successfully**, and AI fields simply stay null
  until the quota resets — the UI shows "AI analysis pending ⏳" rather than an error.
- **No duplicate or similar-incident detection.** Three identical "VPN not working" tickets are
  three separate incidents.
- **Timestamps are stored naive.** The code writes timezone-aware UTC, but SQLite's `DATETIME` drops
  the offset. Consistent as long as everything writes UTC.
- **No pagination** on the list endpoints, and no migrations — `create_all()` creates missing tables
  but does not alter existing ones, so a schema change means re-seeding or adding Alembic.

---

## 🔭 Future Improvements

1. **Background AI processing.** Move the pipeline to a task queue so `POST /incidents` returns
   immediately and triage fields populate asynchronously, with the UI polling or subscribing for
   updates. This removes the 1–3 second block and the timeout risk entirely.
2. **Embeddings-based KB retrieval.** At 10 articles, sending the whole catalogue in the prompt is
   fine. Beyond roughly 50 it stops being viable — vector search over article embeddings would
   pre-filter candidates, with the model reranking and writing rationales for the top few.
3. **Duplicate and similar-incident detection.** Surface related open incidents at creation time,
   both to prevent duplicate work and to detect an emerging outage from a cluster of similar reports.
4. **Authentication and audit trail.** Per-engineer accounts, role-based permissions on resolve, and
   a record of who edited an AI draft before saving it — useful both operationally and for measuring
   how much the drafts actually get changed.
5. **Analytics dashboard.** Resolution times by category and priority, KB article hit rates, the
   share of drafts accepted unedited, and AI-assigned priority compared against what engineers
   corrected it to — the dataset's own `P1`–`P4` column is available as ground truth for scoring
   classification accuracy.

---

## 📁 Project Structure

```
├── app/
│   ├── main.py            FastAPI app, CORS, logging, /health
│   ├── config.py          .env loading, GROQ_API_KEY access
│   ├── constants.py       Status/priority/category vocabularies and emoji
│   ├── database.py        Engine, session factory, init_db()
│   ├── models.py          Incident, KBArticle, IncidentKBLink
│   ├── schemas.py         Pydantic request/response models
│   ├── ai.py              Groq calls: classify, match KB, draft resolution
│   ├── pipeline.py        The 3-step pipeline, shared by API and seeders
│   └── routers/
│       ├── incidents.py   Incident CRUD, reanalyze, resolve
│       └── kb.py          Knowledge base listing
├── app.py                 Streamlit frontend
├── hf_source.py           HuggingFace dataset loader (timeout, column detection)
├── seed_kb.py             Seeds kb_articles
├── seed_incidents.py      Seeds incidents, with optional --analyze
├── requirements.txt
└── .env.example
```

### Data model

- **`incidents`** — `id, title, description, status, priority, category, ai_summary,
  ai_suggested_resolution, resolution_notes, created_at, resolved_at`
- **`kb_articles`** — `id, title, content, tags, created_at`
- **`incident_kb_links`** — `id, incident_id, kb_article_id, relevance_score, rationale`, unique on
  `(incident_id, kb_article_id)` and cascading on delete from either side
