import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.seed import seed_default_data
from app.db.session import get_db_session
from app.services.scheduler import LocalScheduler


def _request_id_from(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_db_session() as session:
        seed_default_data(session)
    scheduler = LocalScheduler(get_settings())
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    await scheduler.stop()


def create_app() -> FastAPI:
    configure_logging()
    logger = logging.getLogger("nanobot.http")
    app = FastAPI(
        title="Nanobot Agent Backend",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        started_at = perf_counter()
        response = await call_next(request)
        duration_ms = int((perf_counter() - started_at) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request.completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        request_id = _request_id_from(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.warning(
            "request.validation_failed request_id=%s path=%s errors=%s",
            request_id,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.exception(
            "request.unhandled request_id=%s path=%s error=%s",
            request_id,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error.", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    app.include_router(api_router)
    return app


app = create_app()
