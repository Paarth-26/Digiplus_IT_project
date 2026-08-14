"""Seed the `incidents` table with sample tickets from the HuggingFace dataset.

Source: https://huggingface.co/datasets/mindweave/help-desk-tickets (config: tickets)

Only `title`, `description`, and `status='open'` are populated. The fields intended
to be produced by AI analysis -- `category`, `priority`, `ai_summary`,
`ai_suggested_resolution` -- are deliberately left NULL, as are `resolution_notes`
and `resolved_at`.

There is no hand-written fallback here (unlike seed_kb.py): fabricated incidents
would be indistinguishable from real ones in the UI, so a failed download exits
non-zero instead.

Passing --analyze runs the Groq triage step over incidents afterwards, filling
`category`, `priority`, and `ai_summary` -- the same analysis `POST /incidents`
performs, applied to rows that were inserted directly into the database.

Usage:
    python seed_incidents.py                  # 12 incidents, no AI
    python seed_incidents.py --limit 15
    python seed_incidents.py --reset          # delete existing incidents first
    python seed_incidents.py --with-comments  # append agent comment threads
    python seed_incidents.py --analyze        # seed, then analyse anything unanalysed
    python seed_incidents.py --analyze-only   # skip seeding; just backfill existing rows
    python seed_incidents.py --analyze-only --reanalyze-all   # redo every incident
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import or_

from app.constants import category_emoji, configure_console, priority_emoji
from app.database import SessionLocal, init_db
from app.models import Incident
from app.pipeline import run_pipeline
from hf_source import REPO_ID, TICKETS_CONFIG, load_comments_map, load_config, pick_column

configure_console()  # emoji-safe stdout even when output is piped

TITLE_COLUMNS = ("summary", "title", "subject", "short_description", "issue")
DESCRIPTION_COLUMNS = ("description", "body", "content", "text")

# Populated only by the AI step later; listed here so the intent is explicit.
AI_FIELDS = ("category", "priority", "ai_summary", "ai_suggested_resolution")


def load_incident_rows(limit: int, timeout: float, with_comments: bool) -> list[dict]:
    ds = load_config(TICKETS_CONFIG, timeout)

    columns = list(ds.column_names)
    print(f"  📊 rows: {len(ds)}")
    print(f"  🧮 columns ({len(columns)}): {', '.join(columns)}")

    title_col = pick_column(columns, TITLE_COLUMNS)
    desc_col = pick_column(columns, DESCRIPTION_COLUMNS)
    if not title_col or not desc_col:
        raise RuntimeError(f"could not map title/description onto columns {columns}")
    print(f"  🗺️  mapping -> title={title_col!r}, description={desc_col!r}")
    print(f"  🤖 leaving NULL (for AI): {', '.join(AI_FIELDS)}, resolution_notes, resolved_at")

    comments = load_comments_map(timeout) if with_comments else {}

    rows: list[dict] = []
    seen: set[str] = set()
    for record in ds:
        title = (record.get(title_col) or "").strip()
        description = (record.get(desc_col) or "").strip()
        if not title or not description:
            continue
        key = title.lower()
        if key in seen:  # synthetic data repeats summaries
            continue
        seen.add(key)

        notes = comments.get(record.get("ticket_id"), [])
        if notes:
            description += "\n\nAgent notes:\n" + "\n".join(f"- {n}" for n in notes)

        rows.append({"title": title[:255], "description": description, "status": "open"})
        if len(rows) >= limit:
            break

    if not rows:
        raise RuntimeError("dataset loaded but produced 0 usable rows")
    return rows


def seed(rows: list[dict], reset: bool) -> tuple[int, int]:
    """Insert rows, skipping titles that already exist. Returns (inserted, skipped)."""
    inserted = skipped = 0
    with SessionLocal() as session:
        if reset:
            deleted = session.query(Incident).delete()
            session.commit()
            print(f"  🗑️  --reset: removed {deleted} existing incident(s)")

        existing = {t.lower() for (t,) in session.query(Incident.title).all()}
        for row in rows:
            if row["title"].lower() in existing:
                skipped += 1
                continue
            # Every unset column stays NULL: category, priority, ai_summary,
            # ai_suggested_resolution, resolution_notes, resolved_at.
            session.add(Incident(**row))
            existing.add(row["title"].lower())
            inserted += 1
        session.commit()
    return inserted, skipped


def analyze_incidents(
    reanalyze_all: bool, delay: float, link_kb: bool = True, draft: bool = True
) -> tuple[int, int]:
    """Run AI triage over stored incidents. Returns (analysed, failed).

    One commit per incident, so a failure partway through keeps the work already
    done. Individual failures are logged and skipped -- one bad row must not abort
    the batch.
    """
    with SessionLocal() as session:
        query = session.query(Incident)
        if not reanalyze_all:
            # "Unanalysed" means any triage field is still missing, so a partial
            # result from an earlier run gets another attempt at the rest.
            query = query.filter(
                or_(
                    Incident.category.is_(None),
                    Incident.priority.is_(None),
                    Incident.ai_summary.is_(None),
                    Incident.ai_suggested_resolution.is_(None),
                )
            )
        targets = query.order_by(Incident.id).all()

        if not targets:
            print("✨ Nothing to analyse — every incident already has triage fields.")
            return 0, 0

        scope = "all" if reanalyze_all else "unanalysed"
        print(f"🤖 Analysing {len(targets)} {scope} incident(s) ...")

        analysed = failed = 0
        for position, incident in enumerate(targets, 1):
            # Same pipeline the API runs on POST /incidents, so seeded rows end up
            # indistinguishable from ones created through the endpoint.
            outcome = run_pipeline(incident, session, link_kb=link_kb, draft=draft)

            if outcome["analysed"]:
                analysed += 1
                notes = ""
                if link_kb:
                    notes += f" 🔗 {outcome['links']} link(s)"
                if draft:
                    notes += " 📝" if outcome["drafted"] else " 📝✗"
                print(
                    f"  ✅ [{position}/{len(targets)}] #{incident.id} "
                    f"{category_emoji(incident.category)} {incident.category} / "
                    f"{priority_emoji(incident.priority)} {incident.priority}{notes}"
                )
            else:
                failed += 1
                print(
                    f"  ❌ [{position}/{len(targets)}] #{incident.id} analysis failed "
                    "(see logged error above)",
                    file=sys.stderr,
                )

            # Gentle pacing option for rate-limited keys; off by default.
            if delay and position < len(targets):
                time.sleep(delay)

    return analysed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the incidents table from HuggingFace.")
    parser.add_argument("--limit", type=int, default=12, help="max incidents to insert (default 12)")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait on HF (default 60)")
    parser.add_argument("--reset", action="store_true", help="delete existing incidents first")
    parser.add_argument(
        "--with-comments",
        action="store_true",
        help="append agent comment threads to the description (generic filler in this dataset)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="after seeding, run AI triage on incidents that lack category/priority/ai_summary",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="skip seeding entirely and only backfill analysis on existing incidents",
    )
    parser.add_argument(
        "--reanalyze-all",
        action="store_true",
        help="with --analyze, include incidents that already have triage fields",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds to wait between AI calls, for rate-limited keys (default 0)",
    )
    parser.add_argument(
        "--no-links",
        action="store_true",
        help="skip KB matching during analysis (saves one Groq call per incident)",
    )
    parser.add_argument(
        "--no-resolution",
        action="store_true",
        help="skip drafting ai_suggested_resolution (saves one Groq call per incident)",
    )
    args = parser.parse_args()

    init_db()

    # --analyze-only and --reanalyze-all both imply analysis; asking for either
    # without --analyze is obviously an analysis request, so don't be pedantic.
    do_analyze = args.analyze or args.analyze_only or args.reanalyze_all

    if not args.analyze_only:
        print(f"🤗 Loading incidents from {REPO_ID} ...")
        try:
            rows = load_incident_rows(args.limit, args.timeout, args.with_comments)
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ failed: {exc}", file=sys.stderr)
            print("  🛑 no fallback for incidents - rerun when the dataset is reachable.", file=sys.stderr)
            return 1

        inserted, skipped = seed(rows, args.reset)
        print(f"\n➕ Inserted : {inserted}")
        print(f"⏭️  Skipped  : {skipped} (title already present)")

    analysed = failed = 0
    if do_analyze:
        print()
        analysed, failed = analyze_incidents(
            args.reanalyze_all, args.delay, not args.no_links, not args.no_resolution
        )
        print(f"\n🤖 Analysed : {analysed}")
        if failed:
            print(f"❌ Failed   : {failed} (fields left null; see errors above)")

    with SessionLocal() as session:
        total = session.query(Incident).count()
        open_count = session.query(Incident).filter(Incident.status == "open").count()
        unanalysed = (
            session.query(Incident)
            .filter(
                or_(
                    Incident.category.is_(None),
                    Incident.priority.is_(None),
                    Incident.ai_summary.is_(None),
                    Incident.ai_suggested_resolution.is_(None),
                )
            )
            .count()
        )
    print(f"🎫 Total incidents now: {total} ({open_count} open, {unanalysed} unanalysed)")

    # Non-zero only if analysis was asked for and nothing at all worked.
    return 1 if (do_analyze and failed and not analysed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
