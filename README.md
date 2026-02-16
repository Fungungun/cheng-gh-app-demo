# GitHub OAuth Demo (React + FastAPI)

This demo shows a GitHub OAuth App login flow with a React (Vite) frontend and a FastAPI backend.

## Backend setup

1. Create a GitHub OAuth App and set the callback URL to `http://localhost:8000/api/github/callback`.
2. Copy [backend/.env.example](backend/.env.example) to `backend/.env` and fill in your values.
3. Install deps and run the server:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and click "Connect GitHub".

## Notes

- Session storage is in-memory for demo only.
- The existing `backend.py` remains untouched and is not used by this demo.
