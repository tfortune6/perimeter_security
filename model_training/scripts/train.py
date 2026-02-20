"""YOLOv8 周界安防微调训练脚本（面向 RTX 3060 6GB 优化）

目标：person / vehicle 两类检测精度提升。

用法（建议在项目根目录执行）：
  python model_training/scripts/train.py

数据集：model_training/data/perim_data.yaml
权重：model_training/weights/yolov8n.pt（不存在则自动下载）

训练完成后：
- 自动复制 best.pt 到 backend/app/models/yolov8n_perim_best.pt（便于后端推理加载）

说明：
- 本脚本使用 ultralytics.YOLO 训练，日志会实时打印训练过程。
- 额外增加一个轻量的 mAP 轮询打印：每隔 N 秒读取 runs/detect/train/results.csv（若存在）。
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Optional


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("train")
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
    # scripts/train.py -> scripts -> model_training -> project root
    return Path(__file__).resolve().parents[2]


def _weights_dir() -> Path:
    return _project_root() / "model_training" / "weights"


def _dataset_yaml() -> Path:
    return _project_root() / "model_training" / "data" / "perim_data.yaml"


def _backend_models_dir() -> Path:
    return _project_root() / "backend" / "app" / "models"


def _download_base_weights_if_needed(logger: logging.Logger, weights_path: Path) -> None:
    """如果 yolov8n.pt 不存在，则使用 ultralytics 的下载能力拉取。"""
    if weights_path.exists():
        logger.info("发现预训练权重：%s", weights_path)
        return

    logger.warning("未发现预训练权重：%s，将尝试自动下载 yolov8n.pt...", weights_path)
    weights_path.parent.mkdir(parents=True, exist_ok=True)

    # Ultralytics 在 YOLO('yolov8n.pt') 时会自动下载到其缓存目录；
    # 我们这里下载后再复制到 model_training/weights 以形成项目自包含。
    from ultralytics import YOLO

    tmp = YOLO("yolov8n.pt")  # 触发下载
    src = Path(tmp.ckpt_path) if hasattr(tmp, "ckpt_path") else None

    # 更稳妥：直接在 ultralytics 缓存里找
    if src is None or (not src.exists()):
        # 常见缓存位置：~/.config/Ultralytics/ 或 ~/.cache/ultralytics/，不同平台略有差异。
        # 这里不强依赖具体路径：如果 YOLO 初始化成功，权重一定已经可用；直接用字符串即可训练。
        logger.warning("未能定位到下载后的本地权重路径，将直接在训练时使用 'yolov8n.pt' 引用。")
        return

    shutil.copy2(src, weights_path)
    logger.info("已下载并复制预训练权重到：%s", weights_path)


def _tail_results_csv(results_csv: Path, last_pos: int, logger: logging.Logger) -> int:
    """轮询读取 results.csv，尽量打印当前 epoch 的 loss / mAP 指标。"""
    if not results_csv.exists():
        return last_pos

    try:
        with results_csv.open("r", encoding="utf-8") as f:
            f.seek(last_pos)
            new = f.read()
            new_pos = f.tell()

        if not new.strip():
            return new_pos

        lines = [ln.strip() for ln in new.splitlines() if ln.strip()]
        # results.csv 最后一行通常是最新 epoch
        last = lines[-1]
        # 直接打印整行，避免强绑定列名版本差异
        logger.info("[results.csv] %s", last)
        return new_pos
    except Exception as e:
        logger.warning("读取 results.csv 失败：%s", e)
        return last_pos


def _monitor_training_runs(logger: logging.Logger, runs_dir: Path, stop_flag_path: Path, poll_sec: float = 10.0) -> None:
    """在训练过程中轮询输出 loss/mAP（从 results.csv）。

    说明：ultralytics 的训练日志本身会输出每个 epoch 的指标；
    这里额外做一个兜底，确保你在某些终端/日志采集场景下也能持续看到关键指标。
    """

    last_pos = 0
    # Ultralytics 默认：runs/detect/train/results.csv
    results_csv = runs_dir / "detect" / "train" / "results.csv"

    while True:
        if stop_flag_path.exists():
            return
        last_pos = _tail_results_csv(results_csv, last_pos, logger)
        time.sleep(poll_sec)


def main() -> int:
    logger = _setup_logger()

    root = _project_root()
    logger.info("Project root: %s", root)

    dataset_yaml = _dataset_yaml()
    if not dataset_yaml.exists():
        logger.error("数据集 YAML 不存在：%s", dataset_yaml)
        return 2

    weights_path = _weights_dir() / "yolov8n.pt"

    try:
        _download_base_weights_if_needed(logger, weights_path)
    except Exception as e:
        logger.exception("下载/准备预训练权重失败：%s", e)
        return 3

    # 续训模式：针对刚才中断的微调任务进行续训
    refine_last = root / "model_training" / "runs" / "detect" / "detect_refine_neg" / "weights" / "last.pt"
    
    if refine_last.exists():
        base_weights = str(refine_last)
        logger.info("发现中断的微调任务，将从 last.pt 续训：%s", base_weights)
        # 续训时，epochs 会自动沿用之前设定的总数（20），resume=True 会处理剩余轮数
        train_args = dict(
            model=base_weights,
            resume=True,
            workers=4,  # 降低 workers 减少内存/虚拟内存压力
        )
    else:
        # 如果找不到 last.pt，则按普通微调逻辑走（加载 best.pt）
        prev_best = root / "model_training" / "runs" / "detect" / "detect_train" / "weights" / "best.pt"
        base_weights = str(prev_best) if prev_best.exists() else "yolov8n.pt"
        
        train_args = dict(
            data=str(dataset_yaml),
            epochs=20,
            imgsz=640,
            device=0,
            amp=True,
            batch=16,
            workers=4,  # 降低 workers 减少内存/虚拟内存压力
            plots=True,
            project=str(root / "model_training" / "runs"),
            name="detect_refine_neg",
            exist_ok=True,
            verbose=True,
        )

    logger.info("训练参数：%s", train_args)

    # 启动训练（Ultralytics 内部会实时打印每个 epoch 的 box/cls/dfl loss 与 mAP 等指标）
    try:
        from ultralytics import YOLO

        model = YOLO(base_weights)

        # 训练过程监控：轮询 results.csv（在某些环境下更容易抓关键指标）
        runs_dir = Path(train_args["project"])
        stop_flag = runs_dir / ".stop_monitor"

        import threading

        monitor_thread = threading.Thread(
            target=_monitor_training_runs,
            kwargs=dict(logger=logger, runs_dir=runs_dir, stop_flag_path=stop_flag, poll_sec=10.0),
            daemon=True,
        )
        monitor_thread.start()

        results = model.train(**train_args)

        # 停止监控线程
        try:
            stop_flag.write_text("done", encoding="utf-8")
        except Exception:
            pass

        logger.info("训练完成。ultralytics results: %s", results)

    except Exception as e:
        logger.exception("训练失败：%s", e)
        return 4

    # 训练输出权重路径（根据我们指定的 project/name）
    best_pt = root / "model_training" / "runs" / "detect" / "detect_train" / "weights" / "best.pt"
    if not best_pt.exists():
        # 兼容 ultralytics 可能的目录结构差异
        alt = list((root / "model_training" / "runs").rglob("best.pt"))
        if alt:
            best_pt = alt[0]

    if not best_pt.exists():
        logger.error("未找到 best.pt，无法部署。请检查 runs 输出目录。")
        return 5

    dest_dir = _backend_models_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "yolov8n_perim_best.pt"

    try:
        shutil.copy2(best_pt, dest_path)
        logger.info("已部署 best.pt 到后端模型目录：%s", dest_path)
    except Exception as e:
        logger.exception("复制 best.pt 失败：%s", e)
        return 6

    logger.info("全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
