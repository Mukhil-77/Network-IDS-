# SOC Dashboard (Frontend)

React + TypeScript + Vite frontend for the AI-Powered Network Threat
Detection Platform. Consumes the FastAPI backend from Milestones 4–6.

## Quick start

```bash
npm install
cp .env.example .env   # point at your running backend if not localhost:8000
npm run dev
```

Requires the backend running (`uvicorn backend.main:app`) for real data —
without it, pages show their error/retry states, which is expected.

## Scripts

- `npm run dev` — local dev server
- `npm run build` — type-check + production build
- `npm test` — run the test suite (vitest)

See `docs/FRONTEND_ARCHITECTURE.md` for architecture, component hierarchy,
routing, API/WebSocket integration details, and screenshots.
