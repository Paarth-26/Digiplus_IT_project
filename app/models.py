from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Free-form on purpose; constrain later if the workflow settles.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggested_resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    kb_links: Mapped[list["IncidentKBLink"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Incident id={self.id} status={self.status!r} title={self.title!r}>"


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Comma-separated tags — keeps SQLite simple; split into a table if querying by tag grows.
    tags: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    incident_links: Mapped[list["IncidentKBLink"]] = relationship(
        back_populates="kb_article", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KBArticle id={self.id} title={self.title!r}>"


class IncidentKBLink(Base):
    __tablename__ = "incident_kb_links"
    __table_args__ = (
        UniqueConstraint("incident_id", "kb_article_id", name="uq_incident_kb_pair"),
        Index("ix_incident_kb_links_incident_id", "incident_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    kb_article_id: Mapped[int] = mapped_column(
        ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False
    )
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="kb_links")
    kb_article: Mapped["KBArticle"] = relationship(back_populates="incident_links")

    def __repr__(self) -> str:
        return f"<IncidentKBLink incident={self.incident_id} kb={self.kb_article_id}>"
