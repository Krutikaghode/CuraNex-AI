from fastapi import FastAPI

from app.api.routes.patients import router as patients_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.reports import router as reports_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Educational healthcare decision-support prototype. Synthetic data only.",
    version="0.4.0",
)
app.include_router(system_router)
app.include_router(patients_router)
app.include_router(predictions_router)
app.include_router(reports_router)
