"""Shared loader for the mindweave/help-desk-tickets HuggingFace dataset.

Used by both `seed_kb.py` and `seed_incidents.py` so the timeout handling, config
selection, and column detection live in one place.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable

REPO_ID = "mindweave/help-desk-tickets"
# The repo's *default* config is `agents` (a staff roster). Ticket text lives in
# `tickets`, so the config name must always be passed explicitly.
TICKETS_CONFIG = "tickets"
COMMENTS_CONFIG = "comments"


def run_with_timeout(fn: Callable[[], Any], timeout: float, label: str) -> Any:
    """Run `fn` in a daemon thread, raising TimeoutError if it overruns.

    A daemon thread (rather than ThreadPoolExecutor) is deliberate: a hung network
    call can't be killed, and the pool's atexit join would then block interpreter
    exit. A daemon thread is simply abandoned when the process ends.
    """
    box: dict[str, Any] = {}

    def runner() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True, name=f"seed-{label}")
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError(f"{label} exceeded {timeout:g}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


def pick_column(available: list[str], candidates: tuple[str, ...]) -> str | None:
    """First candidate present in `available`, case-insensitively."""
    lowered = {c.lower(): c for c in available}
    for want in candidates:
        if want in lowered:
            return lowered[want]
    return None


def load_config(config: str, timeout: float, quiet: bool = False):
    """Load one config of the dataset, bounded by `timeout`."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "the `datasets` package is not installed (pip install datasets)"
        ) from exc

    # Bound the per-file HTTP timeout too, so a stalled socket doesn't sit until
    # the outer thread timeout fires.
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", str(max(10, int(timeout // 2))))

    if not quiet:
        print(f"  ⬇️  loading {REPO_ID} (config={config!r}, timeout={timeout:g}s) ...")
    return run_with_timeout(
        lambda: load_dataset(REPO_ID, config, split="train"),
        timeout,
        f"load_dataset[{config}]",
    )


def load_comments_map(timeout: float) -> dict[Any, list[str]]:
    """Best-effort map of ticket_id -> deduped comment bodies. Never fatal."""
    try:
        ds = load_config(COMMENTS_CONFIG, timeout, quiet=True)
        if "ticket_id" not in ds.column_names or "body" not in ds.column_names:
            return {}

        grouped: dict[Any, list[str]] = {}
        for row in ds:
            body = (row.get("body") or "").strip()
            if not body:
                continue
            bucket = grouped.setdefault(row["ticket_id"], [])
            if body not in bucket:  # synthetic rows duplicate heavily
                bucket.append(body)
        print(f"  💬 enriched with comments for {len(grouped)} tickets")
        return grouped
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  (skipping comment enrichment: {exc})")
        return {}
