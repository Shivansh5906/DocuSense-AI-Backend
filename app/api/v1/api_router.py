from fastapi import APIRouter
from app.api.v1.routes import health, upload, auth, resume

router = APIRouter(prefix="/api/v1")

router.include_router(health)
router.include_router(upload)
router.include_router(auth)
router.include_router(resume)

