from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import AsyncGenerator
import os

from .config import settings

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# 同步引擎（用于 SQLModel 模型创建和同步操作）
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=True,  # 开发时开启 SQL 日志
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 异步引擎（用于异步操作）
# 异步引擎（用于异步操作）
# 注意：settings.DATABASE_URL 形如 "postgresql+psycopg://..."
# 异步驱动应使用 "postgresql+asyncpg://..."（而不是 "postgresql+asyncpgpsycopg://..."）
async_engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql+psycopg://", "postgresql+asyncpg://"),
    echo=True,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 同步会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# 异步会话工厂
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# 依赖项：获取同步会话
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 依赖项：获取异步会话
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# 创建数据库表（同步）
def create_db_and_tables():
    from app.models import VideoSource, AlarmEvent, ZoneConfig  # 避免循环导入
    SQLModel.metadata.create_all(sync_engine)

# 删除数据库表（开发用）
def drop_all_tables():
    SQLModel.metadata.drop_all(sync_engine)

# 初始化数据库（创建表）
def init_db():
    create_db_and_tables()
    print("✅ Database tables created")