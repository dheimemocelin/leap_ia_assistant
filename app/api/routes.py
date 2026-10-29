from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


@router.get("/health/live", response_model=HealthResponse, tags=["health"])
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse, tags=["health"])
async def ready() -> HealthResponse:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="required dependency unavailable") from exc
    finally:
        await redis.aclose()
        await engine.dispose()
    return HealthResponse(status="ok")
