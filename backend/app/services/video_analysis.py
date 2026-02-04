from __future__ import annotations

import json
import os
from typing import List, Tuple, Dict, Any
from uuid import uuid4

import cv2
import numpy as np


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """判断点是否在多边形内（使用 OpenCV pointPolygonTest）。

    point/polygon 都是像素坐标系。
    """
    if not polygon or len(polygon) < 3:
        return False

    contour = np.array(polygon, dtype=np.float32).reshape((-1, 1, 2))
    # >= 0 表示在内部或边界上
    return cv2.pointPolygonTest(contour, point, False) >= 0


def normalize_bbox(bbox_xyxy: List[int], width: int, height: int) -> Dict[str, float]:
    """将 xyxy 转换为 0.0~1.0 归一化坐标"""
    x1, y1, x2, y2 = bbox_xyxy
    return {
        "x": x1 / width,
        "y": y1 / height,
        "w": (x2 - x1) / width,
        "h": (y2 - y1) / height,
    }


def foot_point_from_norm(box_norm: Dict[str, float], width: int, height: int) -> Tuple[float, float]:
    """由归一化 bbox 反推脚点（像素坐标）"""
    x1 = box_norm["x"] * width
    y1 = box_norm["y"] * height
    x2 = (box_norm["x"] + box_norm["w"]) * width
    y2 = (box_norm["y"] + box_norm["h"]) * height
    return (x1 + x2) / 2.0, y2


def analyze_video(video_path: str, video_id: str) -> Dict[str, Any]:
    """
    第一阶段：原始特征提取 (Trigger: 上传视频后)

    - 不接收 zones
    - 仅运行 YOLOv8 + ByteTrack（当前实现先保留 YOLO 检测，轨迹 ID 先用 uuid 占位；后续可接入 ByteTrack 输出稳定 track_id）
    - 生成 raw_tracks.json：每帧 timestamp + objects(id, class, box_norm)
    - 不进行任何报警判定
    - 不写入 AlarmEvent 表
    """

    # 加载 YOLOv8 模型
    try:
        from ultralytics import YOLO

        model = YOLO("yolov8n.pt")
    except Exception as e:
        raise RuntimeError(f"加载 YOLO 模型失败: {e}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    tracks: List[Dict[str, Any]] = []

    frame_id = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp_sec = frame_id / fps

        # 使用 predict 并降低置信度阈值，避免因默认 0.25 过滤掉目标
        results = model.predict(frame, conf=0.25, verbose=False)
        objects: List[Dict[str, Any]] = []

        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls = int(box.cls)

                # 只保留 Person (0) 和 Vehicle (2)
                if cls not in (0, 2):
                    continue

                xyxy = box.xyxy[0].tolist()
                norm_box = normalize_bbox(xyxy, width, height)

                objects.append(
                    {
                        # TODO: 接入 ByteTrack 后，这里应写入稳定的 track_id
                        "id": str(uuid4()),
                        "class": "Person" if cls == 0 else "Vehicle",
                        "box_norm": norm_box,
                    }
                )

        tracks.append(
            {
                "frame_id": frame_id,
                "timestamp": timestamp_sec,
                "objects": objects,
            }
        )

        frame_id += 1

    cap.release()

    raw_tracks_path = f"analysis_results/{video_id}_raw_tracks.json"
    os.makedirs(os.path.dirname(raw_tracks_path), exist_ok=True)
    with open(raw_tracks_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "video_id": video_id,
                "video_path": video_path,
                "width": width,
                "height": height,
                "fps": fps,
                "total_frames": frame_id,
                "tracks": tracks,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "video_id": video_id,
        "raw_tracks_path": raw_tracks_path,
        "total_frames": frame_id,
    }


def compute_alarms(
    *,
    video_id: str,
    video_path: str,
    raw_tracks_path: str,
    zones: List[Dict[str, Any]],
    output_analysis_json_path: str,
) -> Dict[str, Any]:
    """第二阶段：报警规则计算 (Trigger: 保存防区时)

    zones 结构（归一化坐标）示例：
    [{"type":"core","points":[[0.1,0.2],[0.3,0.4],...]}]

    产物：
    - display_overlays.json 写入 output_analysis_json_path
    - 返回 overlays + alarm_events（由调用方决定是否入库）
    """

    if not os.path.exists(raw_tracks_path):
        raise FileNotFoundError(f"raw_tracks.json 不存在: {raw_tracks_path}")

    with open(raw_tracks_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    width = int(raw.get("width") or 0)
    height = int(raw.get("height") or 0)
    fps = float(raw.get("fps") or 0)
    tracks = raw.get("tracks") or []

    # zones 归一化 -> 像素 polygon
    zone_polys: List[Dict[str, Any]] = []
    for z in zones or []:
        pts = z.get("points") or []
        poly = [(float(p[0]) * width, float(p[1]) * height) for p in pts]
        if len(poly) >= 3:
            zone_polys.append({"type": z.get("type"), "polygon": poly})

    overlays = []
    alarm_events = []

    for frame in tracks:
        frame_id = frame.get("frame_id")
        timestamp = frame.get("timestamp")
        objects = frame.get("objects") or []

        display_objects = []
        for obj in objects:
            box_norm = obj.get("box_norm") or {}
            foot_pt = foot_point_from_norm(box_norm, width, height)

            alarm_level = None
            color = "green"

            for zone in zone_polys:
                if point_in_polygon(foot_pt, zone["polygon"]):
                    if zone.get("type") == "core":
                        alarm_level = "CRITICAL"
                        color = "red"
                    elif zone.get("type") == "warning":
                        alarm_level = "WARNING"
                        color = "orange"
                    else:
                        alarm_level = "WARNING"
                        color = "orange"
                    break

            display_objects.append(
                {
                    "id": obj.get("id"),
                    "class": obj.get("class"),
                    "box_norm": box_norm,
                    "alarm_level": alarm_level,
                    "color": color,
                }
            )

            if alarm_level is not None:
                alarm_events.append(
                    {
                        "event_id": str(uuid4()),
                        "video_id": video_id,
                        "video_timestamp": float(timestamp),
                        "object_type": obj.get("class"),
                        "threat_level": alarm_level,
                        "snapshot_path": None,
                    }
                )

        overlays.append({"frame_id": frame_id, "timestamp": timestamp, "objects": display_objects})

    os.makedirs(os.path.dirname(output_analysis_json_path), exist_ok=True)
    with open(output_analysis_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "video_id": video_id,
                "video_path": video_path,
                "width": width,
                "height": height,
                "fps": fps,
                "overlays": overlays,
                "zones": zones,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "analysis_json_path": output_analysis_json_path,
        "alarm_events": alarm_events,
        "alarm_count": len(alarm_events),
    }
