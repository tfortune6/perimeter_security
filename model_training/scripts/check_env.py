"""环境检查脚本（RTX 3060 优化训练前置检查）

用法：
  python model_training/scripts/check_env.py

检查项：
- Python / torch / torchvision 版本
- CUDA 是否可用
- GPU 型号（期望 RTX 3060）
- 显存总量/已分配/已保留
"""

from __future__ import annotations

import logging
import platform
import sys


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("check_env")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # 避免重复添加 handler
    if not logger.handlers:
        logger.addHandler(handler)

    return logger


def _bytes_to_gib(x: int) -> float:
    return float(x) / 1024 / 1024 / 1024


def main() -> int:
    logger = _setup_logger()

    logger.info("===== 系统环境 =====")
    logger.info("OS: %s", platform.platform())
    logger.info("Python: %s", sys.version.replace("\n", " "))

    try:
        import torch

        logger.info("torch: %s", getattr(torch, "__version__", "unknown"))
        logger.info("torch.cuda.is_available(): %s", torch.cuda.is_available())
        logger.info("torch.version.cuda: %s", getattr(torch.version, "cuda", None))

        try:
            import torchvision

            logger.info("torchvision: %s", getattr(torchvision, "__version__", "unknown"))
        except Exception as e:
            logger.warning("torchvision 导入失败: %s", e)

        if torch.cuda.is_available():
            device_id = 0
            name = torch.cuda.get_device_name(device_id)
            props = torch.cuda.get_device_properties(device_id)

            total = props.total_memory
            allocated = torch.cuda.memory_allocated(device_id)
            reserved = torch.cuda.memory_reserved(device_id)

            logger.info("===== CUDA / GPU 信息 =====")
            logger.info("GPU[0] Name: %s", name)
            logger.info("Compute Capability: %s.%s", props.major, props.minor)
            logger.info("Total VRAM: %.2f GiB", _bytes_to_gib(total))
            logger.info("Allocated: %.2f GiB", _bytes_to_gib(allocated))
            logger.info("Reserved: %.2f GiB", _bytes_to_gib(reserved))

            if "3060" in name:
                logger.info("检测到 RTX 3060（或包含 3060 字样的 GPU），符合预期。")
            else:
                logger.warning("未检测到 RTX 3060：当前 GPU=%s（仍可训练，但参数可能需调整）", name)
        else:
            logger.error("CUDA 不可用：将无法使用 RTX 3060 加速。请检查 NVIDIA 驱动 / CUDA / torch 安装。")
            return 2

    except Exception as e:
        logger.exception("torch 导入或 CUDA 检查失败：%s", e)
        return 1

    logger.info("环境检查完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
