"""路由总装配。"""
from fastapi import APIRouter

from src.routes import auth, batches, diffs, meta, pairs, signoffs, tickets

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(pairs.router)
api_router.include_router(batches.router)
api_router.include_router(diffs.router)
api_router.include_router(tickets.router)
api_router.include_router(signoffs.router)
api_router.include_router(meta.router)

__all__ = ["api_router"]
