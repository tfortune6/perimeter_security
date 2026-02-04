from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.core.database import get_sqlmodel_db
from app.models import AnalysisStatus, VideoSource

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/events")
def get_dashboard_events(limit: int = 20, db: Session = Depends(get_sqlmodel_db)):
    return {"code": 0, "message": "ok", "data": []}


@router.get("/dashboard/overlays")
def get_dashboard_overlays(
    video_id: Optional[str] = None,
    sourceId: Optional[str] = None,
    db: Session = Depends(get_sqlmodel_db),
):
    target_id = video_id or sourceId
    if not target_id:
        return {"code": 0, "message": "ok", "data": {"boxes": []}}

    video = db.get(VideoSource, target_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if video.analysis_status != AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=202, detail="分析尚未完成")

    if not video.analysis_json_path or not os.path.exists(video.analysis_json_path):
        raise HTTPException(status_code=404, detail="分析结果文件不存在")

    try:
        with open(video.analysis_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容新旧结构：新结构是 {overlays: [...]}，旧结构可能是 {frames: [...]}
        overlays = data.get("overlays") or data.get("frames") or []
        zones = data.get("zones") or []
        return {"code": 0, "message": "ok", "data": {"overlays": overlays, "zones": zones}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取分析结果失败: {e}")
