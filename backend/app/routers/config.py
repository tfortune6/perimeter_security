from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_sqlmodel_db
from app.models import SystemSettings, VideoSource, Zone

router = APIRouter(tags=["config"])

VIEWBOX_W = 800.0
VIEWBOX_H = 450.0


def _source_to_dict(s: VideoSource) -> dict:
    # 与前端 Dashboard 的 sources 下拉兼容：{id, name}
    return {"id": str(s.video_id), "name": s.file_name}


def _to_norm_points(view_pts):
    """前端传入 viewBox(800x450) 坐标 -> 归一化坐标"""
    if not isinstance(view_pts, list):
        return []
    norm = []
    for p in view_pts:
        if not isinstance(p, list) or len(p) < 2:
            continue
        try:
            x = float(p[0])
            y = float(p[1])
        except Exception:
            continue
        norm.append([x / VIEWBOX_W, y / VIEWBOX_H])
    return norm


def _to_view_points(norm_pts):
    """数据库归一化坐标 -> 前端 viewBox(800x450) 坐标"""
    if not isinstance(norm_pts, list):
        return []
    view = []
    for p in norm_pts:
        if not isinstance(p, list) or len(p) < 2:
            continue
        try:
            x = float(p[0])
            y = float(p[1])
        except Exception:
            continue
        view.append([x * VIEWBOX_W, y * VIEWBOX_H])
    return view


def _zone_to_dict(z: Zone) -> dict:
    return {
        "id": z.id,
        "name": z.name,
        "type": z.type,
        "threshold": z.threshold,
        "motion": z.motion,
        "polygonPoints": _to_view_points(z.polygon_points),
    }


@router.get("/sources")
def list_sources(db: Session = Depends(get_sqlmodel_db)):
    items = db.exec(select(VideoSource).order_by(VideoSource.upload_time.desc())).all()
    return {"code": 0, "message": "ok", "data": [_source_to_dict(x) for x in items]}


@router.get("/system/status")
def get_system_status(db: Session = Depends(get_sqlmodel_db)):
    settings = db.get(SystemSettings, 1)
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)

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
    settings = db.get(SystemSettings, 1)
    if not settings:
        settings = SystemSettings(id=1)
        db.add(settings)

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

    if "online" in patch:
        settings.online = bool(patch["online"])
    if "fps" in patch:
        settings.fps = int(patch["fps"])
    if "version" in patch:
        settings.version = str(patch["version"])

    db.add(settings)
    db.commit()
    db.refresh(settings)

    if settings.current_source_id:
        all_videos = db.exec(select(VideoSource)).all()
        for v in all_videos:
            v.is_demo = v.video_id == settings.current_source_id
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


@router.get("/zones")
def list_zones(sourceId: str, db: Session = Depends(get_sqlmodel_db)):
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
        zone_id = f"zone-{datetime.now(tz=timezone.utc).timestamp():.0f}"

    row = Zone(
        id=str(zone_id),
        source_id=source_uuid,
        name=payload.get("name") or "新建区域",
        type=payload.get("type") or "core",
        threshold=float(payload.get("threshold") or 3),
        motion=bool(payload.get("motion", True)),
        polygon_points=_to_norm_points(polygon_points),
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
        row.polygon_points = _to_norm_points(pts)

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

    zones = db.exec(select(Zone).where(Zone.source_id == source_uuid)).all()
    zones_payload = [{"type": z.type, "points": z.polygon_points} for z in zones]

    from app.models import AlarmEvent, ObjectType, ThreatLevel
    from app.core.database import sync_engine
    from app.services.video_analysis import compute_alarms
    from sqlalchemy import delete
    from sqlmodel import Session

    analysis_json_path = f"analysis_results/{video.video_id}.json"
    result = compute_alarms(
        video_id=str(video.video_id),
        video_path=video.file_path,
        raw_tracks_path=video.raw_tracks_path,
        zones=zones_payload,
        output_analysis_json_path=analysis_json_path,
    )

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
