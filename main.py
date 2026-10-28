import logging
import os
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

load_dotenv()

from database import engine  # noqa: E402
from routers.agents import router as agents_router  # noqa: E402
from routers.documents import router as documents_router  # noqa: E402
from routers.tenants import router as tenants_router  # noqa: E402
from routers.users import router as users_router  # noqa: E402
from routers.voice import router as voice_router  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("nexa.api")

APP_VERSION = "0.2.0"

app = FastAPI(
    title="NEXA",
    description=(
        "Multi-tenant SaaS platform for building, running, and voicing AI agents "
        "with tools, persistent memory, and retrieval-augmented knowledge."
    ),
    version=APP_VERSION,
)

origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    started_at = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


@app.get("/", tags=["Meta"])
def read_root():
    return {
        "service": "NEXA",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Meta"])
@app.get("/ready", tags=["Meta"])
def health():
    """Readiness probe: verifies the API can reach PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("health_check_failed error=%s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": "NEXA",
                "version": APP_VERSION,
                "database": "unavailable",
            },
        )

    return {
        "status": "ok",
        "service": "NEXA",
        "version": APP_VERSION,
        "database": "ok",
    }


app.include_router(agents_router)
app.include_router(tenants_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(voice_router)
