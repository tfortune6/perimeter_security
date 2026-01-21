from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.routers import video


def create_app() -> FastAPI:
    app = FastAPI(title="基于视觉的周界防护分级报警系统", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )

    app.include_router(video.router, prefix="/api")

    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.on_event("startup")
    def on_startup():
        init_db()

    return app


app = create_app()
