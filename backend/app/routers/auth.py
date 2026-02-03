from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.core.auth import create_access_token, decode_token, verify_password
from app.core.database import get_sqlmodel_db
from app.models import User

router = APIRouter(tags=["auth"])

# 由于 main.py 把本 router 挂载到 /api 前缀下，因此 tokenUrl 也需要用 /api/token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


@router.post("/token")
def token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_sqlmodel_db)):
    stmt = select(User).where(User.username == form_data.username)
    user = db.exec(stmt).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.username)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me")
def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_sqlmodel_db)):
    username = decode_token(token)

    stmt = select(User).where(User.username == username)
    user = db.exec(stmt).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return {"id": user.id, "username": user.username}


@router.get("/me")
def read_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_sqlmodel_db)):
    username = decode_token(token)

    stmt = select(User).where(User.username == username)
    user = db.exec(stmt).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    # 与前端 AppLayout 使用字段对齐
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "id": user.id,
            "name": user.username,
            "role": "系统管理员",
            "avatarUrl": "",
        },
    }
