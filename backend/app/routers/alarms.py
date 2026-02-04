from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_sqlmodel_db
from app.models import AlarmEvent, VideoSource

router = APIRouter(tags=["alarms"])


def _alarm_to_dict(a: AlarmEvent) -> dict:
    return {
        "id": f"#{a.event_id}",
        "thumb": a.snapshot_path,
        "time": a.video_timestamp,
        "target": a.object_type.value,
        "severity": "critical" if a.threat_level == 1 else "warning",
        "status": "pending",  # 暂时固定，后续可扩展状态字段
    }


@router.get("/alarms")
def list_alarms(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    query: Optional[str] = Query(default=""),
    level: Optional[str] = Query(default=""),
    startDate: Optional[str] = Query(default=""),
    endDate: Optional[str] = Query(default=""),
    db: Session = Depends(get_sqlmodel_db),
):
    stmt = select(AlarmEvent)

    # 按关键字搜索（ID 或备注，暂无备注字段，先只支持 ID）
    if query:
        cleaned = query.replace("#", "")
        try:
            uuid_obj = UUID(cleaned)
            stmt = stmt.where(AlarmEvent.event_id == uuid_obj)
        except Exception:
            # 非合法 UUID，跳过过滤
            pass

    # 按威胁等级过滤
    if level == "critical":
        stmt = stmt.where(AlarmEvent.threat_level == 1)
    elif level == "warning":
        stmt = stmt.where(AlarmEvent.threat_level == 2)

    # TODO: 按日期范围过滤（需要 video_timestamp 为可解析的时间格式）
    # 当前 video_timestamp 是字符串（秒或时间戳），暂不实现日期过滤

    total = len(db.exec(stmt).all())
    items = db.exec(stmt.offset((page - 1) * pageSize).limit(pageSize)).all()

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "list": [_alarm_to_dict(a) for a in items],
            "total": total,
        },
    }


@router.get("/alarms/{alarm_id}")
def get_alarm_detail(alarm_id: str, db: Session = Depends(get_sqlmodel_db)):
    cleaned = alarm_id.replace("#", "")
    try:
        uuid_obj = UUID(cleaned)
    except Exception:
        raise HTTPException(status_code=400, detail="告警 ID 格式不正确")

    alarm = db.get(AlarmEvent, uuid_obj)
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    # 详情页额外字段（zone、remark）暂为空，后续可扩展
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "id": f"#{alarm.event_id}",
            "thumb": alarm.snapshot_path,
            "time": alarm.video_timestamp,
            "target": alarm.object_type.value,
            "severity": "critical" if alarm.threat_level == 1 else "warning",
            "status": "pending",
            "zone": "",  # 暂时留空
            "remark": "",  # 暂时留空
        },
    }