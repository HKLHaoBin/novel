"""Agent 模块 - 小说生成的智能代理

四大 Agent:
- Designer: 小说架构师，精通雪花写作法、角色弧光理论
- Writer: 小说作家，擅长场景描写、对话设计、情节推进
- Auditor: 逻辑审计师，专注一致性检查和质量控制
- Polisher: 文笔优化师，专注文字润色和风格统一
"""

from .auditor import Auditor, quick_check
from .base import AgentContext, AgentResult, BaseAgent
from .context_builder import (
    build_full_context,
    build_quick_reference,
    build_uncertainty_guidance,
)
from .designer import Designer
from .human_loop import EditMode, HumanLoopManager, InteractionResult
from .polisher import Polisher, quick_polish
from .prompt_loader import (
    get_agent_info,
    get_system_prompt,
    list_available_prompts,
    load_prompt_template,
    prompt_library,
)
from .tools import (
    Tool,
    ToolResult,
    ToolType,
    add_event,
    build_tools_description,
    check_consistency,
    get_all_tools,
    query_character,
    query_events,
    query_location,
    query_relationships,
    query_timeline,
    suggest_next,
    update_character,
    update_location,
)
from .writer import Writer

__all__ = [
    # Base
    "AgentContext",
    "AgentResult",
    "Auditor",
    "BaseAgent",
    # Agents
    "Designer",
    # Human Loop
    "EditMode",
    "HumanLoopManager",
    "InteractionResult",
    "Polisher",
    # Tools
    "Tool",
    "ToolResult",
    "ToolType",
    "Writer",
    "add_event",
    # Context
    "build_full_context",
    "build_quick_reference",
    "build_tools_description",
    "build_uncertainty_guidance",
    "check_consistency",
    "get_agent_info",
    "get_all_tools",
    "get_system_prompt",
    "list_available_prompts",
    "load_prompt_template",
    # Prompt Loader
    "prompt_library",
    "query_character",
    "query_events",
    "query_location",
    "query_relationships",
    "query_timeline",
    # Quick methods
    "quick_check",
    "quick_polish",
    "suggest_next",
    "update_character",
    "update_location",
]
