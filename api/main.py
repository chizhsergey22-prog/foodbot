from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import menu, cart, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Food Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(menu.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
