"""YOLOv8 周界安防验证脚本

用法：
  python model_training/scripts/val.py --weights model_training/weights/yolov8n.pt
  python model_training/scripts/val.py --weights model_training/runs/detect/detect_train/weights/best.pt

说明：
- 默认使用 model_training/data/perim_data.yaml
- 输出 mAP50、mAP50-95 等指标（ultralytics 内置打印 + 返回结果）
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("val")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    logger = _setup_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weights",
        type=str,
        default=str(_project_root() / "model_training" / "runs" / "detect" / "detect_train" / "weights" / "best.pt"),
        help="待验证的权重路径",
    )
    parser.add_argument("--device", type=str, default="0", help="device，例如 0 或 cpu")
    args = parser.parse_args()

    root = _project_root()
    data_yaml = root / "model_training" / "data" / "perim_data.yaml"
    if not data_yaml.exists():
        logger.error("数据集 YAML 不存在：%s", data_yaml)
        return 2

    weights = Path(args.weights)
    if not weights.exists():
        logger.error("权重文件不存在：%s", weights)
        return 3

    try:
        from ultralytics import YOLO

        model = YOLO(str(weights))
        metrics = model.val(data=str(data_yaml), imgsz=640, device=args.device)

        # 兼容不同版本 ultralytics 的 metrics 字段
        # 不同版本返回对象字段可能不同（例如 metrics.map50 / metrics.map 或 metrics.box.map50 等）
        map50 = None
        map5095 = None

        # 1) 新版本常见：metrics.box.map50, metrics.box.map
        box = getattr(metrics, "box", None)
        if box is not None:
            map50 = getattr(box, "map50", None)
            map5095 = getattr(box, "map", None)

        # 2) 旧/其他版本：metrics.map50, metrics.map
        if map50 is None:
        map50 = getattr(metrics, "map50", None)
        if map5095 is None:
        map5095 = getattr(metrics, "map", None)

        # 3) 兜底：把对象转为 dict 再取值（某些版本提供 results_dict）
        if (map50 is None or map5095 is None) and hasattr(metrics, "results_dict"):
            try:
                d = metrics.results_dict
                if isinstance(d, dict):
                    map50 = d.get("metrics/mAP50(B)", map50)
                    map5095 = d.get("metrics/mAP50-95(B)", map5095)
            except Exception:
                pass

        logger.info("验证完成：mAP50=%s, mAP50-95=%s", map50, map5095)
        return 0

    except Exception as e:
        logger.exception("验证失败：%s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
