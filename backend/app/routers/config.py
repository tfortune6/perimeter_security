from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_sqlmodel_db
from app.models import Zone

router = APIRouter(tags=["config"])


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
    # 演示接口：返回保存时间
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "sourceId": sourceId,
            "savedAt": datetime.now(tz=timezone.utc).isoformat(),
        },
    }
