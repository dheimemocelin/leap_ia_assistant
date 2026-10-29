"""Password-gated temporary web chat. Browser never receives backend/provider keys."""

import hashlib
import secrets
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, SecretStr

from app.api.chat import ChatInput, build_agent
from app.config import settings
from app.domain.response import AssistantResponse

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1] / "web"
COOKIE = "leap_web_session"


class Login(BaseModel):
    password: SecretStr
    reviewed_catalog: bool = True


class BrowserSessions:
    def __init__(self):
        self.sessions = {}
        self.attempts = deque(maxlen=20)

    def login(self, password, reviewed):
        now = time.monotonic()
        while self.attempts and self.attempts[0] < now - 60:
            self.attempts.popleft()
        if len(self.attempts) >= 20:
            raise HTTPException(429, "Aguarde um minuto antes de tentar novamente.")
        self.attempts.append(now)
        configured = settings.web_chat_password.get_secret_value()
        if len(configured) < 12:
            raise HTTPException(503, "Acesso web ainda não configurado.")
        if not secrets.compare_digest(password.encode(), configured.encode()):
            raise HTTPException(401, "Senha incorreta.")
        self.sessions = {k: v for k, v in self.sessions.items() if v["expires"] > now}
        if len(self.sessions) >= 32:
            raise HTTPException(429, "Limite de sessões do teste atingido.")
        token = secrets.token_urlsafe(32)
        self.sessions[hashlib.sha256(token.encode()).hexdigest()] = {
            "conversation_id": secrets.token_hex(16),
            "reviewed": reviewed,
            "expires": now + 7200,
            "turns": 0,
        }
        return token

    def get(self, request):
        token = request.cookies.get(COOKIE, "")
        session = self.sessions.get(hashlib.sha256(token.encode()).hexdigest())
        if session is None or session["expires"] <= time.monotonic():
            raise HTTPException(401, "Entre novamente para continuar.")
        return session


def store(request):
    if not hasattr(request.app.state, "browser_sessions"):
        request.app.state.browser_sessions = BrowserSessions()
    return request.app.state.browser_sessions


def same_origin(request):
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if request.headers.get("origin") != expected:
        raise HTTPException(403, "Origem não autorizada.")


@router.get("/", include_in_schema=False)
async def page():
    return FileResponse(
        ROOT / "index.html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/web/chat.js", include_in_schema=False)
async def javascript():
    return FileResponse(ROOT / "chat.js", media_type="text/javascript")


@router.get("/web/chat.css", include_in_schema=False)
async def stylesheet():
    return FileResponse(ROOT / "chat.css", media_type="text/css")


@router.post("/web/login", include_in_schema=False)
async def login(body: Login, request: Request, response: Response):
    same_origin(request)
    if len(body.password.get_secret_value()) > 200:
        raise HTTPException(401, "Senha incorreta.")
    token = store(request).login(body.password.get_secret_value(), body.reviewed_catalog)
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        max_age=7200,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "reviewed_catalog": body.reviewed_catalog}


@router.get("/web/session", include_in_schema=False)
async def session_status(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        session = store(request).get(request)
        return {"authenticated": True, "reviewed_catalog": session["reviewed"]}
    except HTTPException:
        return {"authenticated": False}


@router.post("/web/logout", include_in_schema=False)
async def logout(request: Request, response: Response):
    same_origin(request)
    token = request.cookies.get(COOKIE, "")
    store(request).sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
    response.delete_cookie(COOKIE, path="/")
    return {"authenticated": False}


@router.post("/web/reset", include_in_schema=False)
async def reset(request: Request):
    same_origin(request)
    session = store(request).get(request)
    session["conversation_id"] = secrets.token_hex(16)
    return {"reset": True}


@router.post("/v1/web/messages", response_model=AssistantResponse, include_in_schema=False)
async def message(body: ChatInput, request: Request, response: Response):
    same_origin(request)
    session = store(request).get(request)
    if session["turns"] >= 30:
        raise HTTPException(429, "Limite de 30 mensagens por sessão atingido.")
    session["turns"] += 1
    key = "web_agent_reviewed" if session["reviewed"] else "web_agent_pending"
    if not hasattr(request.app.state, key):
        setattr(request.app.state, key, build_agent(reviewed_catalog=session["reviewed"]))
    agent = getattr(request.app.state, key)
    response.headers["Cache-Control"] = "no-store"
    return await agent.turn(session["conversation_id"], body.text, owner="browser")
