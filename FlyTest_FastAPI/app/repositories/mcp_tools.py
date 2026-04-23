from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.mcp_tools import MCPTool, RemoteMCPConfig
from app.repositories.base import Repository


class MCPToolsRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_remote_configs(self) -> list[RemoteMCPConfig]:
        stmt = (
            select(RemoteMCPConfig)
            .options(selectinload(RemoteMCPConfig.tools))
            .order_by(RemoteMCPConfig.created_at.desc(), RemoteMCPConfig.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_remote_config(self, *, config_id: int) -> RemoteMCPConfig | None:
        stmt = (
            select(RemoteMCPConfig)
            .where(RemoteMCPConfig.id == config_id)
            .options(selectinload(RemoteMCPConfig.tools))
        )
        return self.db.scalar(stmt)

    def create_remote_config(self, item: RemoteMCPConfig) -> RemoteMCPConfig:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def delete_remote_config(self, item: RemoteMCPConfig) -> None:
        for tool in list(item.tools or []):
            self.db.delete(tool)
        self.db.delete(item)
        self.db.flush()

    def list_remote_tools(self, *, config_id: int) -> list[MCPTool]:
        stmt = (
            select(MCPTool)
            .where(MCPTool.mcp_config_id == config_id)
            .options(selectinload(MCPTool.mcp_config))
            .order_by(MCPTool.name.asc(), MCPTool.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_remote_tool(self, *, config_id: int, name: str) -> MCPTool | None:
        stmt = (
            select(MCPTool)
            .where(MCPTool.mcp_config_id == config_id, MCPTool.name == name)
            .options(selectinload(MCPTool.mcp_config))
        )
        return self.db.scalar(stmt)

    def create_remote_tool(self, item: MCPTool) -> MCPTool:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def delete_remote_tool(self, item: MCPTool) -> None:
        self.db.delete(item)
        self.db.flush()
