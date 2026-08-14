"""Seed `kb_articles` from the HuggingFace help-desk-tickets dataset.

Primary source : https://huggingface.co/datasets/mindweave/help-desk-tickets
Fallback       : 10 hand-written IT support articles (used if the download fails,
                 times out, or the `datasets` package isn't installed).

Usage:
    python seed_kb.py                 # auto: try HF, fall back on failure/timeout
    python seed_kb.py --source hf     # HF only; exit non-zero rather than fall back
    python seed_kb.py --source fallback
    python seed_kb.py --limit 20 --timeout 90
    python seed_kb.py --reset         # delete existing kb_articles first
"""

from __future__ import annotations

import argparse
import sys

from app.constants import configure_console
from app.database import SessionLocal, init_db
from app.models import KBArticle
from hf_source import REPO_ID, TICKETS_CONFIG, load_comments_map, load_config, pick_column

configure_console()  # emoji-safe stdout even when output is piped

# Preferred column names, best first. Auto-detection keeps the script working if
# the dataset's schema shifts.
TITLE_COLUMNS = ("summary", "title", "subject", "short_description", "issue")
CONTENT_COLUMNS = ("resolution", "resolution_notes", "description", "body", "content", "text")
TAG_COLUMNS = ("affected_service", "priority", "category", "requester_department", "channel")


# --------------------------------------------------------------------------
# HuggingFace path
# --------------------------------------------------------------------------
def load_hf_rows(limit: int, timeout: float) -> list[dict]:
    """Download the tickets table and shape rows into KB article dicts."""
    ds = load_config(TICKETS_CONFIG, timeout)

    columns = list(ds.column_names)
    print(f"  📊 rows: {len(ds)}")
    print(f"  🧮 columns ({len(columns)}): {', '.join(columns)}")

    title_col = pick_column(columns, TITLE_COLUMNS)
    content_col = pick_column(columns, CONTENT_COLUMNS)
    if not title_col or not content_col:
        raise RuntimeError(
            f"could not map title/content onto columns {columns}"
        )
    tag_cols = [c for c in (pick_column(columns, (t,)) for t in TAG_COLUMNS) if c]
    print(f"  🗺️  mapping -> title={title_col!r}, content={content_col!r}, tags={tag_cols}")

    # This dataset has no resolution column; the closest thing to resolution text is
    # the threaded agent comments, so fold them in when they're available.
    comments_by_ticket = load_comments_map(timeout)

    rows: list[dict] = []
    seen_titles: set[str] = set()
    for record in ds:
        title = (record.get(title_col) or "").strip()
        content = (record.get(content_col) or "").strip()
        if not title or not content:
            continue
        # Synthetic data repeats summaries; keep the KB varied.
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        notes = comments_by_ticket.get(record.get("ticket_id"), [])
        if notes:
            content = content + "\n\nAgent notes:\n" + "\n".join(f"- {n}" for n in notes)

        tags = [str(record[c]) for c in tag_cols if record.get(c) not in (None, "")]
        rows.append(
            {
                "title": title[:255],
                "content": content,
                "tags": ", ".join(tags) or None,
            }
        )
        if len(rows) >= limit:
            break

    if not rows:
        raise RuntimeError("dataset loaded but produced 0 usable rows")
    return rows


# --------------------------------------------------------------------------
# fallback path
# --------------------------------------------------------------------------
FALLBACK_ARTICLES: list[dict] = [
    {
        "title": "Resetting a forgotten account password",
        "tags": "identity, password, self-service",
        "content": (
            "Applies to staff who cannot sign in to their corporate account.\n\n"
            "1. Direct the user to the self-service reset portal and have them verify with their "
            "registered MFA method.\n"
            "2. If MFA is unavailable, verify identity with the user's manager before any manual reset.\n"
            "3. Issue a temporary password flagged 'must change at next sign-in'.\n"
            "4. Confirm the user can sign in, then revoke all active sessions so old tokens die.\n\n"
            "If lockouts repeat within 24h, check for a stale cached credential on a phone or a "
            "mapped drive still presenting the old password."
        ),
    },
    {
        "title": "VPN connects but internal resources are unreachable",
        "tags": "network, vpn, remote-access",
        "content": (
            "Symptom: the VPN client reports 'Connected' but internal hosts time out.\n\n"
            "1. Confirm the user is on the correct tunnel profile — split tunnel will not route "
            "internal ranges.\n"
            "2. Check for a home-network subnet that collides with the corporate range; a 192.168.1.x "
            "clash silently breaks routing.\n"
            "3. Flush DNS and confirm the client picked up internal resolvers.\n"
            "4. Re-authenticate to refresh an expired posture check.\n\n"
            "Escalate to Network if the tunnel is up and routes are correct but traffic still drops."
        ),
    },
    {
        "title": "Network printer shows offline",
        "tags": "endpoint, printing, hardware",
        "content": (
            "1. Confirm the printer is powered on and its panel shows a valid IP on the corporate "
            "network.\n"
            "2. Ping the printer's IP from the user's machine to separate a network fault from a "
            "driver fault.\n"
            "3. Clear the local print spooler queue and restart the spooler service.\n"
            "4. Remove and re-add the printer by IP rather than by discovered name — discovery entries "
            "go stale after a DHCP change.\n\n"
            "Recurring offline states usually mean the printer is on DHCP; request a reservation."
        ),
    },
    {
        "title": "Laptop running slowly",
        "tags": "endpoint, performance, hardware",
        "content": (
            "1. Check resource usage for a single process pinning CPU, memory, or disk — most cases "
            "are one runaway app, a stuck sync client, or a background AV scan.\n"
            "2. Confirm free disk space is above 15%; a nearly full SSD degrades sharply.\n"
            "3. Review startup items and disable anything not required.\n"
            "4. Check pending OS updates and reboot uptime — machines up for weeks accumulate leaks.\n\n"
            "If the device is out of warranty and still slow after cleanup, route to hardware refresh."
        ),
    },
    {
        "title": "Email not syncing on desktop or mobile",
        "tags": "email, sync, collaboration",
        "content": (
            "1. Verify mail loads in the web client — if it does, the fault is local to the client.\n"
            "2. Check the mailbox is under quota; a full mailbox blocks send and receive.\n"
            "3. Re-enter credentials; token expiry after a password change is the most common cause.\n"
            "4. On mobile, confirm background app refresh is enabled and the device has a current "
            "management profile.\n\n"
            "For a corrupt local profile, rebuild the cached data file rather than reinstalling."
        ),
    },
    {
        "title": "Software install blocked by permissions",
        "tags": "endpoint, permissions, software",
        "content": (
            "Standard accounts cannot install software directly; this is intended.\n\n"
            "1. Check whether the title is already in the self-service software portal — most requests "
            "are satisfied there with no ticket.\n"
            "2. If not listed, confirm licensing and security review status before proceeding.\n"
            "3. For approved one-off installs, use the elevation tool for a time-boxed session rather "
            "than granting standing admin rights.\n\n"
            "Never hand out permanent local admin to resolve a single install."
        ),
    },
    {
        "title": "Wi-Fi keeps dropping in the office",
        "tags": "network, wifi, connectivity",
        "content": (
            "1. Confirm the user is on the corporate SSID and not a guest or personal hotspot.\n"
            "2. Check whether the drop is location-specific — a single dead zone points at AP "
            "coverage, not the device.\n"
            "3. Forget and rejoin the network to clear a stale profile.\n"
            "4. Update the wireless adapter driver; older drivers roam badly between APs.\n\n"
            "If several users in one area report drops at once, treat it as an AP fault and escalate "
            "to Network rather than troubleshooting devices individually."
        ),
    },
    {
        "title": "Disk space full on a workstation",
        "tags": "endpoint, storage, maintenance",
        "content": (
            "1. Clear temp directories, browser caches, and the recycle bin first — this usually "
            "recovers several GB.\n"
            "2. Look for oversized local copies of cloud-synced folders and large stale downloads.\n"
            "3. Remove old OS update rollback data if the current build has been stable.\n"
            "4. Move archival material to approved cloud storage instead of local disk.\n\n"
            "Document the recovered amount; a machine refilling within weeks needs a storage upgrade "
            "or a sync-scope change, not another cleanup."
        ),
    },
    {
        "title": "Lost or replaced MFA device",
        "tags": "identity, mfa, security",
        "content": (
            "Treat a lost MFA device as a potential security event, not just an access problem.\n\n"
            "1. Verify identity out-of-band — a live video call or in-person check with the manager. "
            "Never re-enroll MFA on the strength of an email request alone.\n"
            "2. Revoke the lost device's registration and invalidate active sessions.\n"
            "3. Walk the user through enrolling the replacement, and register a backup method at the "
            "same time.\n"
            "4. If the device may have been stolen, raise a security incident alongside the ticket.\n\n"
            "Issue temporary bypass codes only with documented approval and a short expiry."
        ),
    },
    {
        "title": "Screen sharing fails in meetings",
        "tags": "collaboration, meetings, endpoint",
        "content": (
            "1. On macOS, confirm the meeting app has Screen Recording permission — this is the single "
            "most common cause after an OS update, which silently resets it.\n"
            "2. Restart the app fully after granting permission; the setting is only read at launch.\n"
            "3. Check for a pending client update; hosts often block outdated clients from sharing.\n"
            "4. On multi-monitor setups, try sharing a single window to isolate a GPU or scaling issue.\n\n"
            "If sharing starts but viewers see a black screen, disable hardware acceleration in the "
            "meeting client."
        ),
    },
]


def load_fallback_rows(limit: int) -> list[dict]:
    return [dict(a) for a in FALLBACK_ARTICLES[:limit]]


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------
def seed(rows: list[dict], reset: bool) -> tuple[int, int]:
    """Insert rows, skipping titles that already exist. Returns (inserted, skipped)."""
    inserted = skipped = 0
    with SessionLocal() as session:
        if reset:
            deleted = session.query(KBArticle).delete()
            session.commit()
            print(f"  🗑️  --reset: removed {deleted} existing article(s)")

        existing = {t.lower() for (t,) in session.query(KBArticle.title).all()}
        for row in rows:
            if row["title"].lower() in existing:
                skipped += 1
                continue
            session.add(KBArticle(**row))
            existing.add(row["title"].lower())
            inserted += 1
        session.commit()
    return inserted, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed kb_articles.")
    parser.add_argument("--source", choices=("auto", "hf", "fallback"), default="auto")
    parser.add_argument("--limit", type=int, default=18, help="max articles to insert (default 18)")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait on HF (default 60)")
    parser.add_argument("--reset", action="store_true", help="delete existing kb_articles first")
    args = parser.parse_args()

    init_db()

    rows: list[dict] = []
    source = ""

    if args.source in ("auto", "hf"):
        print(f"🤗 Attempting HuggingFace source ({REPO_ID}) ...")
        try:
            rows = load_hf_rows(args.limit, args.timeout)
            source = "huggingface"
            print(f"  ✅ {len(rows)} article(s) prepared from the dataset")
        except Exception as exc:  # noqa: BLE001 - any failure means fall back
            print(f"  ❌ HuggingFace load failed: {exc}", file=sys.stderr)
            if args.source == "hf":
                print("  🛑 --source hf was requested, so not falling back.", file=sys.stderr)
                return 1

    if not rows:
        print("✍️  Using hand-written fallback articles ...")
        rows = load_fallback_rows(min(args.limit, len(FALLBACK_ARTICLES)))
        source = "fallback"

    inserted, skipped = seed(rows, args.reset)
    print(f"\n📦 Source   : {source}")
    print(f"➕ Inserted : {inserted}")
    print(f"⏭️  Skipped  : {skipped} (title already present)")

    with SessionLocal() as session:
        total = session.query(KBArticle).count()
    print(f"📚 Total kb_articles now: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
