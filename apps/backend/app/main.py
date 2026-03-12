import logging
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from json import dumps
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
from app.services.runtime_supervisor import RuntimeSupervisor


def _request_id_from(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else "unknown"


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for error in errors:
        normalized = dict(error)
        context = normalized.get("ctx")
        if isinstance(context, dict):
            normalized["ctx"] = {
                key: value
                if isinstance(value, (str, int, float, bool)) or value is None
                else str(value)
                for key, value in context.items()
            }
        sanitized.append(normalized)
    return sanitized


@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_db_session() as session:
        seed_default_data(session)
    runtime_supervisor = getattr(app.state, "runtime_supervisor", None)
    if runtime_supervisor is not None:
        await runtime_supervisor.start()
    yield
    if runtime_supervisor is not None:
        await runtime_supervisor.stop()


def create_app(
    *,
    shutdown_callback: Callable[[], None] | None = None,
    runtime_supervisor: RuntimeSupervisor | None = None,
) -> FastAPI:
    configure_logging()
    logger = logging.getLogger("nanobot.http")
    settings = get_settings()
    runtime_supervisor = runtime_supervisor or RuntimeSupervisor(settings)
    app = FastAPI(
        title="Nanobot Agent Backend",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.shutdown_callback = shutdown_callback
    app.state.runtime_supervisor = runtime_supervisor

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
        if settings.bootstrap_token and request.method != "OPTIONS":
            provided_token = request.headers.get("x-backend-bootstrap-token") or ""
            if not secrets.compare_digest(provided_token, settings.bootstrap_token):
                logger.warning(
                    (
                        "request.unauthorized request_id=%s method=%s path=%s "
                        "reason=invalid_bootstrap_token"
                    ),
                    request_id,
                    request.method,
                    request.url.path,
                )
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid bootstrap token.", "request_id": request_id},
                    headers={"X-Request-ID": request_id},
                )
                return response
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
        errors = _sanitize_validation_errors(exc.errors())
        logger.warning(
            "request.validation_failed request_id=%s path=%s errors=%s",
            request_id,
            request.url.path,
            dumps(errors, ensure_ascii=False),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": errors, "request_id": request_id},
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
