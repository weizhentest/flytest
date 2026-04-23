from fastapi import APIRouter

from app.api.v1.api_automation import router as api_automation_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.meta import router as meta_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.langgraph import router as langgraph_router
from app.api.v1.mcp_tools import router as mcp_tools_router
from app.api.v1.orchestrator import router as orchestrator_router
from app.api.v1.projects import router as projects_router
from app.api.v1.prompts import router as prompts_router
from app.api.v1.requirements import router as requirements_router
from app.api.v1.skills import router as skills_router
from app.api.v1.testcase_templates import router as testcase_templates_router
from app.api.v1.testcases import router as testcases_router
from app.api.v1.token import router as token_router
from app.api.v1.ui_automation import router as ui_automation_router


router = APIRouter(prefix="/api")
router.include_router(meta_router)
router.include_router(token_router)
router.include_router(accounts_router)
router.include_router(projects_router)
router.include_router(knowledge_router)
router.include_router(langgraph_router)
router.include_router(orchestrator_router)
router.include_router(requirements_router)
router.include_router(prompts_router)
router.include_router(api_keys_router)
router.include_router(skills_router)
router.include_router(testcase_templates_router)
router.include_router(testcases_router)
router.include_router(ui_automation_router)
router.include_router(api_automation_router)
router.include_router(mcp_tools_router)
