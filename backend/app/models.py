from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import Column, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel


class ThreatLevel(int, Enum):
    CRITICAL = 1
    WARNING = 2


class ObjectType(str, Enum):
    PERSON = "Person"
    VEHICLE = "Vehicle"


class ZoneType(str, Enum):
    WARNING_ZONE = "WarningZone"
    CORE_ZONE = "CoreZone"


class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    @classmethod
    def _missing_(cls, value):
        # 兼容历史库中小写/混合大小写枚举值（如 pending）
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.upper()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class VideoSource(SQLModel, table=True):
    __tablename__ = "video_sources"

    video_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    file_name: str = Field(index=True)
    file_path: str

    duration: float = Field(default=0.0)
    is_active: bool = Field(default=False, index=True)

    upload_time: datetime = Field(default_factory=datetime.utcnow, index=True)

    ext: str = Field(default="", description="文件扩展名, e.g., MP4")
    size: str = Field(default="", description="格式化后的文件大小, e.g., 128 MB")
    is_demo: bool = Field(default=False, index=True, description="是否为演示视频")

    analysis_status: AnalysisStatus = Field(
        default=AnalysisStatus.PENDING,
        sa_column=Column(
            SAEnum(
                AnalysisStatus,
                name="analysisstatus",
                native_enum=False,
                values_callable=lambda enum: [e.value for e in enum],
                validate_strings=False,
            )
        ),
        description="分析状态",
    )
    raw_tracks_path: Optional[str] = Field(default=None, description="原始轨迹JSON文件路径")
    analysis_json_path: Optional[str] = Field(default=None, description="分析结果JSON文件路径")

    alarms: Mapped[List["AlarmEvent"]] = Relationship(
        back_populates="video",
        sa_relationship=relationship("AlarmEvent", back_populates="video"),
    )
    zones: Mapped[List["ZoneConfig"]] = Relationship(
        back_populates="video",
        sa_relationship=relationship("ZoneConfig", back_populates="video"),
    )


class AlarmEvent(SQLModel, table=True):
    __tablename__ = "alarm_events"

    event_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    video_id: UUID = Field(foreign_key="video_sources.video_id", index=True)

    video_timestamp: float = Field(description="报警发生在视频内的时间点（秒或时间戳字符串）")
    object_type: ObjectType = Field(default=ObjectType.PERSON)
    threat_level: ThreatLevel = Field(default=ThreatLevel.WARNING)

    snapshot_path: str

    # 新增：是否已读（用于侧边栏 badge）
    is_read: bool = Field(default=False, index=True)

    video: Mapped[Optional["VideoSource"]] = Relationship(
        back_populates="alarms",
        sa_relationship=relationship("VideoSource", back_populates="alarms"),
    )


class SystemSettings(SQLModel, table=True):
    __tablename__ = "system_settings"

    # 仅一行配置，使用固定主键
    id: int = Field(default=1, primary_key=True)

    current_source_id: Optional[UUID] = Field(default=None, foreign_key="video_sources.video_id", index=True)

    online: bool = Field(default=True)
    fps: int = Field(default=24)
    version: str = Field(default="v0.1.0")


# 配置中心区域表（与视频源外键关联）
class Zone(SQLModel, table=True):
    __tablename__ = "zones"

    id: str = Field(primary_key=True, index=True)

    # 外键：配置中心用的 sourceId 实际是 video_sources.video_id（UUID 字符串）
    source_id: UUID = Field(foreign_key="video_sources.video_id", index=True)

    name: str = Field(default="新建区域")
    type: str = Field(default="core")  # core / warning
    threshold: float = Field(default=3)
    motion: bool = Field(default=True)

    polygon_points: List[List[int]] = Field(sa_column=Column(JSONB), default_factory=list)


class ZoneConfig(SQLModel, table=True):
    __tablename__ = "zone_configs"

    zone_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    video_id: UUID = Field(foreign_key="video_sources.video_id", index=True)

    zone_type: ZoneType = Field(default=ZoneType.CORE_ZONE)

    coordinates: Dict[str, Any] = Field(sa_column=Column(JSONB), default_factory=dict)

    video: Mapped[Optional["VideoSource"]] = Relationship(
        back_populates="zones",
        sa_relationship=relationship("VideoSource", back_populates="zones"),
    )


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str