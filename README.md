# Kshetra

Panchayat-level weather forecasts and agromet advisories, downscaled from IMD block forecasts (SIH 2026, PS 26074).

## Quick start

Backend (Python 3.11+):

    cd backend
    py -3.13 -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt
    copy .env.example .env
    .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app

Frontend (Node 18+):

    cd frontend
    npm install
    copy .env.example .env.local
    npm run dev

Open http://localhost:3000/styleguide and http://localhost:8000/health.

## Brand and theme
- Replace `frontend/public/brand/logo-light.png` and `logo-dark.png` with your logo files (same names).
- Change colours only in `frontend/src/styles/theme.css`.

## Database (Supabase) and demo seed

This project's Supabase database is already set up (keys in `backend/.env` and `frontend/.env.local`, which are
not committed). To set up a new one:

1. Create a Supabase project. Put `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` and
   `DATABASE_URL` (Connect > Session pooler URI) in `backend/.env`, and the URL + anon key in `frontend/.env.local`.
2. Generate the demo data (deterministic; also writes the offline Demo Mode JSON in `backend/data/demo/`):

       cd backend
       .venv/Scripts/python -m scripts.seed_demo

3. Load it: `.venv/Scripts/python -m scripts.seed_demo --apply` runs every file in `backend/supabase/migrations/`
   (0001-0005) and then `backend/supabase/seed.sql` on `DATABASE_URL`. Or paste them into the SQL editor in that order.
4. Publish a real forecast (also inserted into the database when Supabase is configured):

       .venv/Scripts/python -m pipeline.run_daily --replay 2025-09-13 --publish-demo
       .venv/Scripts/python -m pipeline.validate

5. In Supabase Auth settings turn **off** "Allow new users to sign up". Officers are added only by an admin (below).

Re-running the seed clears and reloads the demo tables and overwrites the validation files: run `pipeline.validate` again.
The seed adds a synthetic forecast run dated 20 Jul 2026; because it is newer, the app shows it instead of real runs.
On a live database remove it afterwards: `delete from forecast_runs where source = 'seed';` (then publish a real run).

## Data sources

| Data | Source | Status |
|---|---|---|
| Block forecast (5 days) | Open-Meteo, in IMD agromet format | Stand-in for IMD's block feed (labelled on every screen) |
| Village names + locations | OpenStreetMap (`backend/data/raw/osm_siddipet_villages.json`, ODbL) | Real; Telugu / Hindi transliterated |
| Block + panchayat boundaries | Drawn for the prototype (Voronoi around villages) | Approximate, not official |
| Rain observations | IMD 0.25° gridded rainfall (`imdlib`, `backend/data/raw/imd/`) + NOAA GSOD stations | Real, used only for validation |
| Terrain | Copernicus DEM via Open-Meteo | Real |

## Officer accounts

- Public sign-up is disabled; only an **admin** adds officers on the **Officers** page (menu visible to admins only).
- Invite = official email (`OFFICER_EMAIL_DOMAINS`, default `gov.in,nic.in,panchayatcast.in`) + name + blocks.
  The admin gets a one-time invite link (24 h) to send to the officer; the officer sets a password on `/set-password`.
  Supabase's default mailer only emails project team members, so connect SMTP (e.g. Brevo, Resend) for automatic emails.
- Officers only see farmer contacts in their assigned blocks. Test logins: `backend/.officer_credentials.txt` (not committed).

## Farmer contacts

- **Farmers** page: upload CSV / Excel (`name, mobile, panchayat, crop, language`; template on the page).
  Numbers are masked (98xxxxxx10) everywhere in the app; the `farmers` table has no public read access.
- Farmer page `/f/[id]`: "Get advice on SMS / WhatsApp" sign-up with explicit consent and a stop option.
- Sending is **simulated** (real bulk SMS in India needs DLT registration and a gateway); the recipient count is the
  panchayat's real contact list.

## API

- Docs: http://127.0.0.1:8000/docs (use 127.0.0.1 on Windows; `localhost` adds ~200 ms per call).
- Without Supabase keys the API serves the offline demo data from `backend/data/demo/`.
  Header `X-Demo-Mode: 1` forces demo data; `DEMO_MODE=true` in `.env` forces it for every request.
- Every `/api` response has `X-Data-Source: supabase | demo`; `X-Data-Stale: 1` means Supabase failed and
  cached demo data was served.
- Tests: `cd backend && .venv/Scripts/python -m pytest -q`

## Extreme-weather alerts (Phase 6b)

- IMD colour-coded warnings (Yellow / Orange / Red) per panchayat; siren only for Orange/Red with High or Medium confidence.
- Demo: officer bell (top bar) > **Simulate extreme event** creates a clearly labelled very heavy rain event
  (132 mm at Ahmadipur); **Reset to normal** removes it.
- Web Push for farmers needs VAPID keys: `cd backend; .venv\Scripts\python -m scripts.gen_vapid` (already done once).
- Push, notifications and offline mode need a **secure page**: `http://localhost` works on the laptop; on a phone use an
  `https://` address (e.g. the deployed app in Phase 9). For a quick phone test in Chrome for Android, open
  `chrome://flags/#unsafely-treat-insecure-origin-as-secure`, add `http://<laptop-ip>:3000`, and relaunch Chrome.
- CAP 1.2 export (NDMA SACHET format) per alert from the alert drawer; simulated alerts are `<status>Exercise</status>`.
