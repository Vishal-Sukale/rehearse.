# Rehearse: AI mock technical interviewer

React + FastAPI + LangGraph + SQLite. Sign in, pick a track or upload your resume, and an AI interviewer asks one
question at a time. Answers can be typed or spoken. You get a scorecard, answer review and a progress dashboard.
Installable on phones and desktops.

```
ai-interviewer/
├── backend/    FastAPI (api.py, auth.py, db.py) + interviewer/ (LangGraph, prompts, schemas, stats, resume)
├── frontend/   Vite + React (installable PWA)
├── Dockerfile, docker-compose.yml, .dockerignore
```

## Develop
```bash
# terminal 1
cd backend && python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env      # then edit: GROQ_API_KEY and JWT_SECRET  (macOS/Linux: cp)
uvicorn api:app --reload --port 8000

# terminal 2
cd frontend && npm install && npm run dev                         # http://localhost:5173
```

## Run as one app (what you'd deploy)
```bash
cd frontend && npm run build
cd ../backend && uvicorn api:app --port 8000                      # http://localhost:8000
```
The backend serves the built frontend, so the same address works on desktop and phone.

## Try it on your phone
- **Same Wi-Fi, quick look:** run `npm run dev -- --host` and open the "Network" address it prints on your phone.
  Over plain `http://` on a LAN address, browsers block the microphone and app install. Typing works.
- **Full test with HTTPS (microphone and install):** build the frontend, run the backend on port 8000, then expose it
  with a tunnel such as `cloudflared tunnel --url http://localhost:8000` and open the `https://` link on your phone.

## Docker
```bash
# backend/.env needs GROQ_API_KEY and a JWT_SECRET of 32+ characters
docker compose up --build        # http://localhost:8000
```
Data lives in the `rehearse-data` volume.

## Deploy checklist
- Set `APP_ENV=production`, `JWT_SECRET` (32+ chars), `GROQ_API_KEY`, and `TRUST_PROXY=1` behind a hosting platform.
- Serve over HTTPS (needed for the microphone and install).
- Mount persistent storage at `/data`, because SQLite lives there.
- Run **one** instance and **one** worker. Live interviews and rate limits are held in memory.

## Settings
See `backend/.env.example` for every setting (model, answer checking, rate limits, production flags).

## Tests
```bash
cd backend && pytest
```

## Privacy
We store your account, your scorecards and the text of your answers. Resume files are never stored; their text is sent
to the AI model to write questions. Users can download all their data or delete their account from the Account dialog.

## Known limits
- A live interview is lost if the server restarts (finished ones are saved).
- SQLite and in-memory limits suit a single server. For several servers, move to Postgres and Redis.
- No password reset by email yet.