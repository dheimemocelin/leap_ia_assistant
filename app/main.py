from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.commercial_boundary import CommercialOutputBoundary
from app.api.routes import router

app = FastAPI(title="LEAP AI Assistant", version="0.1.0")
app.include_router(router)
app.include_router(chat_router)

app.add_middleware(CommercialOutputBoundary)
