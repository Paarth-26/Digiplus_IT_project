"""Incident CRUD and lifecycle routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session, selectinload

from app.constants import PRIORITIES, STATUSES, priority_emoji, status_emoji
from app.database import get_db
from app.models import Incident, IncidentKBLink
from app.pipeline import run_pipeline
from app.schemas import (
    IncidentCreate,
    IncidentDetailOut,
    IncidentOut,
    IncidentResolve,
    IncidentUpdate,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/incidents", tags=["incidents"])

RESOLVED = "resolved"


def get_incident_or_404(incident_id: int, db: Session) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"❌ Incident {incident_id} not found.",
        )
    return incident


def validate_filter(value: str | None, allowed: tuple[str, ...], field: str) -> str | None:
    """Query filters are validated by hand so the 400 can name the legal values.

    (Typing them as Literal would work but yields a 422, which reads as a malformed
    body rather than a bad query string.)
    """
    if value is None:
        return None
    if value not in allowed:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ Invalid {field} filter '{value}'. Allowed values: {', '.join(allowed)}.",
        )
    return value


@router.post("", response_model=IncidentOut, status_code=http_status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)) -> Incident:
    """➕ Log a new incident, then run the AI pipeline over it.

    The pipeline is best-effort: the incident is committed first, so a Groq outage
    yields a 201 with null triage fields rather than a failed creation.
    """
    incident = Incident(
        title=payload.title,
        description=payload.description,
        status="open",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    log.info("➕ Created incident #%s %s %r", incident.id, status_emoji("open"), incident.title)

    run_pipeline(incident, db)
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: str | None = Query(None, description="Filter by status: " + ", ".join(STATUSES)),
    priority: str | None = Query(None, description="Filter by priority: " + ", ".join(PRIORITIES)),
    db: Session = Depends(get_db),
) -> list[Incident]:
    """📋 List incidents, newest first, with optional status/priority filters."""
    validate_filter(status, STATUSES, "status")
    validate_filter(priority, PRIORITIES, "priority")

    query = db.query(Incident)
    if status is not None:
        query = query.filter(Incident.status == status)
    if priority is not None:
        query = query.filter(Incident.priority == priority)

    results = query.order_by(Incident.created_at.desc(), Incident.id.desc()).all()
    log.info("🔍 Listed %d incident(s) (status=%s, priority=%s)", len(results), status, priority)
    return results


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentDetailOut:
    """🎫 Fetch a single incident, including its AI-matched KB articles."""
    incident = (
        db.query(Incident)
        .options(selectinload(Incident.kb_links).selectinload(IncidentKBLink.kb_article))
        .filter(Incident.id == incident_id)
        .one_or_none()
    )
    if incident is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"❌ Incident {incident_id} not found.",
        )

    # Eager-loaded above so serialisation never depends on a live session, then
    # sorted here because the ordering is a presentation concern, not a stored one.
    detail = IncidentDetailOut.model_validate(incident)
    detail.kb_links.sort(key=lambda link: link.relevance_score or 0.0, reverse=True)
    return detail


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int, payload: IncidentUpdate, db: Session = Depends(get_db)
) -> Incident:
    """✏️ Update triage fields (status, priority, category)."""
    incident = get_incident_or_404(incident_id, db)

    # exclude_unset distinguishes "field omitted" from "field explicitly null",
    # so a caller can clear priority/category by sending null.
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="⚠️ No fields to update. Provide at least one of: status, priority, category.",
        )

    if "status" in changes:
        new_status = changes["status"]
        if new_status is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="⚠️ status cannot be null. Allowed values: " + ", ".join(STATUSES) + ".",
            )
        # Resolving carries side effects (notes + timestamp), so it gets its own
        # endpoint; allowing it here would create a second path to the same state.
        if new_status == RESOLVED:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"⚠️ Use POST /incidents/{incident_id}/resolve to resolve an incident "
                    "— it records resolution_notes and the resolved_at timestamp."
                ),
            )
        # Reopening clears the resolution timestamp so it can't outlive the state.
        if incident.status == RESOLVED and new_status != RESOLVED:
            incident.resolved_at = None
            log.info("↩️ Reopened incident #%s", incident.id)

    for field, value in changes.items():
        setattr(incident, field, value)

    db.commit()
    db.refresh(incident)
    log.info(
        "✏️ Updated incident #%s %s %s (%s)",
        incident.id,
        status_emoji(incident.status),
        priority_emoji(incident.priority),
        ", ".join(changes),
    )
    return incident


@router.post("/{incident_id}/reanalyze", response_model=IncidentOut)
def reanalyze_incident(incident_id: int, db: Session = Depends(get_db)) -> Incident:
    """🔄 Re-run AI triage on an existing incident, overwriting category/priority/ai_summary.

    Unlike creation, this reports failure: the caller explicitly asked for analysis, so
    a silent 200 with unchanged fields would be misleading. A Groq failure returns 502.
    """
    incident = get_incident_or_404(incident_id, db)
    log.info("🔄 Re-analysing incident #%s ...", incident_id)

    outcome = run_pipeline(incident, db)

    # 502 only when nothing at all worked. If one step failed but another landed,
    # data did change, and reporting a gateway error would be wrong.
    if not any((outcome["analysed"], outcome["links"], outcome["drafted"])):
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"🤖 AI analysis failed for incident {incident_id}; its fields are unchanged. "
                "See server logs for the underlying error."
            ),
        )
    return incident


@router.post("/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(
    incident_id: int, payload: IncidentResolve, db: Session = Depends(get_db)
) -> Incident:
    """✅ Resolve an incident, recording notes and the resolution timestamp."""
    incident = get_incident_or_404(incident_id, db)

    if incident.status == RESOLVED:
        when = incident.resolved_at.isoformat() if incident.resolved_at else "unknown time"
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ Incident {incident_id} is already resolved (at {when}).",
        )

    incident.status = RESOLVED
    incident.resolution_notes = payload.resolution_notes
    incident.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(incident)
    log.info("🎉 Resolved incident #%s %s", incident.id, status_emoji(RESOLVED))
    return incident
