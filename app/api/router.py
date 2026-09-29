from fastapi import APIRouter
from app.api.v1 import (
    auth,
    office_leads,
    office_telecaller,
    office_hr,
    office_bdm,
    office_operations,
    office_governance,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(office_leads.router)
api_router.include_router(office_telecaller.router)
api_router.include_router(office_hr.router)
api_router.include_router(office_bdm.router)
api_router.include_router(office_operations.router)
api_router.include_router(office_governance.router)