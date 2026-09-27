# Kshetra

SIH 2026 prototype, PS ID 26074 (MoES - IMD): "Downscaling of weather forecast from Block level to Panchayat level".
Kshetra takes IMD's block-level 5-day agromet forecast, downscales it to every gram panchayat (GP) with a
hybrid statistical + ML engine, and turns it into crop advisories in Telugu / Hindi / English.
Specs live in `documents/` (01 PRD, 02 user flow, 03 MoSCoW, 04 architecture, 05 UI wireframes, 06 demo script,
Data Strategy). Read the relevant PDF before each phase.

## Personas
- **Lakshmi** - Agriculture Extension Officer / DAMU staff, covers 15-25 GPs, issues advisories twice weekly. Logs in.
- **Ramesh** - smallholder cotton/paddy farmer, Siddipet, basic Android phone, reads Telugu. No login (public link).

## Demo flow (must run in < 90 s, also offline in Demo Mode)
Pilot: Telangana > Siddipet > Gajwel block (id 1), 24 GPs, demo GP "Ahmadipur" (panchayat id 7).
1. S1 Region Selection / Home  2. S2 Block vs Panchayat split map (hero)  3. S3 Panchayat detail
4. S4 Crop advisory  5. S5 Share & farmer preview  6. S6 Validation & accuracy.  S7 = farmer mobile page `/f/[id]`.

## Stack and folders
- `frontend/` Next.js 14 App Router, TypeScript, Tailwind CSS 3, shadcn-style components (`src/components/ui`),
  lucide-react, react-leaflet 4, Recharts, next-intl, Supabase JS.
- `backend/` FastAPI + Pydantic v2 (Python 3.13 venv in `backend/.venv`). `app/` API, `pipeline/` ML,
  `supabase/migrations/` SQL, `data/demo/` committed Demo Mode JSON.
- Database: Supabase (Postgres + PostGIS), Supabase Auth for officers.

## Rules
- **Colours only via theme tokens.** `frontend/src/styles/theme.css` is the only place colours are defined
  (`:root` light, `[data-theme="dark"]` dark). Use Tailwind names (`bg-primary`, `text-muted`, `bg-rain-3`...).
  No hex codes in components.
- Dark mode: `data-theme` on `<html>`; Tailwind `dark:` variant targets it. Toggle = `components/theme/ThemeToggle`.
- Logo: `<Logo />` (`components/brand/Logo.tsx`) shows `public/brand/logo-light.png` in light theme and
  `logo-dark.png` in dark theme. Paths in `src/config/brand.ts`.
- Every UI string goes through i18n (en, te, hi) from Phase 3 on.
- Confidence is always colour + text label, never colour alone.
- Use IMD terminology: GKMS, DAMU, agromet advisory, IMD rainfall categories (0 / 2.5 / 15.6 / 64.5 / 115.6 mm),
  POD / FAR / CSI, mass consistency, perfect prognosis. We build on IMD's official forecast, never replace it.
- Never show a metric we cannot back with data. Label the demo feed honestly:
  "Source: Open-Meteo (IMD-format demo feed)".
- Explain every advisory ("because 72% chance of >10 mm in 48 h").

## Architecture notes
- The browser calls `/api/*` on the page's own address; `next.config.mjs` proxies it to FastAPI (`BACKEND_URL`).
  This lets phones on the same Wi-Fi use the app (no 127.0.0.1) and avoids CORS.
- Two root layouts: `app/(main)` (officer app, login, styleguide; next-intl cookie locale) and `app/(farmer)`
  (public `/f/[id]?lang=`, no web fonts, no intl client bundle, service worker `public/sw.js` for offline).
  Keep the farmer page under 200 KB (currently ~130 KB).
- Backend auto-reload is unreliable in this OneDrive folder: restart uvicorn after backend edits.
- Never run `next build` while `next dev` is running unless you set `NEXT_DIST_DIR=.next-prod`.

## Pipeline (Phase 7)
- `backend/pipeline/`: Open-Meteo feed -> 1 km grid (425 cells) -> lapse-rate + XGBoost -> panchayat values with
  mass consistency + ensemble confidence. See `backend/pipeline/README.md` (data used, honest limitations).
- `python -m pipeline.train` (once), `python -m pipeline.run_daily [--replay YYYY-MM-DD] [--publish-demo]`.
- Demo Mode serves `data/demo/forecast.json` (currently the replay of 13 Sep 2025 if published);
  `python -m scripts.seed_demo` restores the synthetic seed. Tests always use `data/seed/` (tests/conftest.py).

## Run
- Backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app` -> http://localhost:8000/docs
- Frontend: `cd frontend && npm run dev` -> http://localhost:3000 (style guide at /styleguide)
- Tests: `cd backend && .venv/Scripts/python -m pytest -q`; `cd frontend && npm run lint`
