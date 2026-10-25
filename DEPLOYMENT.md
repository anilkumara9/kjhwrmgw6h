# Deployment

Two supported shapes. Both serve the same app; pick one.

## Option 1 — Vercel (frontend + backend in this one repo)

- `frontend/` is built as a static site (`@vercel/static-build`, `dist/`).
- `api/index.py` re-exports the FastAPI app as a Vercel Python serverless function.
- `vercel.json` routes `/api/*` to the function and everything else to the static frontend,
  and sets `VITE_API_BASE` to empty so the frontend calls the API on the same origin.
- **Why serverless works here:** the function does not need live Elexon access.
  `vercel.json` includes `backend/data/jan2026_snapshot.json` in the function bundle
  (`includeFiles`), and the backend falls back to that bundled snapshot automatically.
  Root `requirements.txt` provides the function's Python dependencies (fastapi, httpx).

Steps:

1. Push this repo to GitHub (use an anonymous name).
2. In Vercel: **New Project → Import** the repo. Framework preset: **Other** (the repo's
   `vercel.json` drives the build). No environment variables are required.
3. Deploy. Open the generated URL and check `/api/health` returns `{"status":"ok"}`.
4. Put the live URL in `README.md` ("Live app") and verify it in an incognito window.

Honest limitations of the serverless option: cold starts add latency to the first API call;
the function serves the bundled January 2026 snapshot (by design — the challenge scope is a
fixed month), so it does not refresh live data.

## Option 2 — Container host (Docker)

```bash
docker compose up --build
# Frontend http://localhost:8080 · Backend http://localhost:8000
```

Works on any host that runs Docker (a VM, Render/Fly.io/Railway-style container services,
Heroku with the container stack, etc.):

- Backend image: `backend/Dockerfile` (python:3.12-slim, uvicorn on port 8000, snapshot
  bundled in the image).
- Frontend image: `frontend/Dockerfile` (node build → nginx serving `dist/` on port 80).
  Build arg `VITE_API_BASE` points the browser at the backend's public URL
  (default `http://localhost:8000` for local compose).

For a split deployment (static frontend on Vercel + backend container elsewhere), build the
frontend with `VITE_API_BASE=https://<your-backend-host>` and set that same value in the
hosting platform's build settings.

## Heroku note

Heroku works via the container route: `heroku stack:set container` with the two Dockerfiles,
or run the backend as a single dyno (`uvicorn app.main:app --port $PORT` from `backend/`)
and host the static frontend on Vercel.
