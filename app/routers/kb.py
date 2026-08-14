"""Knowledge base routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import KBArticle
from app.schemas import KBArticleOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/kb", tags=["knowledge base"])


@router.get("", response_model=list[KBArticleOut])
def list_kb_articles(
    tag: str | None = Query(None, description="Case-insensitive substring match on tags"),
    db: Session = Depends(get_db),
) -> list[KBArticle]:
    """📚 List knowledge base articles."""
    query = db.query(KBArticle)
    if tag:
        # tags is a comma-separated column, so this is a substring match rather
        # than an exact one. Fine at this size; revisit if tags get their own table.
        query = query.filter(KBArticle.tags.ilike(f"%{tag}%"))

    results = query.order_by(KBArticle.id).all()
    log.info("📚 Listed %d KB article(s) (tag=%s)", len(results), tag)
    return results
