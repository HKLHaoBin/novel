"""Agent 模块 - 小说生成的智能代理

四大 Agent:
- Designer: 小说架构师，精通雪花写作法、角色弧光理论
- Writer: 小说作家，擅长场景描写、对话设计、情节推进
- Auditor: 逻辑审计师，专注一致性检查和质量控制
- Polisher: 文笔优化师，专注文字润色和风格统一
"""

from .base import AgentContext, AgentResult, BaseAgent
from .context_builder import (
    build_full_context,
    build_quick_reference,
    build_uncertainty_guidance,
)
from .designer import Designer
from .writer import Writer
from .auditor import Auditor, quick_check
from .polisher import Polisher, quick_polish
from .tools import (
    Tool,
    ToolResult,
    ToolType,
    get_all_tools,
    build_tools_description,
    query_character,
    query_location,
    query_timeline,
    query_events,
    query_relationships,
    update_character,
    update_location,
    add_event,
    check_consistency,
    suggest_next,
)
from .prompt_loader import (
    prompt_library,
    load_prompt_template,
    get_system_prompt,
    get_agent_info,
    list_available_prompts,
)

__all__ = [
    # Base
    "AgentContext", "AgentResult", "BaseAgent",
    
    # Agents
    "Designer", "Writer", "Auditor", "Polisher",
    
    # Context
    "build_full_context", "build_quick_reference", "build_uncertainty_guidance",
    
    # Tools
    "Tool", "ToolResult", "ToolType",
    "get_all_tools", "build_tools_description",
    "query_character", "query_location", "query_timeline",
    "query_events", "query_relationships",
    "update_character", "update_location", "add_event",
    "check_consistency", "suggest_next",
    
    # Prompt Loader
    "prompt_library", "load_prompt_template",
    "get_system_prompt", "get_agent_info", "list_available_prompts",
    
    # Quick methods
    "quick_check", "quick_polish",
]