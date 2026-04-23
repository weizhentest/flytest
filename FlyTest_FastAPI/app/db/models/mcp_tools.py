from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RemoteMCPConfig(Base):
    __tablename__ = "mcp_tools_remotemcpconfig"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(String(2048))
    transport: Mapped[str] = mapped_column(String(50), default="streamable-http")
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    require_hitl: Mapped[bool] = mapped_column(Boolean, default=False)
    hitl_tools: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tools: Mapped[list["MCPTool"]] = relationship(back_populates="mcp_config", lazy="selectin")


class MCPTool(Base):
    __tablename__ = "mcp_tools_mcptool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mcp_config_id: Mapped[int] = mapped_column(ForeignKey("mcp_tools_remotemcpconfig.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    require_hitl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    mcp_config: Mapped[RemoteMCPConfig] = relationship(back_populates="tools", lazy="selectin")
