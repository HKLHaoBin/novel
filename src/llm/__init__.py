"""LLM 模块 - 封装 intelligence 和 superficial-thinking 库"""

from .provider import (
    LLMProvider,
    create_provider,
    INTELLIGENCE_AVAILABLE,
)

from .knowledge import (
    KnowledgeBase,
    create_knowledge_base,
    MEMORY_AVAILABLE,
)

__all__ = [
    # Provider
    "LLMProvider",
    "create_provider",
    "INTELLIGENCE_AVAILABLE",
    
    # Knowledge
    "KnowledgeBase", 
    "create_knowledge_base",
    "MEMORY_AVAILABLE",
]
