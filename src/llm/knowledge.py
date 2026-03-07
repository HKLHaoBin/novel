"""知识库管理器 - 封装 superficial-thinking 库用于小说生成"""

from typing import Any

# superficial-thinking 库的导入
try:
    from dawn_shuttle.dawn_shuttle_superficial_thinking import (
        MemoryConfig,
        MemoryManager,
    )
    from dawn_shuttle.dawn_shuttle_superficial_thinking import (
        initialize as memory_initialize,
    )

    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False


class KnowledgeBase:
    """小说知识库 - 用于存储和检索小说相关内容"""

    def __init__(
        self,
        db_path: str = "./novel_memory.db",
        max_messages: int = 50,
        max_nodes: int = 200,
    ):
        """
        初始化知识库

        Args:
            db_path: 数据库路径
            max_messages: 工作记忆最大消息数
            max_nodes: 模糊记忆最大节点数
        """
        if not MEMORY_AVAILABLE:
            raise ImportError(
                "superficial-thinking 库未安装，"
                "请确保 dawn_shuttle_superficial_thinking 可用"
            )

        self.db_path = db_path
        self.config = MemoryConfig(
            db_path=db_path,
            working_max_messages=max_messages,
            fuzzy_max_nodes=max_nodes,
            retrieval_top_k=10,
            retrieval_threshold=0.2,
        )
        self._memory: MemoryManager | None = None
        self._llm_provider = None

    async def initialize(
        self, llm_provider, system_prompt: str = ""
    ) -> "KnowledgeBase":
        """
        初始化知识库

        Args:
            llm_provider: LLM 提供者（LLMProvider 实例或 intelligence provider）
            system_prompt: 系统提示词（人设）
        """
        # 获取底层 provider
        if hasattr(llm_provider, "get_raw_provider"):
            self._llm_provider = llm_provider.get_raw_provider()
        else:
            self._llm_provider = llm_provider

        # 默认系统提示词
        if not system_prompt:
            system_prompt = """
你是一个小说创作助手，负责记住小说的各种设定和情节。
你需要记住：
- 角色的设定、性格、能力、关系
- 世界观的规则和背景
- 情节的发展和转折
- 伏笔和揭示
- 时间线和地点信息
"""

        self._memory = await memory_initialize(
            llm=self._llm_provider,
            system_prompt=system_prompt,
            config=self.config,
        )

        return self

    async def add_content(
        self,
        content: str,
        content_type: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        添加内容到知识库

        Args:
            content: 内容文本
            content_type: 内容类型
            metadata: 元数据
        """
        if not self._memory:
            raise RuntimeError("知识库未初始化，请先调用 initialize()")

        # 构建带类型标记的内容
        marked_content = f"[{content_type}] {content}"

        await self._memory.add_message(
            role="user",
            content=marked_content,
        )

        # 如果有元数据，也添加进去
        if metadata:
            meta_str = " | ".join(f"{k}: {v}" for k, v in metadata.items())
            await self._memory.add_message(
                role="assistant",
                content=f"已记录: {meta_str}",
            )

    async def add_chapter_summary(
        self,
        chapter_num: int,
        title: str,
        summary: str,
        key_events: list[str] | None = None,
        characters: list[str] | None = None,
    ) -> None:
        """
        添加章节摘要

        Args:
            chapter_num: 章节号
            title: 章节标题
            summary: 摘要内容
            key_events: 关键事件
            characters: 涉及角色
        """
        content_parts = [f"第{chapter_num}章《{title}》摘要：{summary}"]

        if key_events:
            content_parts.append(f"关键事件：{', '.join(key_events)}")

        if characters:
            content_parts.append(f"涉及角色：{', '.join(characters)}")

        await self.add_content(
            content="\n".join(content_parts),
            content_type="chapter",
            metadata={"chapter": chapter_num, "title": title},
        )

    async def add_character_info(
        self,
        name: str,
        info_type: str,
        content: str,
    ) -> None:
        """
        添加角色信息

        Args:
            name: 角色名
            info_type: 信息类型
            content: 内容
        """
        await self.add_content(
            content=f"角色【{name}】{info_type}：{content}",
            content_type="character",
            metadata={"character": name, "info_type": info_type},
        )

    async def add_world_setting(
        self,
        category: str,
        content: str,
    ) -> None:
        """
        添加世界观设定

        Args:
            category: 类别
            content: 内容
        """
        await self.add_content(
            content=f"世界观【{category}】：{content}",
            content_type="world",
            metadata={"category": category},
        )

    async def add_plot_point(
        self,
        plot_type: str,
        content: str,
        related_characters: list[str] | None = None,
    ) -> None:
        """
        添加情节点

        Args:
            plot_type: 类型
            content: 内容
            related_characters: 相关角色
        """
        content_parts = [f"情节【{plot_type}】：{content}"]

        if related_characters:
            content_parts.append(f"相关角色：{', '.join(related_characters)}")

        await self.add_content(
            content="\n".join(content_parts),
            content_type="plot",
            metadata={"plot_type": plot_type},
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        检索相关内容

        Args:
            query: 查询字符串
            top_k: 返回数量

        Returns:
            相关内容列表
        """
        if not self._memory:
            raise RuntimeError("知识库未初始化，请先调用 initialize()")

        result = await self._memory.retrieve(query)

        memories = []

        # 添加模糊记忆
        for mem in result.fuzzy_memories[:top_k]:
            memories.append(
                {
                    "type": "fuzzy",
                    "summary": mem.summary,
                    "keywords": mem.keywords.primary
                    if hasattr(mem, "keywords")
                    else [],
                    "importance": mem.importance,
                    "timestamp": str(mem.timestamp),
                }
            )

        # 添加精准记忆
        for mem in result.precise_memories[:top_k]:
            memories.append(
                {
                    "type": "precise",
                    "content": mem.content,
                    "importance": mem.importance,
                    "timestamp": str(mem.timestamp),
                }
            )

        return memories

    async def query(self, question: str) -> str:
        """
        查询知识库（带 LLM 汇总）

        Args:
            question: 问题

        Returns:
            汇总后的回答
        """
        if not self._memory:
            raise RuntimeError("知识库未初始化，请先调用 initialize()")

        # 使用 query_memory 方法（会调用 LLM 进行意图分析和结果汇总）
        return await self._memory.query_memory(question)  # type: ignore[no-any-return]

    def get_context(self, include_fuzzy: bool = True) -> list[dict]:
        """
        获取当前上下文

        Args:
            include_fuzzy: 是否包含模糊记忆

        Returns:
            消息列表
        """
        if not self._memory:
            return []

        return self._memory.get_context(include_fuzzy=include_fuzzy)  # type: ignore[no-any-return]

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self._memory:
            return {"status": "not_initialized"}

        return self._memory.get_stats()  # type: ignore[no-any-return]

    async def close(self) -> None:
        """关闭知识库"""
        if self._memory:
            await self._memory.close()
            self._memory = None

    async def clear(self) -> None:
        """清空知识库"""
        if self._memory:
            await self.close()
            # 删除数据库文件
            import os

            if os.path.exists(self.db_path):
                os.remove(self.db_path)

    async def restore_from_snapshot(
        self,
        global_summary: str = "",
        characters_data: dict | None = None,
        timeline_data: dict | None = None,
        world_map_data: dict | None = None,
        graph_data: dict | None = None,
    ) -> None:
        """
        从 snapshot 恢复数据到知识库

        Args:
            global_summary: 小说设计大纲
            characters_data: 角色数据
            timeline_data: 时间线数据
            world_map_data: 世界地图数据
            graph_data: 图结构数据
        """
        if not self._memory:
            raise RuntimeError("知识库未初始化，请先调用 initialize()")

        # 恢复设计大纲
        if global_summary:
            await self.add_content(
                content=f"小说设计大纲：\n{global_summary}",
                content_type="design",
                metadata={"type": "global_summary"},
            )

        # 恢复角色数据
        if characters_data:
            for char_name, char_info in characters_data.items():
                if isinstance(char_info, dict):
                    info_str = "\n".join(
                        f"  - {k}: {v}" for k, v in char_info.items()
                    )
                    await self.add_character_info(
                        name=char_name,
                        info_type="设定",
                        content=info_str,
                    )

        # 恢复时间线数据
        if timeline_data:
            events = timeline_data.get("events", [])
            for event in events:
                if isinstance(event, dict):
                    await self.add_content(
                        content=f"时间线事件：{event.get('description', str(event))}",
                        content_type="timeline",
                        metadata=event,
                    )

        # 恢复世界地图数据
        if world_map_data:
            locations = world_map_data.get("locations", [])
            for loc in locations:
                if isinstance(loc, dict):
                    loc_name = loc.get("name", "未知地点")
                    loc_desc = loc.get("description", "")
                    await self.add_world_setting(
                        category=f"地点-{loc_name}",
                        content=loc_desc,
                    )

        # 恢复图结构数据（情节节点等）
        if graph_data:
            nodes = graph_data.get("nodes", [])
            for node in nodes:
                if isinstance(node, dict):
                    node_type = node.get("type", "unknown")
                    attrs = node.get("attrs", {})
                    if node_type in ["main_plot", "sub_plot"]:
                        await self.add_plot_point(
                            plot_type=node_type,
                            content=attrs.get("description", str(attrs)),
                            related_characters=attrs.get("characters", []),
                        )


async def create_knowledge_base(
    llm_provider,
    db_path: str = "./novel_memory.db",
    system_prompt: str = "",
) -> KnowledgeBase:
    """
    创建并初始化知识库

    Args:
        llm_provider: LLM 提供者
        db_path: 数据库路径
        system_prompt: 系统提示词

    Returns:
        初始化后的 KnowledgeBase
    """
    kb = KnowledgeBase(db_path=db_path)
    await kb.initialize(llm_provider, system_prompt)
    return kb
