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

        # 使用 Ultralytics 内置 track（ByteTrack）输出稳定 track_id
        # 只需要 track_id 用于后续去抖动/冷却/逗留判定
        results = model.track(
            frame,
            conf=0.25,
            verbose=False,
            persist=True,
            tracker="bytetrack.yaml",
        )

        objects: List[Dict[str, Any]] = []

        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None or len(boxes) == 0:
                continue

            # Ultralytics Boxes 上可用属性：cls, xyxy, id
            clss = boxes.cls
            xyxys = boxes.xyxy
            ids = getattr(boxes, "id", None)

            for i in range(len(boxes)):
                cls = int(clss[i])

                # 只保留 Person (0) 和 Vehicle (2)
                if cls not in (0, 2):
                    continue

                xyxy = xyxys[i].tolist()
                norm_box = normalize_bbox(xyxy, width, height)

                track_id = None
                if ids is not None:
                    try:
                        track_id = int(ids[i])
                    except Exception:
                        track_id = None

                # fallback：如果该帧没给 id，就退化为 uuid
                obj_id = f"t{track_id}" if track_id is not None else str(uuid4())

                objects.append(
                    {
                        "id": obj_id,
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

    新增机制：
    - 去抖动：目标连续 N 帧在区内才确认状态切换（默认 10 帧，约 0.4s）
    - 报警冷却：同一目标触发后进入冷却期（默认 5s），期间不新增事件

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

    # zones 归一化 -> 像素 polygon（保留 id/name 便于输出 zoneName）
    zone_polys: List[Dict[str, Any]] = []
    for z in zones or []:
        pts = z.get("points") or []
        poly = [(float(p[0]) * width, float(p[1]) * height) for p in pts]
        if len(poly) >= 3:
            zone_polys.append(
                {
                    "id": z.get("id") or z.get("zone_id") or z.get("zoneId"),
                    "name": z.get("name") or z.get("zone_name") or z.get("zoneName"),
                    "type": z.get("type"),
                    "polygon": poly,
                }
            )

    # 去抖动与冷却机制参数
    DEBOUNCE_FRAMES = 10  # 连续 N 帧在区内才确认入侵
    COOLDOWN_SECONDS = 5.0  # 冷却期（秒）

    # 黄色警戒区逗留阈值：连续停留超过该时间才触发（防路人穿越误报）
    WARNING_LOITER_SECONDS = 5.0

    # 追踪每个目标的状态（基于临时 id）
    # key: object_id -> {
    #   in_core: bool,
    #   core_consecutive: int,
    #   last_core_alarm_ts: float,
    #   warning_enter_ts: Optional[float],
    #   warning_last_seen_ts: Optional[float],
    #   warning_triggered: bool,
    #   last_warning_alarm_ts: float,
    # }
    target_state: Dict[str, Dict[str, Any]] = {}

    overlays = []
    alarm_events = []

    for frame in tracks:
        frame_id = frame.get("frame_id")
        timestamp = frame.get("timestamp")
        objects = frame.get("objects") or []

        display_objects = []
        for obj in objects:
            obj_id = obj.get("id")
            box_norm = obj.get("box_norm") or {}
            foot_pt = foot_point_from_norm(box_norm, width, height)

            alarm_level = None
            color = "green"

            # 判断所在区域（core 优先于 warning）
            in_core_now = False
            in_warning_now = False
            hit_zone_id = None
            hit_zone_name = None
            for zone in zone_polys:
                if not point_in_polygon(foot_pt, zone["polygon"]):
                    continue
                if zone.get("type") == "core":
                    in_core_now = True
                    hit_zone_id = zone.get("id")
                    hit_zone_name = zone.get("name")
                    break
                if zone.get("type") == "warning":
                    in_warning_now = True
                    hit_zone_id = zone.get("id")
                    hit_zone_name = zone.get("name")

            if in_core_now:
                alarm_level = "CRITICAL"
                color = "red"
            elif in_warning_now:
                alarm_level = "WARNING"
                color = "orange"
            else:
                alarm_level = None
                color = "green"

            display_objects.append(
                {
                    "id": obj_id,
                    "class": obj.get("class"),
                    "box_norm": box_norm,
                    "alarm_level": alarm_level,
                    "color": color,
                    "zone_id": hit_zone_id,
                    "zoneName": hit_zone_name,
                }
            )

            # 去抖动 + 冷却 + 黄色区逗留判定
            if obj_id:
                state = target_state.setdefault(
                    obj_id,
                    {
                        "in_core": False,
                        "core_consecutive": 0,
                        "last_core_alarm_ts": -1.0,
                        "warning_enter_ts": None,
                        "warning_last_seen_ts": None,
                        "warning_triggered": False,
                        "last_warning_alarm_ts": -1.0,
                    },
                )

                ts = float(timestamp)

                # --- core 区：去抖动 + 冷却 ---
                if in_core_now:
                    state["core_consecutive"] += 1
                else:
                    state["core_consecutive"] = max(int(state.get("core_consecutive") or 0) - 1, 0)

                if (
                    (not state.get("in_core"))
                    and in_core_now
                    and int(state.get("core_consecutive") or 0) >= DEBOUNCE_FRAMES
                ):
                    state["in_core"] = True
                    if ts - float(state.get("last_core_alarm_ts") or -1.0) >= COOLDOWN_SECONDS:
                        alarm_events.append(
                            {
                                "event_id": str(uuid4()),
                                "video_id": video_id,
                                "video_timestamp": ts,
                                "object_type": obj.get("class"),
                                "threat_level": "CRITICAL",
                                "snapshot_path": None,
                            }
                        )
                        state["last_core_alarm_ts"] = ts
                elif state.get("in_core") and not in_core_now:
                    state["in_core"] = False

                # --- warning 区：逗留阈值 + 冷却 ---
                # 规则：目标在黄色区连续停留时间 t > WARNING_LOITER_SECONDS 才触发；短暂穿越视为路人
                if in_warning_now and (not in_core_now):
                    if state.get("warning_enter_ts") is None:
                        state["warning_enter_ts"] = ts
                        state["warning_triggered"] = False
                    state["warning_last_seen_ts"] = ts

                    enter_ts = float(state.get("warning_enter_ts") or ts)
                    dwell = ts - enter_ts

                    if (not state.get("warning_triggered")) and dwell >= WARNING_LOITER_SECONDS:
                        # 逗留超过阈值，触发一次 WARNING（并进入冷却）
                        if ts - float(state.get("last_warning_alarm_ts") or -1.0) >= COOLDOWN_SECONDS:
                            alarm_events.append(
                                {
                                    "event_id": str(uuid4()),
                                    "video_id": video_id,
                                    "video_timestamp": ts,
                                    "object_type": obj.get("class"),
                                    "threat_level": "WARNING",
                                    "snapshot_path": None,
                                }
                            )
                            state["last_warning_alarm_ts"] = ts
                        state["warning_triggered"] = True
                else:
                    # 离开 warning（或进入 core）：如果未达到逗留阈值，视为路人，直接清空计时
                    state["warning_enter_ts"] = None
                    state["warning_last_seen_ts"] = None
                    state["warning_triggered"] = False

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