"""小说生成器

一个完整的 AI 小说生成系统

核心模块：
- core: 核心数据结构（图、时间轴、地图、角色卡、状态管理）
- agent: AI 代理（设计师、作家、审计师、优化师）
- llm: LLM 适配层（intelligence 和 superficial-thinking 的封装）
"""

from src.core import (
    Graph, Node, NodeType, Edge, EdgeType,
    TimePoint, Timeline,
    Location, LocationType, LocationEdge, LocationRelation, WorldMap,
    CharacterCard, Ability,
    NovelContext, NovelCoordinator,
    NovelSnapshot, NovelStateManager, GenerationPhase,
)

from src.agent import (
    AgentContext, AgentResult, BaseAgent,
    Designer, Writer, Auditor, Polisher,
    query_character, query_location, query_timeline,
)

from src.llm import (
    LLMProvider, create_provider,
    KnowledgeBase, create_knowledge_base,
)

from src.generator import NovelGenerator, create_generator

__all__ = [
    # Core
    "Graph", "Node", "NodeType", "Edge", "EdgeType",
    "TimePoint", "Timeline",
    "Location", "LocationType", "LocationEdge", "LocationRelation", "WorldMap",
    "CharacterCard", "Ability",
    "NovelContext", "NovelCoordinator",
    "NovelSnapshot", "NovelStateManager", "GenerationPhase",
    
    # Agent
    "AgentContext", "AgentResult", "BaseAgent",
    "Designer", "Writer", "Auditor", "Polisher",
    "query_character", "query_location", "query_timeline",
    
    # LLM
    "LLMProvider", "create_provider",
    "KnowledgeBase", "create_knowledge_base",
    
    # Generator
    "NovelGenerator", "create_generator",
]