from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import select
from sqlmodel import Session as SQLModelSession

from app.core.auth import hash_password
from app.core.database import SessionLocal, init_db
from app.models import User
from app.routers import auth, video


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) 初始化表
    init_db()

    # 2) 演示账号初始化：若无用户则创建 admin/123456
    db: SQLModelSession = SQLModelSession(SessionLocal.kw["bind"])
    try:
        existing = db.exec(select(User).limit(1)).first()
        if not existing:
            admin = User(username="admin", password_hash=hash_password("123456"))
            db.add(admin)
            db.commit()
    finally:
        db.close()

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="基于视觉的周界防护分级报警系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 认证：/api/token
    app.include_router(auth.router, prefix="/api")

    # 业务：/api/...
    app.include_router(video.router, prefix="/api")

    app.mount("/static", StaticFiles(directory="static"), name="static")

    return app


app = create_app()
