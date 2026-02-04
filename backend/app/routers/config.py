from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_sqlmodel_db
from app.models import VideoSource, Zone, SystemSettings

router = APIRouter(tags=["config"])


def _source_to_dict(s: VideoSource) -> dict:
    # 与前端 Dashboard 的 sources 下拉兼容：{id, name}
    return {"id": str(s.video_id), "name": s.file_name}


@router.get("/sources")
def list_sources(db: Session = Depends(get_sqlmodel_db)):
    items = db.exec(select(VideoSource).order_by(VideoSource.upload_time.desc())).all()
    return {"code": 0, "message": "ok", "data": [_source_to_dict(x) for x in items]}


@router.get("/system/status")
def get_system_status(db: Session = Depends(get_sqlmodel_db)):
    # 读取持久化配置，若不存在则初始化
    settings = db.get(SystemSettings, 1)
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    # 若未设置 current_source_id，则使用最新视频作为默认
    current = settings.current_source_id
    if not current:
        latest = db.exec(select(VideoSource).order_by(VideoSource.upload_time.desc())).first()
        if latest:
            current = latest.video_id
            settings.current_source_id = current
            db.add(settings)
            db.commit()

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "online": settings.online,
            "version": settings.version,
            "fps": settings.fps,
            "currentSourceId": str(current) if current else "",
        },
    }


@router.put("/system/status")
def update_system_status(patch: dict, db: Session = Depends(get_sqlmodel_db)):
    # 确保配置行存在
    settings = db.get(SystemSettings, 1)
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)

    # 更新 currentSourceId（若传入）
    current = patch.get("currentSourceId")
    if current is not None:
        try:
            source_uuid = UUID(str(current))
        except Exception:
            raise HTTPException(status_code=400, detail="currentSourceId 格式不正确")

        exists = db.exec(select(VideoSource).where(VideoSource.video_id == source_uuid)).first()
        if not exists:
            raise HTTPException(status_code=400, detail="currentSourceId 不存在")

        settings.current_source_id = source_uuid

    # 可选：更新其他字段（暂不暴露给前端）
    if "online" in patch:
        settings.online = bool(patch["online"])
    if "fps" in patch:
        settings.fps = int(patch["fps"])
    if "version" in patch:
        settings.version = str(patch["version"])

    db.add(settings)
    db.commit()
    db.refresh(settings)

    # 同步 video_sources.is_demo（兼容旧逻辑/列表展示）
    if settings.current_source_id:
        all_videos = db.exec(select(VideoSource)).all()
        for v in all_videos:
            v.is_demo = (v.video_id == settings.current_source_id)
            db.add(v)
        db.commit()

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "online": settings.online,
            "version": settings.version,
            "fps": settings.fps,
            "currentSourceId": str(settings.current_source_id) if settings.current_source_id else "",
        },
    }


def _zone_to_dict(z: Zone) -> dict:
    return {
        "id": z.id,
        "name": z.name,
        "type": z.type,
        "threshold": z.threshold,
        "motion": z.motion,
        "polygonPoints": z.polygon_points,
    }


@router.get("/zones")
def list_zones(sourceId: str, db: Session = Depends(get_sqlmodel_db)):
    # sourceId 为前端传入的视频 id（UUID 字符串）
    try:
        source_uuid = UUID(sourceId)
    except Exception:
        raise HTTPException(status_code=400, detail="sourceId 格式不正确")

    items = db.exec(select(Zone).where(Zone.source_id == source_uuid)).all()
    return {"code": 0, "message": "ok", "data": [_zone_to_dict(x) for x in items]}


@router.post("/zones")
def create_zone(sourceId: str, payload: dict, db: Session = Depends(get_sqlmodel_db)):
    try:
        source_uuid = UUID(sourceId)
    except Exception:
        raise HTTPException(status_code=400, detail="sourceId 格式不正确")

    polygon_points = payload.get("polygonPoints")
    if not isinstance(polygon_points, list) or len(polygon_points) < 3:
        raise HTTPException(status_code=400, detail="多边形至少需要 3 个点")

    zone_id = payload.get("id")
    if not zone_id:
        # 与 mock 保持一致的 id 前缀风格
        zone_id = f"zone-{datetime.now(tz=timezone.utc).timestamp():.0f}"

    row = Zone(
        id=str(zone_id),
        source_id=source_uuid,
        name=payload.get("name") or "新建区域",
        type=payload.get("type") or "core",
        threshold=float(payload.get("threshold") or 3),
        motion=bool(payload.get("motion", True)),
        polygon_points=polygon_points,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return {"code": 0, "message": "ok", "data": _zone_to_dict(row)}


@router.put("/zones/{zone_id}")
def update_zone(zone_id: str, patch: dict, db: Session = Depends(get_sqlmodel_db)):
    row = db.get(Zone, zone_id)
    if not row:
        raise HTTPException(status_code=404, detail="区域不存在")

    if "name" in patch:
        row.name = patch["name"]
    if "type" in patch:
        row.type = patch["type"]
    if "threshold" in patch:
        row.threshold = float(patch["threshold"])
    if "motion" in patch:
        row.motion = bool(patch["motion"])
    if "polygonPoints" in patch:
        pts = patch["polygonPoints"]
        if not isinstance(pts, list) or len(pts) < 3:
            raise HTTPException(status_code=400, detail="多边形至少需要 3 个点")
        row.polygon_points = pts

    db.add(row)
    db.commit()
    db.refresh(row)

    return {"code": 0, "message": "ok", "data": _zone_to_dict(row)}


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str, db: Session = Depends(get_sqlmodel_db)):
    row = db.get(Zone, zone_id)
    if not row:
        raise HTTPException(status_code=404, detail="区域不存在")

    db.delete(row)
    db.commit()

    return {"code": 0, "message": "ok", "data": True}


@router.post("/config/save")
def save_config(sourceId: Optional[str] = None, db: Session = Depends(get_sqlmodel_db)):
    if not sourceId:
        raise HTTPException(status_code=400, detail="sourceId 必需")

    try:
        source_uuid = UUID(sourceId)
    except Exception:
        raise HTTPException(status_code=400, detail="sourceId 格式不正确")

    video = db.get(VideoSource, source_uuid)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if not video.raw_tracks_path:
        raise HTTPException(status_code=400, detail="该视频尚未完成特征提取，请稍后再试")

    # 读取当前防区
    zones = db.exec(select(Zone).where(Zone.source_id == source_uuid)).all()
    zones_payload = [
        {"type": z.type, "points": z.polygon_points} for z in zones
    ]

    # 第二阶段：报警规则计算
    from app.services.video_analysis import compute_alarms
    from app.models import AlarmEvent, ThreatLevel, ObjectType
    from sqlmodel import Session
    from app.core.database import sync_engine

    analysis_json_path = f"analysis_results/{video.video_id}.json"
    result = compute_alarms(
        video_id=str(video.video_id),
        video_path=video.file_path,
        raw_tracks_path=video.raw_tracks_path,
        zones=zones_payload,
        output_analysis_json_path=analysis_json_path,
    )

    # 清理旧报警记录并写入新记录（事务安全）
    from sqlalchemy import delete
    with Session(sync_engine) as tx:
        tx.exec(delete(AlarmEvent).where(AlarmEvent.video_id == video.video_id))
        for ev in result.get("alarm_events") or []:
            alarm = AlarmEvent(
                event_id=UUID(ev["event_id"]),
                video_id=UUID(ev["video_id"]),
                video_timestamp=ev["video_timestamp"],
                object_type=ObjectType.PERSON if ev["object_type"] == "Person" else ObjectType.VEHICLE,
                threat_level=ThreatLevel.CRITICAL if ev["threat_level"] == "CRITICAL" else ThreatLevel.WARNING,
                snapshot_path=ev.get("snapshot_path") or "",
            )
            tx.add(alarm)
        tx.commit()

    # 更新 video.analysis_json_path
    video.analysis_json_path = analysis_json_path
    db.add(video)
    db.commit()

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "sourceId": sourceId,
            "savedAt": datetime.now(tz=timezone.utc).isoformat(),
            "alarmCount": result.get("alarm_count", 0),
        },
    }
