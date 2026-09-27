# Kshetra demo runbook

Target: the 6-step flow in **under 90 seconds**, working even with Wi-Fi off.

## 30 minutes before judges

1. Start the backend: `cd backend; .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. Start the frontend as a **production build** (pages load in about 1 s instead of 5-30 s the first time in dev mode):
   `cd frontend; npm run build; npm start` (stop `npm run dev` first). Or `docker compose up --build` from the project root.
   Measured: all 9 demo pages load in about 9 s in total; the click path fits well under 90 s.
3. Open http://localhost:3000 → **Continue in Demo Mode**. Home should show **Gajwel · 24 GPs**.
   Demo Mode is the safe choice for judges: no internet needed. Real officer login needs internet (Supabase).
4. Click through every screen once (S1 → S6, Farmers, and `/f/7?lang=te`) so maps, fonts and charts are cached.
5. Choose the data story:
   - Real replay (13 Sep 2025, all 8 blocks, honest, softer contrast): already published.
   - Synthetic story (Ahmadipur 38 mm, dramatic): `cd backend; .venv\Scripts\python -m scripts.seed_demo`, then
     `.venv\Scripts\python -m pipeline.validate`, then restart the backend. (The seed overwrites the validation files.)
6. In the alert drawer turn on **Alert sounds** (needed once per browser session).
7. Press **Shift+D** for the demo guide + stopwatch. Phone: open the farmer page and keep it on screen.
8. Have the backup screen recording ready.

## The 90-second click path (keys 1-6 jump in Demo Mode)

| # | Screen | Do | Say (short) |
|---|---|---|---|
| 1 | Home | Open Block Dashboard | "Lakshmi, extension officer, Gajwel block. Farmers get a link, no login." |
| 2 | Split map | Rain → Tmax → Rain, move to Day 2 | "Left: IMD's one block value. Right: every panchayat, averaging back to it." |
| 3 | Panchayat | Tap the wettest GP | "Rain, probability, confidence, difference from block." |
| 4 | Advisory | Crop and stage are already filled in → Why? | "Crop and stage come from the sowing date. Every advice says why." |
| 5 | Share | Telugu → Send | "One tap, farmer's language, to the farmers on this panchayat's list." |
| 6 | Validation | Tmax → Rain | "Honest scores at stations never used in training, including IMD gridded rain." |
| + | Alerts | Bell → Simulate extreme event | "Orange alert: siren, farmer SOS, CAP for SACHET, and only what changed." |

## If judges ask for more (30 s each)

| Ask | Show |
|---|---|
| "Does the officer do this 24 times?" | **Advisories** → Generate drafts for all → Approve & send selected. |
| "Where do phone numbers come from?" | **Farmers** → Download template → Upload. Numbers are masked. Farmer page → "Get advice on SMS / WhatsApp" with consent. |
| "Who can log in?" | Sign in as admin → **Officers**: invite-only, official emails, public sign-up off. |
| "Do you replace IMD's bulletin?" | S2 → **Bulletin (PDF)**: IMD agromet format, built on IMD's block forecast. |
| "Other blocks?" | Block selector: all 8 Siddipet mandals, 290 panchayats. |
| "Is it accurate?" | S6: small, honest gains; IMD data shows 34-87 mm across neighbouring cells on 12 Sep 2025. |

## If something fails

| Problem | Fix |
|---|---|
| "API unreachable" | Backend is down: restart it (step 1). |
| Page blank / 500 after a build | Stop frontend, delete `frontend/.next`, then `npm run build; npm start` again. |
| Wi-Fi drops | Stay in Demo Mode: the cached forecast and maps work offline (map tiles already cached in step 4). |
| Real login fails | Use **Continue in Demo Mode** (no internet needed). |
| No siren | Click anywhere, then "Tap to enable alert sound" in the banner. |
| Anything else | Switch to the backup recording; continue the pitch. |

## Numbers you may quote (real, from `pipeline.validate` / `pipeline.train`)

- 10 check points never used in training (4 NOAA GSOD stations + 6 IMD 0.25° gridded rainfall cells near Gajwel),
  Jun-Sep 2024 + Jun-Aug 2025: temperature equal to the block value; rain CSI (≥2.5 mm) **+2.5%** (90% CI 0.7 to 4.7);
  rain ≥10 mm +2.7% (CI crosses 0); heavy rain ≥64.5 mm not better (only 22 events).
- Engine at 9 km (model-to-model): Tmax RMSE 1.57 → 0.52 °C; rain ≥10 mm CSI 0.44 → 0.60.
- IMD observed rain on 12 Sep 2025 around Gajwel: **34 to 87 mm** in neighbouring 25 km cells (why one block value is not enough).
- Pipeline: all 8 Siddipet blocks, 290 panchayats, about 6 seconds per run on a laptop; farmer page about 111 KB.

## What is real and what is not (say it before they ask)

- Real: Open-Meteo forecasts (stand-in for IMD's block feed), IMD gridded rainfall, NOAA stations, OpenStreetMap village names and locations.
- Approximate: block and panchayat boundaries (drawn for the prototype); Telugu / Hindi village names are transliterated.
- Simulated: SMS / WhatsApp delivery (needs DLT registration and a gateway); farmer counts where no contacts are uploaded.
