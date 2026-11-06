"""FastAPI application entry point for the internal AI service.

All API routers require the service-to-service token. Only ``/health`` remains
public so the Express gateway or an orchestrator can perform liveness checks.
"""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import prediction_routes, research_routes, stock_routes
from app.security import require_service_token

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ai_smp")

# Fail fast on invalid production configuration. Error messages never include
# secret values, only the names of missing or unsafe settings.
settings.validate()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every API route is mounted behind the internal service token. The legacy
# frontend keeps using the Express JWT flow; Express forwards the service
# token server-side.
service_auth = [Depends(require_service_token)]
app.include_router(stock_routes.router, dependencies=service_auth)
app.include_router(prediction_routes.router, dependencies=service_auth)
app.include_router(research_routes.router, dependencies=service_auth)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log details server-side and return a non-sensitive client response."""

    logger.exception(
        "Unhandled error for %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal server error",
            }
        },
    )


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
