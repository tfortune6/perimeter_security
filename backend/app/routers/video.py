import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List
from uuid import UUID

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_sqlmodel_db, sync_engine
from app.models import AlarmEvent, AnalysisStatus, SystemSettings, VideoSource, Zone, ZoneConfig
from app.services.video_analysis import analyze_video

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
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_sqlmodel_db),
):
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
        analysis_status=AnalysisStatus.PROCESSING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)


    # 注册后台任务：视频分析
    def run_analysis():
        from sqlmodel import Session

        try:
            result = analyze_video(
                video_path=save_path,
                video_id=str(row.video_id),
            )

            # 第一阶段完成：写入 raw_tracks_path，并标记为 COMPLETED（表示特征提取完成）
            with Session(sync_engine) as db2:
                video = db2.get(VideoSource, str(row.video_id))
                if video:
                    video.analysis_status = AnalysisStatus.COMPLETED
                    video.raw_tracks_path = result.get("raw_tracks_path")
                    db2.add(video)
                    db2.commit()
        except Exception as e:
            # 失败则标记为失败状态
            with Session(sync_engine) as db2:
                video = db2.get(VideoSource, str(row.video_id))
                if video:
                    video.analysis_status = AnalysisStatus.FAILED
                    db2.add(video)
                    db2.commit()
            print(f"分析任务失败: {e}")

    # 将任务注册到 BackgroundTasks（在响应返回后执行）
    background_tasks.add_task(run_analysis)

    return {"code": 0, "message": "ok", "data": _to_ui_dict(row)}


@router.get("/videos")
def list_videos(keyword: Optional[str] = None, db: Session = Depends(get_sqlmodel_db)):
    settings = db.get(SystemSettings, 1)
    current_id = str(settings.current_source_id) if settings and settings.current_source_id else ""

    stmt = select(VideoSource)
    if keyword:
        stmt = stmt.where(VideoSource.file_name.ilike(f"%{keyword}%"))
    items = db.exec(stmt.order_by(VideoSource.upload_time.desc())).all()

    data = []
    for v in items:
        row = _to_ui_dict(v)
        # 以 system_settings.current_source_id 为权威“当前演示源”
        row["isDemo"] = bool(current_id and str(v.video_id) == current_id)
        # 补充分析元信息
        row["analysisStatus"] = getattr(v.analysis_status, "value", v.analysis_status)
        row["analysisJsonPath"] = v.analysis_json_path
        data.append(row)

    return {"code": 0, "message": "ok", "data": data}


@router.get("/videos/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_sqlmodel_db)):
    # 避免与 /videos/demo 等固定路径冲突：非 UUID 直接 404
    try:
        UUID(video_id)
    except Exception:
        raise HTTPException(status_code=404, detail="视频不存在")

    v = db.get(VideoSource, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="视频不存在")

    settings = db.get(SystemSettings, 1)
    current_id = str(settings.current_source_id) if settings and settings.current_source_id else ""

    row = _to_ui_dict(v)
    row["isDemo"] = bool(current_id and str(v.video_id) == current_id)
    row["analysisStatus"] = getattr(v.analysis_status, "value", v.analysis_status)
    row["analysisJsonPath"] = v.analysis_json_path

    return {"code": 0, "message": "ok", "data": row}


@router.post("/videos/{video_id}/set-demo")
def set_demo(video_id: str, db: Session = Depends(get_sqlmodel_db)):
    target_video = db.get(VideoSource, video_id)
    if not target_video:
        raise HTTPException(status_code=404, detail="视频不存在")

    # 统一写入 system_settings.current_source_id（权威状态）
    settings = db.get(SystemSettings, 1)
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)

    settings.current_source_id = target_video.video_id
    db.add(settings)
    db.commit()
    db.refresh(settings)

    # 保持 is_demo 字段同步（兼容旧逻辑）
    all_videos = db.exec(select(VideoSource)).all()
    for v in all_videos:
        v.is_demo = (v.video_id == target_video.video_id)
        db.add(v)
    db.commit()

    return {"code": 0, "message": "ok", "data": _to_ui_dict(target_video)}


@router.get("/videos/demo")
def get_demo_video(db: Session = Depends(get_sqlmodel_db)):
    # 仪表盘大屏使用的“当前源视频”：优先 system_settings.current_source_id
    settings = db.get(SystemSettings, 1)
    current_id = settings.current_source_id if settings else None

    video = None
    if current_id:
        video = db.get(VideoSource, str(current_id))

    if not video:
        # fallback：取最新上传视频
        video = db.exec(select(VideoSource).order_by(VideoSource.upload_time.desc())).first()

    if not video:
        return {"code": 0, "message": "ok", "data": None}

    return {"code": 0, "message": "ok", "data": _to_ui_dict(video)}


@router.delete("/videos/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_sqlmodel_db)):
    target_video = db.get(VideoSource, video_id)
    if not target_video:
        raise HTTPException(status_code=404, detail="视频不存在")

    # 删除前检查关联数据，避免外键约束导致 500
    zone_count = db.exec(select(Zone).where(Zone.source_id == target_video.video_id)).all()
    alarm_count = db.exec(select(AlarmEvent).where(AlarmEvent.video_id == target_video.video_id)).all()
    config_count = db.exec(select(ZoneConfig).where(ZoneConfig.video_id == target_video.video_id)).all()

    if zone_count or alarm_count or config_count:
        raise HTTPException(
            status_code=400,
            detail="删除失败：该视频源存在关联数据（区域/告警/配置）。请先在【配置中心】删除该视频源的区域，并清理相关告警记录/配置后，再重试删除。",
        )

    try:
        if os.path.exists(target_video.file_path):
            os.remove(target_video.file_path)
    except Exception as e:
        print(f"Warn: Failed to delete file {target_video.file_path}: {e}")

    # 如果删除的是当前选择源（system_settings.current_source_id），需先清空设置，避免外键约束导致 500
    settings = db.get(SystemSettings, 1)
    if settings and settings.current_source_id and str(settings.current_source_id) == str(video_id):
        settings.current_source_id = None
        db.add(settings)
        db.commit()

    db.delete(target_video)
    db.commit()

    return {"code": 0, "message": "ok", "data": True}
