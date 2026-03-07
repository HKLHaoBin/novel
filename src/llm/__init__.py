"""LLM 模块 - 封装 intelligence 和 superficial-thinking 库"""

from .knowledge import (
    MEMORY_AVAILABLE,
    KnowledgeBase,
    create_knowledge_base,
)
from .provider import (
    INTELLIGENCE_AVAILABLE,
    LLMProvider,
    create_provider,
)

__all__ = [
    "INTELLIGENCE_AVAILABLE",
    "MEMORY_AVAILABLE",
    # Knowledge
    "KnowledgeBase",
    # Provider
    "LLMProvider",
    "create_knowledge_base",
    "create_provider",
]
