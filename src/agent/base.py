"""Agent 基类和数据结构"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.core import CharacterCard, Graph, Timeline, WorldMap


class LLMProviderProtocol(Protocol):
    """LLM 提供者协议"""

    model: str

    def get_raw_provider(self) -> Any: ...

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs,
    ) -> str: ...


class KnowledgeBaseProtocol(Protocol):
    """知识库协议"""

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]: ...

    async def add_content(
        self, content: str, content_type: str = "", metadata: dict | None = None
    ) -> None: ...


@dataclass
class AgentContext:
    """Agent 执行上下文"""

    # 核心数据结构
    graph: Graph | None = None
    timeline: Timeline | None = None
    world_map: WorldMap | None = None
    characters: dict[str, CharacterCard] = field(default_factory=dict)

    # 当前状态
    current_point_id: str | None = None
    user_input: str = ""

    # 额外信息
    extra: dict[str, Any] = field(default_factory=dict)

    # LLM 和知识库（新增）
    llm: LLMProviderProtocol | None = None
    knowledge: KnowledgeBaseProtocol | None = None


@dataclass
class AgentResult:
    """Agent 执行结果"""

    success: bool = True
    content: str = ""

    # 要添加的数据
    nodes_to_add: list[Any] = field(default_factory=list)
    edges_to_add: list[Any] = field(default_factory=list)
    timepoints_to_add: list[Any] = field(default_factory=list)

    # 章节信息
    chapter_num: int = 0
    chapter_title: str = ""

    # 审计相关
    issues: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    # 额外信息
    extra: dict[str, Any] = field(default_factory=dict)

    # 错误信息
    error: str = ""

    def has_issues(self) -> bool:
        """是否有问题"""
        return len(self.issues) > 0

    def get_severe_issues(self) -> list[dict]:
        """获取严重问题"""
        return [i for i in self.issues if i.get("severity") == "severe"]

    def get_medium_issues(self) -> list[dict]:
        """获取中等问题"""
        return [i for i in self.issues if i.get("severity") == "medium"]


class BaseAgent:
    """Agent 基类"""

    name: str = "base_agent"
    description: str = "基础 Agent"

    def __init__(self, llm: LLMProviderProtocol | None = None):
        """
        初始化 Agent

        Args:
            llm: LLM 提供者
        """
        self.llm = llm

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行 Agent 任务

        Args:
            context: 执行上下文

        Returns:
            执行结果
        """
        raise NotImplementedError("子类必须实现 execute 方法")

    async def _call_llm(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """
        调用 LLM

        Args:
            prompt: 提示词
            system: 系统提示
            temperature: 温度
            max_tokens: 最大 token

        Returns:
            LLM 响应
        """
        if not self.llm:
            raise RuntimeError(f"Agent {self.name} 未配置 LLM 提供者")

        return await self.llm.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _retrieve_knowledge(self, query: str, top_k: int = 5) -> list[dict]:
        """
        从知识库检索

        Args:
            query: 查询
            top_k: 返回数量

        Returns:
            检索结果
        """
        if not self.llm or not hasattr(self, "_context"):
            return []

        if hasattr(self._context, "knowledge") and self._context.knowledge:
            return await self._context.knowledge.retrieve(query, top_k)  # type: ignore[no-any-return]

        return []

    def set_llm(self, llm: LLMProviderProtocol) -> None:
        """设置 LLM 提供者"""
        self.llm = llm

    def get_prompt(self, context: AgentContext) -> str:
        """
        获取提示词（子类可重写）

        Args:
            context: 执行上下文

        Returns:
            提示词
        """
        return ""
