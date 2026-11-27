from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.database import initialize_database
from backend.routes.patients import router as patients_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="CuraNex AI",
    description="Educational healthcare decision-support prototype.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(patients_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
