"""Streamlit frontend for the Support Incident Triage Assistant.

Talks to the FastAPI backend over HTTP only -- it imports nothing from the `app`
package, so the two can run and be restarted independently.

Run the backend first, then:
    streamlit run app.py
"""

import os

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")

# Creating an incident runs three sequential Groq calls server-side, so it needs a
# far longer timeout than a plain read.
READ_TIMEOUT = 15
WRITE_TIMEOUT = 120

STATUS_OPTIONS = ["All", "open", "in_progress", "resolved"]
PRIORITY_OPTIONS = ["All", "critical", "high", "medium", "low"]

# Fallbacks only. The API returns status_emoji / priority_emoji / category_emoji on
# every incident, and those are preferred so the badge mapping lives in one place.
STATUS_EMOJI = {"open": "🔵", "in_progress": "🟡", "resolved": "🟢"}
PRIORITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

PENDING_TEXT = "AI analysis pending ⏳"

st.set_page_config(
    layout="wide",
    page_title="Support Incident Triage Assistant",
    page_icon="🎯",
)


# --------------------------------------------------------------------------
# styling
# --------------------------------------------------------------------------
def inject_css() -> None:
    """Custom theme.

    Deliberately scoped to our own class names wherever possible. Only a handful of
    Streamlit's own test ids are touched, so a Streamlit upgrade that renames
    internals degrades the look rather than breaking the page.
    """
    st.markdown(
        """
        <style>
        :root {
            --accent: #4f46e5;
            --accent-soft: #eef2ff;
            --bg: #f5f6fa;
            --card: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --border: #e5e7eb;
        }

        .stApp { background: var(--bg); }

        /* Tighten the default top padding so the header sits high on the page. */
        .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }

        /* ---- branded header ---- */
        .app-header {
            background: linear-gradient(135deg, #4f46e5 0%, #6366f1 55%, #818cf8 100%);
            border-radius: 16px;
            padding: 1.5rem 1.75rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 10px 24px rgba(79, 70, 229, 0.22);
        }
        .app-header h1 {
            color: #ffffff; font-size: 1.75rem; font-weight: 700;
            margin: 0 0 0.3rem 0; letter-spacing: -0.02em; line-height: 1.2;
        }
        .app-header p { color: rgba(255,255,255,0.88); margin: 0; font-size: 0.95rem; }

        /* ---- KPI tiles ---- */
        .kpi {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 12px; padding: 0.85rem 1rem;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.06);
        }
        .kpi .kpi-label {
            color: var(--muted); font-size: 0.75rem; text-transform: uppercase;
            letter-spacing: 0.06em; font-weight: 600; margin-bottom: 0.2rem;
        }
        .kpi .kpi-value { color: var(--text); font-size: 1.6rem; font-weight: 700; line-height: 1; }

        /* ---- cards ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--card);
            border-radius: 14px !important;
            border: 1px solid var(--border) !important;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.06), 0 8px 20px rgba(16, 24, 40, 0.04);
        }

        .card-title {
            font-size: 1.02rem; font-weight: 650; color: var(--text);
            margin: 0 0 0.15rem 0; line-height: 1.35;
        }
        .card-id { color: var(--muted); font-weight: 600; font-size: 0.85rem; }
        .card-summary {
            color: var(--muted); font-size: 0.9rem; line-height: 1.5;
            margin: 0.5rem 0 0.1rem 0;
        }
        .card-pending { color: #b45309; font-size: 0.9rem; font-style: italic; margin-top: 0.5rem; }

        /* ---- pill badges ---- */
        .pill-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.55rem 0 0.2rem 0; }
        .pill {
            display: inline-flex; align-items: center; gap: 0.3rem;
            padding: 0.16rem 0.6rem; border-radius: 999px;
            font-size: 0.78rem; font-weight: 600; line-height: 1.5;
            border: 1px solid transparent; white-space: nowrap;
        }
        .pill-open        { background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; }
        .pill-in_progress { background:#fffbeb; color:#b45309; border-color:#fde68a; }
        .pill-resolved    { background:#ecfdf5; color:#047857; border-color:#a7f3d0; }
        .pill-critical    { background:#fef2f2; color:#b91c1c; border-color:#fecaca; }
        .pill-high        { background:#fff7ed; color:#c2410c; border-color:#fed7aa; }
        .pill-medium      { background:#fefce8; color:#a16207; border-color:#fef08a; }
        .pill-low         { background:#f0fdf4; color:#15803d; border-color:#bbf7d0; }
        .pill-category    { background:var(--accent-soft); color:#4338ca; border-color:#c7d2fe; }
        .pill-muted       { background:#f3f4f6; color:#6b7280; border-color:#e5e7eb; }

        /* ---- KB article block inside the detail dialog ---- */
        .kb-card {
            border: 1px solid var(--border); border-left: 3px solid var(--accent);
            border-radius: 10px; padding: 0.75rem 0.9rem; margin-bottom: 0.6rem;
            background: #fcfcff;
        }
        .kb-title { font-weight: 650; color: var(--text); font-size: 0.95rem; }
        .kb-rationale { color: var(--muted); font-size: 0.86rem; margin-top: 0.3rem; line-height: 1.5; }
        .kb-score {
            float: right; background: var(--accent-soft); color: #4338ca;
            border-radius: 999px; padding: 0.1rem 0.55rem;
            font-size: 0.75rem; font-weight: 700;
        }

        .section-label {
            font-size: 0.78rem; font-weight: 700; color: var(--muted);
            text-transform: uppercase; letter-spacing: 0.06em; margin: 0.2rem 0 0.35rem 0;
        }

        .empty-state {
            text-align: center; padding: 2.5rem 1rem; color: var(--muted);
            background: var(--card); border: 1px dashed var(--border); border-radius: 14px;
        }
        .empty-state .emoji { font-size: 2.2rem; display: block; margin-bottom: 0.5rem; }

        /* ---- buttons ---- */
        .stButton > button { border-radius: 9px; font-weight: 600; transition: all 0.15s ease; }
        .stButton > button[kind="primary"] {
            background: var(--accent); border-color: var(--accent);
        }
        .stButton > button[kind="primary"]:hover:enabled {
            background: #4338ca; border-color: #4338ca;
        }
        .stButton > button:focus-visible { outline: 3px solid #a5b4fc; outline-offset: 2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


# --------------------------------------------------------------------------
# API helpers  (unchanged behaviour -- same endpoints, params and payloads)
# --------------------------------------------------------------------------
def api_call(method: str, path: str, **kwargs):
    """Return (data, error_message). Never raises, so the UI always renders."""
    url = f"{API_BASE}{path}"
    try:
        response = requests.request(method, url, **kwargs)
    except requests.exceptions.ConnectionError:
        return None, f"Cannot reach the API at {API_BASE}. Is the backend running?"
    except requests.exceptions.Timeout:
        return None, "The API took too long to respond."
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed: {exc}"

    if response.ok:
        try:
            return response.json(), None
        except ValueError:
            return None, "The API returned a response that was not JSON."

    # FastAPI puts a readable message in `detail`; validation errors nest it deeper.
    try:
        payload = response.json()
        detail = payload.get("detail", payload)
    except ValueError:
        detail = response.text or f"HTTP {response.status_code}"

    if isinstance(detail, list):  # 422 validation errors
        detail = "; ".join(
            f"{'.'.join(str(p) for p in item.get('loc', [])[1:])}: {item.get('msg', '')}".strip(": ")
            for item in detail
        )
    return None, f"{response.status_code} — {detail}"


def fetch_incidents(status: str, priority: str):
    params = {}
    if status != "All":
        params["status"] = status
    if priority != "All":
        params["priority"] = priority
    return api_call("GET", "/incidents", params=params, timeout=READ_TIMEOUT)


# --------------------------------------------------------------------------
# toasts + dialog routing
# --------------------------------------------------------------------------
def queue_toast(message: str, icon: str = "✅") -> None:
    """Queue a toast to survive the st.rerun() that follows a write.

    A toast raised immediately before st.rerun() is discarded by the rerun, so
    feedback has to be stashed and emitted on the next run instead.
    """
    st.session_state.setdefault("_toasts", []).append((message, icon))


def flush_toasts() -> None:
    for message, icon in st.session_state.pop("_toasts", []):
        st.toast(message, icon=icon)


def open_dialog(name: str, incident_id: int | None = None, rerun: bool = False) -> None:
    """Mark a dialog to open at the dispatch point near the end of the script.

    Deliberately does NOT rerun by default. Calling st.rerun() from a button that
    sits above the filter widgets would abort the run before those widgets render,
    and Streamlit discards the state of widgets a run didn't draw -- which silently
    reset the Status/Priority filters. Only a caller that is already past the main
    render (i.e. inside a dialog) may pass rerun=True.
    """
    st.session_state["dialog"] = name
    st.session_state["dialog_incident"] = incident_id
    if rerun:
        st.rerun()


def close_dialog() -> None:
    st.session_state["dialog"] = None
    st.session_state["dialog_incident"] = None
    st.rerun()


# --------------------------------------------------------------------------
# presentation helpers
# --------------------------------------------------------------------------
def pill(label: str, kind: str, emoji: str = "") -> str:
    prefix = f"{emoji} " if emoji else ""
    return f'<span class="pill pill-{kind}">{prefix}{label}</span>'


def badge_row(incident: dict) -> str:
    """Status / priority / category pills. Never colour-only -- each carries text."""
    status = incident.get("status") or "unknown"
    status_icon = incident.get("status_emoji") or STATUS_EMOJI.get(status, "⚪")
    pills = [pill(status.replace("_", " "), status, status_icon)]

    priority = incident.get("priority")
    if priority:
        icon = incident.get("priority_emoji") or PRIORITY_EMOJI.get(priority, "⚪")
        pills.append(pill(priority, priority, icon))
    else:
        pills.append(pill("priority pending", "muted", "⏳"))

    category = incident.get("category")
    if category:
        pills.append(pill(category, "category", incident.get("category_emoji") or "🏷️"))
    else:
        pills.append(pill("category pending", "muted", "⏳"))

    return f'<div class="pill-row">{"".join(pills)}</div>'


def empty_state(emoji: str, title: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="empty-state"><span class="emoji">{emoji}</span>'
        f"<strong>{title}</strong>{f'<br>{hint}' if hint else ''}</div>",
        unsafe_allow_html=True,
    )


def pending_note(label: str) -> None:
    st.markdown(f'<div class="card-pending">{label} — {PENDING_TEXT}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# dialogs
# --------------------------------------------------------------------------
@st.dialog("➕ New Incident", width="large")
def create_dialog() -> None:
    st.caption("Describe the problem. AI triage runs automatically once it's logged.")

    with st.form("create_incident_form", clear_on_submit=False, border=False):
        title = st.text_input(
            "Title",
            placeholder="VPN drops every 15 minutes",
            help="A one-line summary of the problem.",
        )
        description = st.text_area(
            "Description",
            placeholder="What is happening, who is affected, and when it started.",
            height=160,
            help="More detail produces a better AI summary and KB match.",
        )
        col_submit, col_cancel = st.columns([1, 1])
        with col_submit:
            submitted = st.form_submit_button("Create incident", type="primary", width="stretch")
        with col_cancel:
            cancelled = st.form_submit_button("Cancel", width="stretch")

    if cancelled:
        close_dialog()

    if submitted:
        if not title.strip() or not description.strip():
            st.error("Title and description are both required.")
            return

        with st.spinner("🤖 AI is analyzing..."):
            created, error = api_call(
                "POST",
                "/incidents",
                json={"title": title.strip(), "description": description.strip()},
                timeout=WRITE_TIMEOUT,
            )

        if error:
            st.error(error)
            return

        queue_toast(f"Created incident #{created['id']} — {created['title']}", "🎉")
        if not created.get("ai_summary"):
            queue_toast("AI analysis did not run; triage fields are pending.", "⏳")
        st.session_state["dialog"] = None
        st.session_state["dialog_incident"] = None
        st.rerun()


@st.dialog("🎫 Incident detail", width="large")
def detail_dialog(incident_id: int) -> None:
    detail, error = api_call("GET", f"/incidents/{incident_id}", timeout=READ_TIMEOUT)
    if error:
        st.error(error)
        if st.button("Close"):
            close_dialog()
        return

    st.markdown(
        f'<div class="card-title"><span class="card-id">#{detail["id"]}</span> '
        f'{detail["title"]}</div>{badge_row(detail)}',
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown('<div class="section-label">Description</div>', unsafe_allow_html=True)
    st.write(detail.get("description") or "_No description recorded._")

    st.markdown('<div class="section-label">🤖 AI summary</div>', unsafe_allow_html=True)
    if detail.get("ai_summary"):
        st.info(detail["ai_summary"])
    else:
        pending_note("🤖 Summary")

    st.markdown('<div class="section-label">📚 Knowledge base matches</div>', unsafe_allow_html=True)
    kb_links = detail.get("kb_links") or []
    if not kb_links:
        st.markdown(
            '<div class="kb-rationale">📭 No knowledge base article matched this incident.</div>',
            unsafe_allow_html=True,
        )
    else:
        for link in kb_links:
            article = link.get("kb_article") or {}
            score = link.get("relevance_score")
            score_text = f"{score:.0%}" if isinstance(score, (int, float)) else "n/a"
            st.markdown(
                f'<div class="kb-card"><span class="kb-score">{score_text}</span>'
                f'<div class="kb-title">📄 {article.get("title", "Unknown article")}</div>'
                f'<div class="kb-rationale">{link.get("rationale") or "No rationale recorded."}</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            with st.expander(f"Read “{article.get('title', 'article')}”"):
                st.write(article.get("content") or "_empty_")

    st.markdown('<div class="section-label">✨ Suggested resolution</div>', unsafe_allow_html=True)
    is_resolved = detail.get("status") == "resolved"
    if is_resolved:
        st.success(f"Resolved at {detail.get('resolved_at')}")
        st.write(detail.get("resolution_notes") or "_No notes recorded._")
    elif detail.get("ai_suggested_resolution"):
        st.markdown(detail["ai_suggested_resolution"])
    else:
        pending_note("✨ Suggested resolution")

    st.divider()
    col_resolve, col_reanalyze, col_close = st.columns([1, 1, 1])
    with col_resolve:
        if st.button(
            "✅ Resolve",
            type="primary",
            width="stretch",
            disabled=is_resolved,
            help="Already resolved" if is_resolved else "Review the draft, then confirm",
            key="detail_resolve",
        ):
            # Inside a dialog, so the main page has already rendered: rerun is safe
            # here and is required to swap one dialog for another.
            open_dialog("resolve", incident_id, rerun=True)
    with col_reanalyze:
        if st.button(
            "🔄 Re-analyze",
            width="stretch",
            help="Run AI triage, KB matching and drafting again",
            key="detail_reanalyze",
        ):
            with st.spinner("🤖 AI is analyzing..."):
                _, reanalyze_error = api_call(
                    "POST", f"/incidents/{incident_id}/reanalyze", timeout=WRITE_TIMEOUT
                )
            if reanalyze_error:
                queue_toast(reanalyze_error, "⚠️")
            else:
                queue_toast(f"Incident #{incident_id} re-analyzed", "🤖")
            st.rerun()
    with col_close:
        if st.button("Close", width="stretch", key="detail_close"):
            close_dialog()


@st.dialog("✅ Resolve incident")
def resolve_dialog(incident_id: int) -> None:
    detail, error = api_call("GET", f"/incidents/{incident_id}", timeout=READ_TIMEOUT)
    if error:
        st.error(error)
        if st.button("Close"):
            close_dialog()
        return

    if detail.get("status") == "resolved":
        st.info(f"Incident #{incident_id} is already resolved.")
        if st.button("Close", width="stretch"):
            close_dialog()
        return

    st.markdown(f"**#{detail['id']} — {detail['title']}**")
    st.caption("Review and edit the drafted resolution before confirming. This cannot be undone.")

    if not detail.get("ai_suggested_resolution"):
        st.warning(f"No AI draft available — {PENDING_TEXT}. Write the resolution yourself.")

    notes = st.text_area(
        "Resolution notes",
        value=detail.get("ai_suggested_resolution") or "",
        height=240,
        key=f"resolve_notes_{incident_id}",
        help="Saved to the incident as resolution_notes.",
    )

    col_confirm, col_cancel = st.columns([1, 1])
    with col_confirm:
        confirm = st.button(
            "✅ Confirm resolve",
            type="primary",
            width="stretch",
            disabled=not notes.strip(),
            help="Resolution notes cannot be empty" if not notes.strip() else "Mark this incident resolved",
        )
    with col_cancel:
        if st.button("Cancel", width="stretch"):
            close_dialog()

    if confirm:
        with st.spinner("Saving resolution..."):
            resolved, resolve_error = api_call(
                "POST",
                f"/incidents/{incident_id}/resolve",
                json={"resolution_notes": notes.strip()},
                timeout=WRITE_TIMEOUT,
            )
        if resolve_error:
            st.error(resolve_error)
            return
        queue_toast(f"Incident #{resolved['id']} marked resolved", "🎉")
        st.session_state["dialog"] = None
        st.session_state["dialog_incident"] = None
        st.rerun()


# --------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <h1>🎯 Support Incident Triage Assistant</h1>
        <p>AI-assisted triage — automatic summaries, priority, and knowledge base matches.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

flush_toasts()

# --------------------------------------------------------------------------
# toolbar
# --------------------------------------------------------------------------
col_new, col_status, col_priority, col_refresh = st.columns([1.1, 1, 1, 0.7], vertical_alignment="bottom")

with col_new:
    if st.button("➕ New Incident", type="primary", width="stretch", help="Log a new incident"):
        open_dialog("create")
with col_status:
    status_filter = st.selectbox("Status", STATUS_OPTIONS, key="status_filter")
with col_priority:
    priority_filter = st.selectbox("Priority", PRIORITY_OPTIONS, key="priority_filter")
with col_refresh:
    if st.button("🔄 Refresh", width="stretch", help="Reload from the API"):
        st.rerun()

st.divider()

incidents, list_error = fetch_incidents(status_filter, priority_filter)

if list_error:
    st.error(f"⚠️ {list_error}")
    empty_state("🔌", "Backend unreachable", "Start it with: uvicorn app.main:app --reload")
    st.stop()

# --------------------------------------------------------------------------
# KPI tiles — counts reflect the unfiltered board, so filtering never hides scale
# --------------------------------------------------------------------------
all_incidents, _ = fetch_incidents("All", "All")
board = all_incidents if all_incidents is not None else incidents


def count_status(name: str) -> int:
    return sum(1 for i in board if i.get("status") == name)


kpis = [
    ("Total", len(board), ""),
    ("🔵 Open", count_status("open"), ""),
    ("🟡 In progress", count_status("in_progress"), ""),
    ("🟢 Resolved", count_status("resolved"), ""),
    ("⏳ Awaiting AI", sum(1 for i in board if not i.get("ai_summary")), ""),
]
for column, (label, value, _) in zip(st.columns(len(kpis)), kpis):
    with column:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>',
            unsafe_allow_html=True,
        )

st.write("")

# --------------------------------------------------------------------------
# incident list
# --------------------------------------------------------------------------
filtered = status_filter != "All" or priority_filter != "All"
st.markdown(
    f'<div class="section-label">Incidents — {len(incidents)} '
    f'{"match" if filtered else "total"}</div>',
    unsafe_allow_html=True,
)

if not incidents:
    empty_state(
        "📭",
        "No incidents found",
        "Nothing matches these filters. Try resetting them, or log a new incident.",
    )
else:
    for incident in incidents:
        with st.container(border=True):
            text_col, action_col = st.columns([5, 1.15], vertical_alignment="center")

            with text_col:
                st.markdown(
                    f'<div class="card-title"><span class="card-id">#{incident["id"]}</span> '
                    f'{incident["title"]}</div>{badge_row(incident)}',
                    unsafe_allow_html=True,
                )
                if incident.get("ai_summary"):
                    st.markdown(
                        f'<div class="card-summary">🤖 {incident["ai_summary"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="card-pending">🤖 {PENDING_TEXT}</div>',
                        unsafe_allow_html=True,
                    )

            with action_col:
                if st.button(
                    "🔍 Details",
                    key=f"details_{incident['id']}",
                    width="stretch",
                    help="Open the full incident",
                ):
                    open_dialog("detail", incident["id"])

                already_resolved = incident.get("status") == "resolved"
                if st.button(
                    "✅ Resolve",
                    key=f"resolve_{incident['id']}",
                    type="primary",
                    width="stretch",
                    disabled=already_resolved,
                    help="Already resolved" if already_resolved else "Review the draft, then confirm",
                ):
                    open_dialog("resolve", incident["id"])

# --------------------------------------------------------------------------
# dialog dispatch — one dialog at a time; state survives filter/list rendering
# --------------------------------------------------------------------------
active_dialog = st.session_state.get("dialog")
active_incident = st.session_state.get("dialog_incident")

if active_dialog == "create":
    create_dialog()
elif active_dialog == "detail" and active_incident is not None:
    detail_dialog(active_incident)
elif active_dialog == "resolve" and active_incident is not None:
    resolve_dialog(active_incident)

# --------------------------------------------------------------------------
# footer — backend status
# --------------------------------------------------------------------------
st.divider()
health, health_error = api_call("GET", "/health", timeout=5)
if health_error:
    st.caption("🔌 Backend unreachable")
else:
    key_note = "🔑 Groq key loaded" if health.get("groq_api_key_loaded") else "⚠️ GROQ_API_KEY missing"
    st.caption(f"{health.get('status_emoji', '')} Backend {health.get('status')} · {key_note} · {API_BASE}")
