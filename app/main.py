from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.api.universe_routes import router as universe_router
from app.api.screener_routes import router as screener_router
from app.core.config import get_settings
from app.db.init_db import init_db
from app.services.scheduler_service import scheduler_service


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    # Allow Next.js dev server to call the API from the browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup():
        init_db()
        scheduler_service.start()

    @app.on_event("shutdown")
    def _shutdown():
        scheduler_service.shutdown()

    app.include_router(auth_router)
    app.include_router(universe_router)
    app.include_router(screener_router)
    app.include_router(router)
    return app


app = create_app()

