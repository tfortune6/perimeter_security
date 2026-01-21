import os
from datetime import datetime
from pathlib import Path
from typing import List

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_db
from app.models import VideoSource

router = APIRouter(tags=["videos"])

ALLOWED_EXT = {".mp4", ".avi"}


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _get_video_duration_seconds(file_path: str) -> float:
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        cap.release()
        return 0.0

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()

    if fps <= 0:
        return 0.0
    return float(frames / fps)


def _build_upload_path(file_name: str) -> str:
    # 防止目录穿越，只取 basename
    safe_name = os.path.basename(file_name)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return str(Path(settings.UPLOAD_DIR) / f"{ts}_{safe_name}")


@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1) 校验格式
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式：{ext}，仅支持 MP4/AVI")

    # 2) 保存文件到 static/uploads
    _ensure_dir(settings.UPLOAD_DIR)
    save_path = _build_upload_path(filename)

    try:
        with open(save_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    # 3) 读取时长
    duration = _get_video_duration_seconds(save_path)

    # 4) 写入数据库
    row = VideoSource(
        file_name=os.path.basename(filename),
        file_path=save_path,
        duration=duration,
        is_active=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "video_id": str(row.video_id),
            "file_name": row.file_name,
            "file_path": row.file_path,
            "duration": row.duration,
            "is_active": row.is_active,
            "upload_time": row.upload_time.isoformat(),
            # 提供可访问的静态URL（前端可直接用 /static/...）
            "url": f"/static/uploads/{Path(row.file_path).name}",
        },
    }


@router.get("/videos")
def list_videos(db: Session = Depends(get_db)):
    stmt = select(VideoSource).order_by(VideoSource.upload_time.desc())
    items = db.exec(stmt).all()

    return {
        "code": 0,
        "message": "ok",
        "data": [
            {
                "video_id": str(v.video_id),
                "file_name": v.file_name,
                "file_path": v.file_path,
                "duration": v.duration,
                "is_active": v.is_active,
                "upload_time": v.upload_time.isoformat(),
                "url": f"/static/uploads/{Path(v.file_path).name}",
            }
            for v in items
        ],
    }
