"""Password-gated temporary web chat. Browser never receives backend/provider keys."""

import hashlib
import secrets
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, SecretStr

from app.api.chat import ChatInput, build_agent
from app.config import settings
from app.domain.response import AssistantResponse

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1] / "web"
COOKIE = "leap_web_session"
MEDIA_ROOT = (Path(__file__).resolve().parents[2] / "assets/media").resolve()


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
        setattr(
            request.app.state,
            key,
            build_agent(reviewed_catalog=session["reviewed"], test_media=session["reviewed"]),
        )
    agent = getattr(request.app.state, key)
    response.headers["Cache-Control"] = "no-store"
    result = await agent.turn(session["conversation_id"], body.text, owner="browser")
    grants = session.setdefault("media_tokens", {})
    for media_id in result.media_ids:
        if media_id not in grants.values():
            grants[secrets.token_urlsafe(24)] = media_id
    return result


class MediaIds(BaseModel):
    media_ids: list[str] = Field(max_length=3)


def media_agent(request, session):
    key = "web_agent_reviewed" if session["reviewed"] else "web_agent_pending"
    agent = getattr(request.app.state, key, None)
    if agent is None:
        raise HTTPException(404, "Imagem indisponível.")
    return agent


@router.post("/web/media/resolve", include_in_schema=False)
async def resolve_media(body: MediaIds, request: Request, response: Response):
    same_origin(request)
    session = store(request).get(request)
    response.headers["Cache-Control"] = "no-store"
    tokens = {value: token for token, value in session.get("media_tokens", {}).items()}
    if any(media_id not in tokens for media_id in body.media_ids):
        raise HTTPException(403, "Imagem não autorizada nesta conversa.")
    return {
        "images": [
            {"id": media_id, "url": "/web/media/" + tokens[media_id]} for media_id in body.media_ids
        ]
    }


@router.get("/web/media/{token}", include_in_schema=False)
async def image(token: str, request: Request):
    session = store(request).get(request)
    media_id = session.get("media_tokens", {}).get(token)
    if not media_id:
        raise HTTPException(404, "Imagem indisponível.")
    agent = media_agent(request, session)
    record = next((m for m in agent.catalog.media() if m.id == media_id), None)
    if record is None:
        raise HTTPException(404, "Imagem indisponível.")
    from app.catalog.media_library import MediaSearchQuery

    eligible = agent.media.search(MediaSearchQuery(vehicle_id=record.vehicle_id, limit=100))
    if record.id not in {m.id for m in eligible}:
        raise HTTPException(404, "Imagem indisponível.")
    root = MEDIA_ROOT
    path = Path(record.asset_path or "")
    resolved = (
        path.resolve()
        if path.is_absolute()
        else (Path(__file__).resolve().parents[2] / path).resolve()
    )
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise HTTPException(404, "Imagem indisponível.")
    if resolved.stat().st_size > 10 * 1024 * 1024:
        raise HTTPException(413, "Imagem muito grande.")
    data = resolved.read_bytes()
    if not record.sha256 or hashlib.sha256(data).hexdigest() != record.sha256:
        raise HTTPException(404, "Imagem indisponível.")
    if (
        record.mime_type != "image/jpeg"
        or not data.startswith(bytes.fromhex("ffd8ff"))
        or not data.endswith(bytes.fromhex("ffd9"))
    ):
        raise HTTPException(415, "Formato de imagem inválido.")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="vehicle.jpeg"',
        },
    )
