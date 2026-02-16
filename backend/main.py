import os
import secrets
import urllib.parse
from typing import Any, Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

load_dotenv()

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/github/callback")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

SESSION_COOKIE_NAME = "gh_demo_session"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

# In-memory stores for demo only.
SESSIONS: Dict[str, Dict[str, Any]] = {}
OAUTH_STATES = set()


def require_config() -> None:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Missing GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET",
        )


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/github/login")
def github_login() -> RedirectResponse:
    require_config()
    state = secrets.token_urlsafe(16)
    OAUTH_STATES.add(state)

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "read:user user:email repo",
        "state": state,
    }

    query = urllib.parse.urlencode(params)
    url = f"https://github.com/login/oauth/authorize?{query}"
    return RedirectResponse(url=url, status_code=302)


@app.get("/api/github/callback")
def github_callback(code: str | None = None, state: str | None = None) -> RedirectResponse:
    require_config()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if state not in OAUTH_STATES:
        raise HTTPException(status_code=400, detail="Invalid state")

    OAUTH_STATES.discard(state)

    token = exchange_code_for_token(code)
    user = fetch_user(token)
    emails = fetch_emails(token)

    primary_email = None
    for entry in emails:
        if entry.get("primary"):
            primary_email = entry.get("email")
            break

    session_id = secrets.token_urlsafe(24)
    SESSIONS[session_id] = {
        "login": user.get("login"),
        "id": user.get("id"),
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
        "email": primary_email,
        "token": token,
    }

    response = RedirectResponse(url=FRONTEND_ORIGIN, status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response


@app.get("/api/github/me")
def github_me(request: Request) -> JSONResponse:
    session = get_session(request)
    return JSONResponse(public_session(session))


@app.get("/api/github/repos")
def github_repos(request: Request) -> JSONResponse:
    session = get_session(request)
    token = session.get("token")
    print(f"Fetching repos for user {session.get('login')} with token {token}")
    if not token:
        raise HTTPException(status_code=401, detail="Missing delegated token")

    repos = fetch_repos(token)
    return JSONResponse(repos)


@app.post("/api/logout")
def logout(request: Request) -> JSONResponse:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        SESSIONS.pop(session_id, None)
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


def get_session(request: Request) -> Dict[str, Any]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id or session_id not in SESSIONS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return SESSIONS[session_id]


def public_session(session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "login": session.get("login"),
        "id": session.get("id"),
        "name": session.get("name"),
        "avatar_url": session.get("avatar_url"),
        "email": session.get("email"),
    }


def exchange_code_for_token(code: str) -> str:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Accept": "application/json"}

    with httpx.Client(timeout=15) as client:
        response = client.post("https://github.com/login/oauth/access_token", data=data, headers=headers)
        response.raise_for_status()
        payload = response.json()

    access_token = payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to obtain access token")
    return access_token


def fetch_user(token: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=15) as client:
        response = client.get("https://api.github.com/user", headers=headers)
        response.raise_for_status()
        return response.json()


def fetch_emails(token: str) -> list[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=15) as client:
        response = client.get("https://api.github.com/user/emails", headers=headers)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()


def fetch_repos(token: str) -> list[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    params = {
        "per_page": 100,
        "sort": "updated",
    }
    with httpx.Client(timeout=15) as client:
        response = client.get("https://api.github.com/user/repos", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    return [
        {
            "id": repo.get("id"),
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "html_url": repo.get("html_url"),
            "private": repo.get("private"),
            "updated_at": repo.get("updated_at"),
        }
        for repo in data
    ]
