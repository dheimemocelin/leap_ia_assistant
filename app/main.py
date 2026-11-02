import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import build_agent
from app.api.chat import router as chat_router
from app.api.commercial_boundary import CommercialOutputBoundary
from app.api.evolution import configuration_ready
from app.api.evolution import router as evolution_router
from app.api.routes import router
from app.api.web_chat import router as web_router
from app.channels.evolution import EvolutionAdapter
from app.channels.evolution_worker import EvolutionWorker
from app.config import settings


@asynccontextmanager
async def lifespan(app):
    task = worker = None
    if settings.evolution_enabled:
        if not configuration_ready():
            raise RuntimeError("WhatsApp pilot configuration incomplete")
        from app.channels.evolution_store import EvolutionStore

        storage = EvolutionStore(settings.pilot_db_path)
        app.state.evolution_store = storage
        agent = build_agent(reviewed_catalog=True, test_media=True)
        adapter = EvolutionAdapter(
            settings.evolution_url,
            settings.evolution_api_key.get_secret_value(),
            settings.evolution_instance,
        )
        worker = EvolutionWorker(
            storage, agent, adapter, send_enabled=settings.evolution_send_enabled
        )
        app.state.evolution_worker = worker
        task = asyncio.create_task(worker.run())
    try:
        yield
    finally:
        if worker:
            worker.stop.set()
            try:
                await asyncio.wait_for(task, timeout=20)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title="LEAP AI Assistant", version="0.1.0", lifespan=lifespan)
app.include_router(evolution_router)
app.include_router(router)
app.include_router(chat_router)
app.include_router(web_router)

app.add_middleware(CommercialOutputBoundary)
