from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship


class ThreatLevel(int, Enum):
    CRITICAL = 1
    WARNING = 2


class ObjectType(str, Enum):
    PERSON = "Person"
    VEHICLE = "Vehicle"


class ZoneType(str, Enum):
    WARNING_ZONE = "WarningZone"
    CORE_ZONE = "CoreZone"


class VideoSource(SQLModel, table=True):
    __tablename__ = "video_sources"

    video_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    file_name: str = Field(index=True)
    file_path: str

    duration: float = Field(default=0.0)
    is_active: bool = Field(default=False, index=True)

    upload_time: datetime = Field(default_factory=datetime.utcnow, index=True)

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

    video_timestamp: str = Field(description="报警发生在视频内的时间点（秒或时间戳字符串）")
    object_type: ObjectType = Field(default=ObjectType.PERSON)
    threat_level: ThreatLevel = Field(default=ThreatLevel.WARNING)

    snapshot_path: str

    video: Mapped[Optional["VideoSource"]] = Relationship(
        back_populates="alarms",
        sa_relationship=relationship("VideoSource", back_populates="alarms"),
    )


class ZoneConfig(SQLModel, table=True):
    __tablename__ = "zone_configs"

    zone_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    video_id: UUID = Field(foreign_key="video_sources.video_id", index=True)

    zone_type: ZoneType = Field(default=ZoneType.CORE_ZONE)

    # 多边形点集，JSONB 存储：例如 {"points": [[x1,y1],[x2,y2],...]}
    coordinates: Dict[str, Any] = Field(sa_column=Column(JSONB), default_factory=dict)

    video: Mapped[Optional["VideoSource"]] = Relationship(
        back_populates="zones",
        sa_relationship=relationship("VideoSource", back_populates="zones"),
    )
