"""AI pipeline steps shared by the API routes and the seeders.

These live outside the router because they are application services, not HTTP
concerns: `seed_incidents.py --analyze` runs exactly the same steps against rows
inserted directly into the database.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai import analyze_incident, apply_analysis, suggest_kb_links, suggest_resolution
from app.constants import category_emoji, priority_emoji
from app.models import Incident, IncidentKBLink, KBArticle

log = logging.getLogger(__name__)


def run_analysis(incident: Incident, db: Session) -> list[str]:
    """Analyse an incident and persist whatever came back. Never raises.

    The incident is already committed before this runs, so an AI failure can only
    leave the triage fields null -- it can never lose the incident itself.
    """
    result = analyze_incident(incident.title, incident.description)
    if result.error and not result.category and not result.priority and not result.summary:
        log.warning("⚠️ Incident #%s left un-analysed: %s", incident.id, result.error)
        return []

    changed = apply_analysis(incident, result)
    if changed:
        db.commit()
        db.refresh(incident)
        log.info(
            "🤖 Incident #%s analysed %s %s (%s)",
            incident.id,
            category_emoji(incident.category),
            priority_emoji(incident.priority),
            ", ".join(changed),
        )
    return changed


def run_kb_linking(incident: Incident, db: Session) -> int:
    """Match the incident against the KB and replace its links. Never raises.

    Returns the number of links written. Zero is a legitimate outcome -- either no
    article was relevant, or the step failed; the two are distinguished in the logs,
    not in the return value, because neither should affect the caller's response.
    """
    try:
        articles = db.query(KBArticle).order_by(KBArticle.id).all()
        result = suggest_kb_links(
            incident.title, incident.description, incident.ai_summary, articles
        )

        if result.error:
            log.warning("⚠️ Incident #%s KB linking failed: %s", incident.id, result.error)
            return 0

        # Replace rather than append: re-running must not accumulate stale matches,
        # and the (incident_id, kb_article_id) unique constraint would reject dupes.
        removed = (
            db.query(IncidentKBLink).filter(IncidentKBLink.incident_id == incident.id).delete()
        )
        if removed:
            log.info("🔗 Cleared %d previous KB link(s) for incident #%s", removed, incident.id)

        for suggestion in result.links:
            db.add(
                IncidentKBLink(
                    incident_id=incident.id,
                    kb_article_id=suggestion.kb_article_id,
                    relevance_score=suggestion.relevance_score,
                    rationale=suggestion.rationale,
                )
            )
        db.commit()

        if result.links:
            log.info("🔗 Incident #%s linked to %d KB article(s)", incident.id, len(result.links))
        else:
            log.info("🔗 Incident #%s: no relevant KB article", incident.id)
        return len(result.links)
    except Exception as exc:  # noqa: BLE001 - linking must never break the caller
        log.error("❌ KB linking blew up for incident #%s: %s", incident.id, exc)
        db.rollback()
        return 0


def run_resolution_draft(incident: Incident, db: Session) -> bool:
    """Draft `ai_suggested_resolution`. Never raises. Returns whether one was saved.

    Runs whether or not KB linking found anything: with articles the draft is grounded
    in them, without any the model is told none were found and asked for diagnostic
    next steps instead.
    """
    try:
        articles = [
            link.kb_article
            for link in sorted(
                incident.kb_links, key=lambda link: link.relevance_score or 0.0, reverse=True
            )
            if link.kb_article is not None
        ]

        result = suggest_resolution(
            incident.title, incident.description, incident.ai_summary, articles
        )
        if not result.resolution:
            log.warning(
                "⚠️ Incident #%s has no drafted resolution: %s", incident.id, result.error
            )
            return False

        incident.ai_suggested_resolution = result.resolution
        db.commit()
        db.refresh(incident)
        log.info(
            "📝 Incident #%s resolution drafted (%s)",
            incident.id,
            f"from {len(articles)} KB article(s)" if result.grounded else "no KB match",
        )
        return True
    except Exception as exc:  # noqa: BLE001 - drafting must never break the caller
        log.error("❌ Resolution drafting blew up for incident #%s: %s", incident.id, exc)
        db.rollback()
        return False


def run_pipeline(incident: Incident, db: Session, link_kb: bool = True, draft: bool = True) -> dict:
    """Run the full analyse → link → draft pipeline. Never raises.

    Each step is independent: a failure in one leaves the others' results intact, and
    none of them can fail the caller's request.
    """
    changed = run_analysis(incident, db)
    links = run_kb_linking(incident, db) if link_kb else 0
    drafted = run_resolution_draft(incident, db) if draft else False
    return {"analysed": changed, "links": links, "drafted": drafted}
