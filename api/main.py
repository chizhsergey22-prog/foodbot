from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import menu, cart, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Food Bot API", lifespan=lifespan)

ALLOWED_ORIGINS = [
    "https://web.telegram.org",
    "https://k.web.telegram.org",
    "https://z.web.telegram.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(menu.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
