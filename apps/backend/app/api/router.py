from fastapi import APIRouter

from app.api.routes.activity import router as activity_router
from app.api.routes.agent import router as agent_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.cron_jobs import router as cron_jobs_router
from app.api.routes.execution import router as execution_router
from app.api.routes.health import router as health_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.settings import router as settings_router
from app.api.routes.skills import router as skills_router
from app.api.routes.tools import router as tools_router

api_router = APIRouter()
api_router.include_router(activity_router)
api_router.include_router(approvals_router)
api_router.include_router(agent_router)
api_router.include_router(execution_router)
api_router.include_router(health_router)
api_router.include_router(skills_router)
api_router.include_router(cron_jobs_router)
api_router.include_router(sessions_router)
api_router.include_router(settings_router)
api_router.include_router(tools_router)
