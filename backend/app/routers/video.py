import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_sqlmodel_db
from app.models import VideoSource

router = APIRouter(tags=["videos"])

ALLOWED_EXT = {".mp4", ".avi", ".webm", ".mkv"}


def _format_size(size_bytes: int) -> str:
    if size_bytes > 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _format_duration(seconds: float) -> str:
    if not seconds or seconds < 0:
        return "00:00:00"
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _to_beijing(dt: datetime) -> datetime:
    """将 naive/aware datetime 转为北京时间（UTC+8）再用于展示。"""
    if dt.tzinfo is None:
        # 当前项目历史上使用 datetime.utcnow() 写库，属于 UTC naive
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=8)))


def _to_ui_dict(v: VideoSource) -> dict:
    """将数据库模型转换为前端 UI 需要的字典格式。"""
    upload_at = _to_beijing(v.upload_time).strftime("%Y-%m-%d %H:%M")

    return {
        "id": str(v.video_id),
        "name": v.file_name,
        "ext": (v.ext or "").upper(),
        "quality": "",  # 暂时留空，可后续从视频元数据解析
        "size": v.size,
        "duration": _format_duration(v.duration),
        "uploadAt": upload_at,
        "isDemo": v.is_demo,
        "previewUrl": f"/static/uploads/{Path(v.file_path).name}",
    }


@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_sqlmodel_db)):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式：{ext}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # 文件名用北京时间时间戳，方便与前端显示一致
    ts = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime(
        "%Y%m%d_%H%M%S"
    )
    safe_name = os.path.basename(filename)
    save_path = str(Path(settings.UPLOAD_DIR) / f"{ts}_{safe_name}")

    size_bytes = 0
    try:
        with open(save_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                size_bytes += len(chunk)
                f.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    cap = cv2.VideoCapture(save_path)
    duration_sec = 0.0
    if cap.isOpened():
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if fps > 0:
            duration_sec = float(frames / fps)
    cap.release()

    row = VideoSource(
        file_name=safe_name,
        file_path=save_path,
        duration=duration_sec,
        ext=ext.replace(".", ""),
        size=_format_size(size_bytes),
        is_demo=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {"code": 0, "message": "ok", "data": _to_ui_dict(row)}


@router.get("/videos")
def list_videos(keyword: Optional[str] = None, db: Session = Depends(get_sqlmodel_db)):
    stmt = select(VideoSource)
    if keyword:
        stmt = stmt.where(VideoSource.file_name.ilike(f"%{keyword}%"))
    items = db.exec(stmt.order_by(VideoSource.upload_time.desc())).all()

    return {"code": 0, "message": "ok", "data": [_to_ui_dict(v) for v in items]}


@router.post("/videos/{video_id}/set-demo")
def set_demo(video_id: str, db: Session = Depends(get_sqlmodel_db)):
    all_videos = db.exec(select(VideoSource)).all()
    for v in all_videos:
        v.is_demo = False
        db.add(v)

    target_video = db.get(VideoSource, video_id)
    if not target_video:
        raise HTTPException(status_code=404, detail="视频不存在")
    target_video.is_demo = True
    db.add(target_video)
    db.commit()
    db.refresh(target_video)

    return {"code": 0, "message": "ok", "data": _to_ui_dict(target_video)}


@router.delete("/videos/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_sqlmodel_db)):
    target_video = db.get(VideoSource, video_id)
    if not target_video:
        raise HTTPException(status_code=404, detail="视频不存在")

    try:
        if os.path.exists(target_video.file_path):
            os.remove(target_video.file_path)
    except Exception as e:
        print(f"Warn: Failed to delete file {target_video.file_path}: {e}")

    db.delete(target_video)
    db.commit()

    return {"code": 0, "message": "ok", "data": True}
