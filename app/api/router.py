from fastapi import APIRouter

from app.api.endpoints.aircraft import router as aircraft_router
from app.api.endpoints.airports import router as airports_router
from app.api.endpoints.recommendations import router as recommendations_router
from app.api.endpoints.routes import router as routes_router
from app.api.endpoints.schedules import router as schedules_router
from app.api.endpoints.ml import router as ml_router

from app.core.config import settings

api_router = APIRouter(prefix=settings.API_PREFIX)

api_router.include_router(aircraft_router)
api_router.include_router(airports_router)
api_router.include_router(routes_router)
api_router.include_router(recommendations_router)
api_router.include_router(schedules_router)
api_router.include_router(ml_router)

@api_router.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV
    }
