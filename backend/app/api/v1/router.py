"""Agregador das rotas compartilhadas sob o prefixo /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, health
from app.modules.access.controllers import router as access_router
from app.modules.audit.controllers import router as audit_router
from app.modules.catalogs.controllers import router as catalogs_router
from app.modules.comments.controllers import router as comments_router
from app.modules.dashboard.controllers import router as dashboard_router
from app.modules.equipments.controllers import router as equipments_router
from app.modules.notifications.controllers import router as notifications_router
from app.modules.processes.controllers import router as processes_router
from app.modules.queues.controllers import router as queues_router
from app.modules.suppliers.controllers import router as suppliers_router
from app.modules.users.controllers import router as users_router
from app.modules.workflow.controllers import router as workflow_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users_router)
api_router.include_router(access_router)
api_router.include_router(audit_router)
api_router.include_router(catalogs_router)
api_router.include_router(comments_router)
api_router.include_router(equipments_router)
api_router.include_router(notifications_router)
api_router.include_router(processes_router)
api_router.include_router(workflow_router)
api_router.include_router(queues_router)
api_router.include_router(suppliers_router)
api_router.include_router(dashboard_router)
