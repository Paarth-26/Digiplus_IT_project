# Frontend — Support Incident Triage Assistant

React 19 + Vite 8 + Tailwind CSS 4 + React Router 7. Talks to the FastAPI backend
over HTTP only, so the two run and restart independently.

## Run it

Terminal 1 — backend (from the repo root):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Terminal 2 — frontend:

```powershell
cd frontend
npm install
npm run dev
```

The UI opens at <http://localhost:5173> and calls the API at <http://127.0.0.1:8000>.

## Pages

| Route                  | Page          | What it does                                              |
| ---------------------- | ------------- | --------------------------------------------------------- |
| `/`                    | Dashboard     | KPI tiles, priority distribution, recent activity          |
| `/incidents`           | All incidents | Every incident, with search / sort / priority filters      |
| `/incidents/ongoing`   | Ongoing       | `open` + `in_progress`                                     |
| `/incidents/completed` | Completed     | `resolved`                                                 |
| `/incidents/new`       | New incident  | Create form, with sample incidents and a "what happens next" panel |
| `/incidents/:id`       | Detail        | Full incident, KB matches, resolve / re-analyze / reopen   |

Nav counts, the dashboard tiles, and the ongoing/completed splits all read from one
shared fetch (`context/IncidentsContext.jsx`). The list endpoint filters by a single
status, but "ongoing" spans two — and every page needs whole-board counts — so the
board is fetched once and sliced in the client. Navigation is then instant and the
counts can't disagree with each other.

## Interaction

- **Search** across id, title, description, AI summary and category — press `/` to focus it
- **Sort** by newest, oldest, or highest priority (untriaged sorts last — unknown severity, not zero)
- **Priority filter chips**, multi-select, with a clear-filters escape hatch
- Skeleton loaders, empty states per page, toasts on every write, staggered card entrances
- All motion is dropped under `prefers-reduced-motion`

## Configuration

The API base URL is read from `VITE_API_BASE`, defaulting to `http://127.0.0.1:8000`.
To point elsewhere, copy `.env.example` to `.env` and edit it. Vite only exposes
variables prefixed with `VITE_` to browser code, and reads `.env` at startup —
restart the dev server after changing it.

## CORS

The backend enables `CORSMiddleware` with `allow_origins=["*"]` by default
(`app/main.py`), so no dev proxy is needed. Setting `CORS_ORIGINS` in the root `.env`
narrows that list — if you do, include `http://localhost:5173`.

## Structure

```
src/
├── main.jsx                       Router + provider mount
├── App.jsx                        Route table
├── index.css                      Design tokens (@theme) + component classes
├── api/client.js                  fetch wrapper; every call returns { data, error }
├── context/IncidentsContext.jsx   Shared board fetch, counts, toasts
├── utils/datetime.js              UTC-safe timestamp formatting
├── components/
│   ├── Layout.jsx                 Sidebar nav with live counts, mobile menu, health footer
│   ├── IncidentList.jsx           Search, sort, filter chips, results
│   ├── IncidentCard.jsx           One incident row; navigates to the detail route
│   ├── StatusBadge.jsx            open / in_progress / resolved
│   ├── PriorityBadge.jsx          low / medium / high / critical
│   ├── Pill.jsx                   Shared badge shape
│   ├── StatCard.jsx               KPI tile
│   ├── PriorityDistribution.jsx   Horizontal bar chart
│   └── states.jsx                 EmptyState / ErrorState / CardSkeleton / PageHeader
└── pages/
    ├── Dashboard.jsx
    ├── AllIncidents.jsx
    ├── Ongoing.jsx
    ├── Completed.jsx
    ├── CreateIncident.jsx
    ├── IncidentDetail.jsx
    └── NotFound.jsx
```

## Design system

Tokens live in one `@theme` block in `src/index.css` and nowhere else; Tailwind v4
generates utilities from them (`bg-canvas`, `rounded-card`, `shadow-card`, …).

| Token             | Value                        |
| ----------------- | ---------------------------- |
| `--color-canvas`  | `#f6f7fb` soft gray page     |
| `--color-card`    | `#ffffff` card surface       |
| `--color-accent`  | `#4f46e5` indigo             |
| `--color-ink`     | `#1f2937` primary text       |
| `--color-muted`   | `#6b7280` secondary text     |
| `--radius-card`   | `14px` (panels `16px`)       |
| `--shadow-card`   | 1px lift + wide soft ambient |

### Priority ramp

Priority is an **ordered severity scale**, so the distribution chart uses a
single-hue ordinal ramp (light = low → dark = critical) rather than four unrelated
hues: a ramp says "more severe" on its own, where categorical color would only say
"different".

| Tier     | Step      |
| -------- | --------- |
| low      | `#818cf8` |
| medium   | `#6366f1` |
| high     | `#4f46e5` |
| critical | `#3730a3` |

Validated against the white card surface: monotone lightness, every adjacent step
≥ 0.06 ΔL, light end at 2.98:1 contrast, hue spread 0°. The chart is one series, so
it carries no legend box — the heading names what is plotted and every bar is
directly labeled with its tier and count. Badge colors are always paired with a text
label, so status and priority never rely on hue alone.

## Build

```powershell
npm run build      # -> dist/
npm run preview    # serve the production build locally
```

Client-side routing needs a SPA fallback — every unknown path must serve
`index.html`. `npm run dev` and `npm run preview` do this already; a static host
needs it configured (Netlify `_redirects`, Vercel rewrites, or `try_files
$uri /index.html` on nginx), or deep links like `/incidents/ongoing` 404 on refresh.
