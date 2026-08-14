"""Groq-backed incident triage.

`analyze_incident()` is total: it never raises. Every failure mode -- missing key,
network error, rate limit, malformed JSON, out-of-vocabulary values -- is logged and
returned as an `AnalysisResult` whose fields are None, so incident creation always
succeeds regardless of what the model or the network does.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from app.constants import CATEGORIES, PRIORITIES

log = logging.getLogger(__name__)

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "1"))

# Truncated before sending: incident text is user-supplied and unbounded.
MAX_TITLE_CHARS = 500
MAX_DESCRIPTION_CHARS = 4000

# Bounds on the KB payload, so prompt size stays predictable as the KB grows.
MAX_KB_ARTICLES = 50
MAX_KB_CONTENT_CHARS = 1200
MAX_KB_LINKS = 3

# Upper bound on a stored draft, so a runaway generation can't bloat the row.
MAX_RESOLUTION_CHARS = 4000

SYSTEM_PROMPT = f"""You are an IT service desk triage assistant.

Analyse the incident and reply with a single JSON object, nothing else, with exactly \
these three keys:

- "category": exactly one of {list(CATEGORIES)}
- "priority": exactly one of {list(PRIORITIES)}
- "summary": a neutral 1-2 sentence summary of the incident

Rules:
- Use "Other" only when the incident genuinely fits no other category.
- Judge priority by business impact and urgency: "critical" for a widespread outage \
or a security compromise, "low" for a single user with a workaround.
- Do not invent details that are not in the incident text. If the text is too thin to \
judge, summarise only what is stated.
"""


@dataclass
class AnalysisResult:
    """Per-field results. Any field may be None if the model omitted or botched it."""

    category: str | None = None
    priority: str | None = None
    summary: str | None = None
    error: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.category or self.priority or self.summary)


def _client():
    """Build a Groq client, or raise if the key is absent."""
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return Groq(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)


def _match_vocabulary(value: object, allowed: tuple[str, ...], field: str) -> str | None:
    """Accept a value only if it maps onto the controlled vocabulary.

    Case-insensitive, since models vary on capitalisation ("HIGH", "network"). Anything
    genuinely outside the vocabulary is dropped rather than coerced -- a wrong-but-valid
    category is worse than an absent one, because it looks trustworthy.
    """
    if not isinstance(value, str):
        log.warning("🤖 AI returned non-string %s: %r", field, value)
        return None
    cleaned = value.strip()
    for candidate in allowed:
        if cleaned.lower() == candidate.lower():
            return candidate
    log.warning("🤖 AI returned out-of-vocabulary %s: %r (allowed: %s)", field, value, ", ".join(allowed))
    return None


def analyze_incident(title: str, description: str) -> AnalysisResult:
    """Classify an incident. Never raises -- failures come back as empty fields."""
    try:
        client = _client()
        user_content = (
            f"Title: {title[:MAX_TITLE_CHARS]}\n\n"
            f"Description: {description[:MAX_DESCRIPTION_CHARS]}"
        )

        log.info("🤖 Analysing incident with %s ...", MODEL)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001 - deliberately total
        log.error("❌ Groq call failed (%s): %s", type(exc).__name__, exc)
        return AnalysisResult(error=f"{type(exc).__name__}: {exc}")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        # response_format=json_object makes this unlikely, not impossible.
        log.error("❌ Groq returned invalid JSON: %s | raw=%.200r", exc, raw)
        return AnalysisResult(error=f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        log.error("❌ Groq returned JSON that is not an object: %.200r", raw)
        return AnalysisResult(error="JSON payload was not an object")

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        if summary is not None:
            log.warning("🤖 AI returned unusable summary: %r", summary)
        summary = None
    else:
        summary = summary.strip()

    result = AnalysisResult(
        category=_match_vocabulary(payload.get("category"), CATEGORIES, "category"),
        priority=_match_vocabulary(payload.get("priority"), PRIORITIES, "priority"),
        summary=summary,
    )

    if result.is_empty:
        log.error("❌ AI response had no usable fields: %.200r", raw)
        result.error = "no usable fields in AI response"
    else:
        log.info(
            "✅ AI analysis: category=%s priority=%s summary=%s",
            result.category,
            result.priority,
            "yes" if result.summary else "no",
        )
    return result


KB_SYSTEM_PROMPT = f"""You are an IT service desk assistant matching an incident against a \
knowledge base.

You are given an incident and a list of knowledge base articles. Identify at most \
{MAX_KB_LINKS} articles that would genuinely help an agent resolve THIS incident.

Reply with a single JSON object, nothing else:

{{"links": [{{"id": <article id>, "relevance_score": <number 0-1>, \
"rationale": "<one sentence on why this article helps>"}}]}}

Rules:
- Only use "id" values from the supplied article list.
- relevance_score is 0 to 1, where 1 means the article directly resolves the incident.
- Returning fewer than {MAX_KB_LINKS} links is correct and expected. Return \
{{"links": []}} when no article genuinely applies.
- Do NOT pad the list with weak matches. An article that merely shares a topic word \
with the incident is not relevant.
- The rationale must state what the article gives the agent for this specific incident.
"""


@dataclass
class KBLinkSuggestion:
    kb_article_id: int
    relevance_score: float | None
    rationale: str | None


@dataclass
class KBLinkResult:
    links: list[KBLinkSuggestion]
    error: str | None = None


def _extract_link_list(payload: dict) -> list | None:
    """Find the array of links, tolerating a differently-named key."""
    for key in ("links", "articles", "results", "matches"):
        if isinstance(payload.get(key), list):
            return payload[key]
    # Last resort: a single list value under any key.
    lists = [v for v in payload.values() if isinstance(v, list)]
    return lists[0] if len(lists) == 1 else None


def _first(item: dict, *keys):
    for key in keys:
        if key in item:
            return item[key]
    return None


def _parse_link(item: object, valid_ids: set[int]) -> KBLinkSuggestion | None:
    """Validate one suggested link. Returns None if it can't be trusted."""
    if not isinstance(item, dict):
        log.warning("🔗 AI returned non-object link entry: %r", item)
        return None

    raw_id = _first(item, "id", "kb_article_id", "article_id")
    try:
        article_id = int(raw_id)
    except (TypeError, ValueError):
        log.warning("🔗 AI returned unusable KB article id: %r", raw_id)
        return None

    # A hallucinated id is the main risk here: it would create a link to an article
    # that does not exist, or worse, to an unrelated one that happens to share the id.
    if article_id not in valid_ids:
        log.warning("🔗 AI referenced KB article %s, which was not in the supplied list", article_id)
        return None

    raw_score = _first(item, "relevance_score", "score", "relevance")
    score: float | None
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        log.warning("🔗 AI returned unusable relevance_score %r for article %s", raw_score, article_id)
        score = None
    else:
        if not 0.0 <= score <= 1.0:
            log.warning("🔗 Clamping out-of-range relevance_score %r for article %s", score, article_id)
            score = min(1.0, max(0.0, score))

    rationale = _first(item, "rationale", "reason", "why")
    if not isinstance(rationale, str) or not rationale.strip():
        log.warning("🔗 AI returned no rationale for article %s", article_id)
        rationale = None
    else:
        rationale = rationale.strip()

    return KBLinkSuggestion(kb_article_id=article_id, relevance_score=score, rationale=rationale)


def suggest_kb_links(title: str, description: str, summary: str | None, articles) -> KBLinkResult:
    """Pick the KB articles relevant to an incident. Never raises.

    `articles` is any sequence of objects exposing `id`, `title` and `content`.
    An empty `links` list is a valid, expected outcome -- not an error.
    """
    articles = list(articles)[:MAX_KB_ARTICLES]
    if not articles:
        log.info("🔗 No KB articles to match against; skipping linking")
        return KBLinkResult(links=[])

    valid_ids = {a.id for a in articles}

    incident_text = f"Title: {title[:MAX_TITLE_CHARS]}\n"
    if summary:
        # The summary is the cleanest statement of the problem when it exists,
        # but the raw description is kept too so no detail is lost.
        incident_text += f"Summary: {summary}\n"
    incident_text += f"Description: {description[:MAX_DESCRIPTION_CHARS]}"

    catalogue = "\n\n".join(
        f"--- Article id={a.id} ---\nTitle: {a.title}\nContent: {(a.content or '')[:MAX_KB_CONTENT_CHARS]}"
        for a in articles
    )

    try:
        client = _client()
        log.info("🔗 Matching incident against %d KB article(s) ...", len(articles))
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": KB_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"INCIDENT:\n{incident_text}\n\nKNOWLEDGE BASE:\n{catalogue}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001 - deliberately total
        log.error("❌ Groq KB-linking call failed (%s): %s", type(exc).__name__, exc)
        return KBLinkResult(links=[], error=f"{type(exc).__name__}: {exc}")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        log.error("❌ Groq returned invalid JSON for KB links: %s | raw=%.200r", exc, raw)
        return KBLinkResult(links=[], error=f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        log.error("❌ KB-link JSON was not an object: %.200r", raw)
        return KBLinkResult(links=[], error="JSON payload was not an object")

    entries = _extract_link_list(payload)
    if entries is None:
        log.error("❌ KB-link JSON had no recognisable links array: %.200r", raw)
        return KBLinkResult(links=[], error="no links array in response")

    links: list[KBLinkSuggestion] = []
    seen: set[int] = set()
    for entry in entries:
        parsed = _parse_link(entry, valid_ids)
        if parsed is None or parsed.kb_article_id in seen:
            continue
        seen.add(parsed.kb_article_id)
        links.append(parsed)

    # Strongest first, then trim: if the model over-returns, keep its best picks.
    links.sort(key=lambda link: link.relevance_score or 0.0, reverse=True)
    if len(links) > MAX_KB_LINKS:
        log.warning("🔗 AI returned %d links; keeping the top %d", len(links), MAX_KB_LINKS)
        links = links[:MAX_KB_LINKS]

    if links:
        log.info(
            "✅ KB links: %s",
            ", ".join(f"#{link.kb_article_id}({link.relevance_score})" for link in links),
        )
    else:
        # A genuine "nothing relevant" answer, which the prompt explicitly permits.
        log.info("🔗 No KB article judged relevant")
    return KBLinkResult(links=links)


RESOLUTION_SYSTEM_PROMPT = """You are an IT service desk assistant drafting a resolution for a \
support engineer to review and edit before sending.

Reply with a single JSON object, nothing else:

{"resolution": "<the draft resolution>"}

Rules:
- Be concise and actionable. Use short numbered steps when there is more than one action.
- Write for an engineer, not the end user. No greetings, no sign-off.
- This is a draft for review, not a claim that the incident is fixed. Do not assert \
that the problem has been resolved.
- Do not invent product names, versions, ticket numbers, or configuration details \
that are not in the material you were given.
"""

GROUNDED_SUFFIX = """
- Base the resolution on the supplied knowledge base articles and follow their steps \
where they apply. If an article only partly applies, use the part that does and say \
what still needs checking.
"""

UNGROUNDED_SUFFIX = """
- No knowledge base documentation was found for this incident. Do NOT invent a \
documented procedure or imply one exists.
- Instead, suggest the general next diagnostic steps an engineer should take to narrow \
down the cause, and state what information should be gathered from the reporter.
"""


@dataclass
class ResolutionResult:
    resolution: str | None = None
    grounded: bool = False
    error: str | None = None


def suggest_resolution(
    title: str, description: str, summary: str | None, articles=()
) -> ResolutionResult:
    """Draft a resolution, grounded in `articles` when any were linked. Never raises.

    With no articles the model is told explicitly that nothing was found, so it
    proposes diagnostic next steps rather than fabricating a documented procedure.
    """
    articles = list(articles)[:MAX_KB_LINKS]
    grounded = bool(articles)

    incident_text = f"Title: {title[:MAX_TITLE_CHARS]}\n"
    if summary:
        incident_text += f"Summary: {summary}\n"
    incident_text += f"Description: {description[:MAX_DESCRIPTION_CHARS]}"

    if grounded:
        docs = "\n\n".join(
            f"--- {a.title} ---\n{(a.content or '')[:MAX_KB_CONTENT_CHARS]}" for a in articles
        )
        user_content = f"INCIDENT:\n{incident_text}\n\nKNOWLEDGE BASE ARTICLES:\n{docs}"
    else:
        user_content = (
            f"INCIDENT:\n{incident_text}\n\n"
            "KNOWLEDGE BASE ARTICLES:\n(none — no article matched this incident)"
        )

    system_prompt = RESOLUTION_SYSTEM_PROMPT + (GROUNDED_SUFFIX if grounded else UNGROUNDED_SUFFIX)

    try:
        client = _client()
        log.info(
            "📝 Drafting resolution (%s) ...",
            f"grounded in {len(articles)} article(s)" if grounded else "no KB match",
        )
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001 - deliberately total
        log.error("❌ Groq resolution call failed (%s): %s", type(exc).__name__, exc)
        return ResolutionResult(grounded=grounded, error=f"{type(exc).__name__}: {exc}")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        log.error("❌ Groq returned invalid JSON for resolution: %s | raw=%.200r", exc, raw)
        return ResolutionResult(grounded=grounded, error=f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        log.error("❌ Resolution JSON was not an object: %.200r", raw)
        return ResolutionResult(grounded=grounded, error="JSON payload was not an object")

    resolution = _first(payload, "resolution", "draft_resolution", "suggested_resolution", "text")

    # Some models answer with a list of steps rather than a string; that is usable.
    if isinstance(resolution, list):
        parts = [str(step).strip() for step in resolution if str(step).strip()]
        resolution = "\n".join(f"{n}. {part}" for n, part in enumerate(parts, 1)) if parts else None

    if not isinstance(resolution, str) or not resolution.strip():
        log.error("❌ Resolution response had no usable text: %.200r", raw)
        return ResolutionResult(grounded=grounded, error="no usable resolution in response")

    resolution = resolution.strip()
    if len(resolution) > MAX_RESOLUTION_CHARS:
        log.warning("📝 Truncating resolution from %d chars", len(resolution))
        resolution = resolution[:MAX_RESOLUTION_CHARS].rstrip()

    log.info("✅ Resolution drafted (%d chars, grounded=%s)", len(resolution), grounded)
    return ResolutionResult(resolution=resolution, grounded=grounded)


def apply_analysis(incident, result: AnalysisResult) -> list[str]:
    """Copy non-None analysis fields onto an incident. Returns the fields changed.

    Partial results are kept: if the model got the category right but botched the
    priority, the good field is still saved.
    """
    changed: list[str] = []
    if result.category is not None:
        incident.category = result.category
        changed.append("category")
    if result.priority is not None:
        incident.priority = result.priority
        changed.append("priority")
    if result.summary is not None:
        incident.ai_summary = result.summary
        changed.append("ai_summary")
    return changed
