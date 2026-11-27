import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.deps import get_current_user
from app.api.routes.assistant import router as assistant_router
from app.api.routes.auth import router as auth_router
from app.api.routes.patients import router as patients_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.reports import router as reports_router
from app.api.routes.system import router as system_router
from app.api.routes.vitals import router as vitals_router
from app.core.config import get_settings
from app.core.security import check_secret_is_safe
from app.db.session import SessionLocal
from app.services import users

logger = logging.getLogger("curanex")
settings = get_settings()


def bootstrap_admin() -> None:
    """Create the first admin from CURANEX_ADMIN_EMAIL/PASSWORD if there are no users yet."""
    if not (settings.admin_email and settings.admin_password):
        return
    with SessionLocal() as db:
        if users.count_users(db) == 0:
            users.create_user(
                db,
                email=settings.admin_email,
                full_name="Administrator",
                password=settings.admin_password,
                role="admin",
            )
            logger.warning("Created initial admin %s", settings.admin_email)


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_secret_is_safe()
    bootstrap_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Educational healthcare decision-support prototype. Synthetic data only.",
    version="0.7.0",
    lifespan=lifespan,
)

# Public: health check and sign-in. Everything else requires a valid bearer token.
app.include_router(system_router)
app.include_router(auth_router)
protected = [Depends(get_current_user)]
for router in (
    patients_router,
    predictions_router,
    reports_router,
    assistant_router,
    vitals_router,
):
    app.include_router(router, dependencies=protected)
