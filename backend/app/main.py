import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import copilot, songs, studio
from .services.acestep import get_acestep
from .services.jobs import poll_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop = asyncio.Event()
    poller = asyncio.create_task(poll_loop(stop))
    yield
    stop.set()
    await poller


app = FastAPI(
    title="Crescendo API",
    description="AI music studio built on the ACE-Step 1.5 engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(songs.router)
app.include_router(studio.router)
app.include_router(copilot.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "engine_reachable": await get_acestep().health()}
