# FlightDeck · MSFS Recommendation Frontend

A Next.js 16 / React 19 / Tailwind CSS 4 user interface for the Python FastAPI recommendation engine built earlier in this conversation.

## Start

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Start your Python backend separately on `http://127.0.0.1:8000`. Open `http://localhost:3000`.

Adjust `FASTAPI_BASE_URL` in `.env.local` if necessary (restart Next.js after editing it).

## Features

- Route discovery with the parameters supported by `MainRecommendationRequest`.
- Aircraft category, departure/arrival ICAO, duration, airport mode, flyability cutoff, weather preferences.
- Advanced options for runway metadata, realism, live METAR, scenarios, gate selection, decision trace, and more.
- Recommendation cards with scores, aircraft details, departure gate **candidates**, evidence coverage, reasons/warnings, and raw response JSON.
- Decision trace, rejected examples, and request ID for correlating with backend logs.
- Direct aircraft/airport validation: `POST /api/v1/recommendations/validate` (use actual aircraft ID).
- Next.js server-side API proxy (no browser-side cross-origin access and no CORS configuration required).

## Endpoints

Next.js proxies POST `/api/recommendations/generate` → `${FASTAPI_BASE_URL}/api/v1/recommendations/generate` and `/api/recommendations/validate` similarly.

## Known constraints

- The Python backend schema may have changed from the upgrade package. Use FastAPI `/openapi.json` to reconcile any differences.
- Aircraft IDs are database primary keys, not ICAO designators. In particular, the sample validation ID **must be corrected** to your B777-300ER record.
- Gate assignments are suggestions only, derived from your local CSV inventory when provided.
- Scoring and validation are simulator heuristics, never real-world dispatch assessment.
- The UI intentionally does not invent results or silently substitute mock routes if the backend fails.
