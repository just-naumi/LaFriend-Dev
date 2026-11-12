from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.courses import router as courses_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(courses_router)

