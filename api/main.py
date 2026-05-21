from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import menu, cart, orders
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import redis.asyncio as aioredis
    import aiohttp

    logger.info("API starting up")

    # FIX: Create a single Redis connection pool for the entire app lifetime
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis connection pool created")

    # FIX: Create a single aiohttp session for outgoing HTTP requests (Telegram API)
    app.state.http_session = aiohttp.ClientSession()
    logger.info("HTTP session created")

    yield

    # Cleanup on shutdown
    await app.state.http_session.close()
    logger.info("HTTP session closed")
    await app.state.redis.aclose()
    logger.info("Redis connection pool closed")
    logger.info("API shutting down")


app = FastAPI(title="Food Bot API", lifespan=lifespan)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(menu.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
