"""Pydantic request/response models.

Body validation failures surface as 422 (FastAPI's default for request models);
semantic problems the schema can't express -- unknown ids, illegal state
transitions, bad query filters -- are raised as 400/404 in the routes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, computed_field

from app.constants import (
    CategoryLiteral,
    PriorityLiteral,
    StatusLiteral,
    category_emoji,
    priority_emoji,
    status_emoji,
)

# Whitespace-only input fails min_length because stripping happens first.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TitleStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ShortStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class IncidentCreate(BaseModel):
    """POST /incidents - only title and description are accepted at intake.

    Priority, category and the ai_* fields are populated by triage, not the caller,
    so extra='forbid' rejects them loudly rather than silently ignoring them.
    """

    model_config = ConfigDict(extra="forbid")

    title: TitleStr
    description: NonEmptyStr


class IncidentUpdate(BaseModel):
    """PATCH /incidents/{id} - every field optional, at least one required."""

    model_config = ConfigDict(extra="forbid")

    status: StatusLiteral | None = None
    priority: PriorityLiteral | None = None
    # Same vocabulary the AI emits, so a manual correction and an AI result are
    # never in different value spaces.
    category: CategoryLiteral | None = None


class IncidentResolve(BaseModel):
    """POST /incidents/{id}/resolve - notes are the point of the call, so required."""

    model_config = ConfigDict(extra="forbid")

    resolution_notes: NonEmptyStr


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    priority: str | None
    category: str | None
    ai_summary: str | None
    ai_suggested_resolution: str | None
    resolution_notes: str | None
    created_at: datetime
    resolved_at: datetime | None

    # Derived, not stored: keeps badge glyphs consistent across any client.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_emoji(self) -> str:
        return status_emoji(self.status)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def priority_emoji(self) -> str:
        return priority_emoji(self.priority)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def category_emoji(self) -> str:
        return category_emoji(self.category)


class IncidentKBLinkOut(BaseModel):
    """One AI-suggested link, with the article it points at."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_article_id: int
    relevance_score: float | None
    rationale: str | None
    kb_article: "KBArticleOut"


class IncidentDetailOut(IncidentOut):
    """GET /incidents/{id} — the incident plus its KB matches.

    Kept separate from IncidentOut so the list endpoint doesn't pay for the join.
    """

    kb_links: list[IncidentKBLinkOut] = []


class KBArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    tags: str | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tag_list(self) -> list[str]:
        """`tags` is a comma-separated column; hand clients the split form too."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]


# KBArticleOut is defined after IncidentKBLinkOut references it.
IncidentKBLinkOut.model_rebuild()
