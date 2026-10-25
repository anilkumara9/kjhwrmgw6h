# Submission Checklist

## 1. Code repository (public, anonymous name)

- [ ] Create a **public** GitHub repo with an anonymous, non-identifying name —
  suggested: `kjhwr-7f3a-wind` (any random string works; do **not** use your name,
  the client's name, or "REint" in the repo name).
- [ ] Push this project to it. Confirm the bundled snapshot
  (`backend/data/jan2026_snapshot.json`) is included and that `.venv/`, `node_modules/`,
  `frontend/dist/` and `backend/data/cache/` are not committed (see `.gitignore`).
- [ ] Confirm the README renders on GitHub and its "Live app" link is filled in.

## 2. Deployment

- [ ] Deploy (see `DEPLOYMENT.md`): frontend on Vercel; backend as the Vercel serverless
  function from this repo, or a container host.
- [ ] Open the deployed URL and check: Overview loads with January numbers,
  `/api/health` returns OK, Day Explorer works for 2026-01-15.

## 3. Video (unlisted YouTube, ≤ 10 min total)

- [ ] Record using `VIDEO_SCRIPT.md` (Part 1 client pitch ≤ 5 min; Part 2 tech-lead ≤ 5 min).
  **Do not submit without the video — evaluation starts with it.**
- [ ] Upload to YouTube with visibility **Unlisted**.
- [ ] Copy the video URL.

## 4. Incognito verification (do this for EVERY link before submitting)

- [ ] Open a browser **incognito / private** window (not signed in to anything).
- [ ] Open the GitHub repo URL — fully readable without login.
- [ ] Open the deployed app URL — loads and shows data.
- [ ] Open the YouTube URL — plays without sign-in.
- [ ] Fix any link that asks for login or returns 404 before submitting.

## 5. Submit the form

- [ ] Fill out the submission form: **https://forms.cloud.microsoft/r/Ljmf1aWESK**
  with the repo URL, deployed app URL, and unlisted video URL from the incognito check.
- [ ] Keep a copy of the three URLs and the submission timestamp for your records.
