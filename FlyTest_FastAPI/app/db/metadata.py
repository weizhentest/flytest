"""Import SQLAlchemy models here so Alembic can discover metadata."""

from app.db.base import Base
from app.db.models import api_keys as _api_key_models  # noqa: F401
from app.db.models import auth as _auth_models  # noqa: F401
from app.db.models import knowledge as _knowledge_models  # noqa: F401
from app.db.models import mcp_tools as _mcp_tools_models  # noqa: F401
from app.db.models import orchestrator as _orchestrator_models  # noqa: F401
from app.db.models import projects as _project_models  # noqa: F401
from app.db.models import prompts as _prompt_models  # noqa: F401
from app.db.models import requirements as _requirements_models  # noqa: F401
from app.db.models import skills as _skills_models  # noqa: F401
from app.db.models import testcase_templates as _testcase_template_models  # noqa: F401

__all__ = ["Base"]
