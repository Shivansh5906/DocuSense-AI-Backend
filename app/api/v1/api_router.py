from fastapi import APIRouter
from app.api.v1.routes import health, upload, query, summary

router = APIRouter(prefix="/api/v1")

router.include_router(health)
router.include_router(upload)
router.include_router(query)
router.include_router(summary)
