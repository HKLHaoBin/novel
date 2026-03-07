"""小说生成器

一个完整的 AI 小说生成系统

核心模块：
- core: 核心数据结构（图、时间轴、地图、角色卡、状态管理）
- agent: AI 代理（设计师、作家、审计师、优化师）
- llm: LLM 适配层（intelligence 和 superficial-thinking 的封装）
"""

from src.agent import (
    AgentContext,
    AgentResult,
    Auditor,
    BaseAgent,
    Designer,
    Polisher,
    Writer,
    query_character,
    query_location,
    query_timeline,
)
from src.core import (
    Ability,
    CharacterCard,
    Edge,
    EdgeType,
    GenerationPhase,
    Graph,
    Location,
    LocationEdge,
    LocationRelation,
    LocationType,
    Node,
    NodeType,
    NovelContext,
    NovelCoordinator,
    NovelSnapshot,
    NovelStateManager,
    Timeline,
    TimePoint,
    WorldMap,
)
from src.generator import NovelGenerator, create_generator
from src.llm import (
    KnowledgeBase,
    LLMProvider,
    create_knowledge_base,
    create_provider,
)

__all__ = [
    "Ability",
    # Agent
    "AgentContext",
    "AgentResult",
    "Auditor",
    "BaseAgent",
    "CharacterCard",
    "Designer",
    "Edge",
    "EdgeType",
    "GenerationPhase",
    # Core
    "Graph",
    "KnowledgeBase",
    # LLM
    "LLMProvider",
    "Location",
    "LocationEdge",
    "LocationRelation",
    "LocationType",
    "Node",
    "NodeType",
    "NovelContext",
    "NovelCoordinator",
    # Generator
    "NovelGenerator",
    "NovelSnapshot",
    "NovelStateManager",
    "Polisher",
    "TimePoint",
    "Timeline",
    "WorldMap",
    "Writer",
    "create_generator",
    "create_knowledge_base",
    "create_provider",
    "query_character",
    "query_location",
    "query_timeline",
]
