"""小说生成器 - 主流程编排

整合所有模块，实现完整的小说生成流程：
1. 设计阶段 - Designer
2. 写作阶段 - Writer
3. 审计阶段 - Auditor
4. 润色阶段 - Polisher
"""

from collections.abc import Callable
from pathlib import Path

from src.agent import AgentContext, AgentResult, Auditor, Designer, Polisher, Writer
from src.core import NovelContext, NovelCoordinator
from src.llm import KnowledgeBase, LLMProvider, create_knowledge_base


class NovelGenerator:
    """小说生成器"""

    def __init__(
        self,
        llm_config: dict,
        save_dir: str = "./novels",
        knowledge_db: str | None = None,  # 已废弃，每个小说使用独立知识库
    ):
        """
        初始化生成器

        Args:
            llm_config: LLM 配置
                {
                    "type": "deepseek",
                    "api_key": "sk-...",
                    "model": "deepseek-chat"
                }
            save_dir: 小说保存目录
            knowledge_db: 已废弃，每个小说使用独立知识库
        """
        # 初始化 LLM
        self.llm = LLMProvider(
            provider_type=llm_config.get("type", "deepseek"),
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", ""),
            model=llm_config.get("model", ""),
        )

        # 初始化协调器
        self.coordinator = NovelCoordinator(save_dir=save_dir)
        self.save_dir = save_dir

        # 知识库（每个小说独立）
        self.knowledge: KnowledgeBase | None = None

        # 初始化 Agents
        self.designer = Designer(llm=self.llm)
        self.writer = Writer(llm=self.llm)
        self.auditor = Auditor(llm=self.llm)
        self.polisher = Polisher(llm=self.llm)

        # 当前小说上下文
        self.novel_ctx: NovelContext | None = None

        # 回调函数
        self._on_progress: Callable[[str, str], None] | None = None
        self._on_chapter_complete: Callable[[int, str], None] | None = None

    def _get_knowledge_db_path(self, title: str) -> str:
        """获取小说专属的知识库路径"""
        safe_title = self._sanitize_title(title)
        novel_dir = Path(self.save_dir) / safe_title
        novel_dir.mkdir(parents=True, exist_ok=True)
        return str(novel_dir / "knowledge.db")

    def _sanitize_title(self, title: str) -> str:
        """清理标题中的非法字符"""
        import re

        # 移除或替换文件系统不允许的字符
        # Windows 不允许: < > : " / \ | ? *
        # Unix 不允许: / 和空字符
        safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title)
        # 移除首尾空格和点（Windows不允许结尾是点或空格）
        safe_title = safe_title.strip(". ")
        # 如果清理后为空，使用默认名称
        if not safe_title:
            safe_title = "untitled"
        return safe_title

    def on_progress(self, callback: Callable[[str, str], None]) -> None:
        """设置进度回调"""
        self._on_progress = callback

    def on_chapter_complete(self, callback: Callable[[int, str], None]) -> None:
        """设置章节完成回调"""
        self._on_chapter_complete = callback

    async def create_novel(
        self,
        title: str,
        user_prompt: str,
        total_chapters: int = 20,
        word_count_per_chapter: int = 3000,
    ) -> NovelContext:
        """
        创建新小说

        Args:
            title: 小说标题
            user_prompt: 用户需求描述
            total_chapters: 总章节数
            word_count_per_chapter: 每章字数

        Returns:
            小说上下文
        """
        # 创建小说上下文
        self.novel_ctx = self.coordinator.create_novel(title, user_prompt)
        self.novel_ctx.snapshot.progress.total_chapters = total_chapters
        self.novel_ctx.snapshot.user_guidance = (
            f"共{total_chapters}章，每章约{word_count_per_chapter}字"
        )

        # 初始化小说专属知识库
        db_path = self._get_knowledge_db_path(title)
        self.knowledge = await create_knowledge_base(
            llm_provider=self.llm,
            db_path=db_path,
            system_prompt=f"你是小说《{title}》的创作助手，负责记住所有设定和情节。",
        )

        self._report_progress("created", f"已创建小说《{title}》")

        return self.novel_ctx

    async def design(self) -> AgentResult:
        """
        执行设计阶段

        Returns:
            设计结果
        """
        if not self.novel_ctx:
            raise RuntimeError("请先调用 create_novel 创建小说")

        self._report_progress("designing", "正在设计架构...")

        # 构建 Agent 上下文
        agent_ctx = self._build_agent_context()
        agent_ctx.extra["total_chapters"] = (
            self.novel_ctx.snapshot.progress.total_chapters
        )

        # 执行设计
        result = await self.designer.execute(agent_ctx)

        if result.success:
            # 保存设计结果到 snapshot
            self.novel_ctx.snapshot.global_summary = result.content

            # 将设计中的节点、边、时间点添加到图结构
            if result.nodes_to_add:
                for node in result.nodes_to_add:
                    self.novel_ctx.graph.add_node(node)
            if result.edges_to_add:
                for edge in result.edges_to_add:
                    self.novel_ctx.graph.add_edge(edge)
            if result.timepoints_to_add:
                for tp in result.timepoints_to_add:
                    self.novel_ctx.timeline.append(tp)

            # 保存完整数据到 snapshot（包括 graph, timeline, world_map, characters）
            self.coordinator.save_novel(self.novel_ctx)

            # 存入知识库
            if self.knowledge:
                await self.knowledge.add_content(
                    content=result.content,
                    content_type="design",
                    metadata={"phase": "architecture"},
                )

            # 更新进度
            from src.core.state import GenerationPhase

            self.coordinator.state_manager.update_progress(
                self.novel_ctx.snapshot, phase=GenerationPhase.BLUEPRINT
            )

            self._report_progress("designed", "架构设计完成")
        else:
            self._report_progress("error", f"设计失败: {result.error}")

        return result

    async def write_chapter(
        self,
        chapter_num: int,
        blueprint: str = "",
        auto_audit: bool = True,
        auto_polish: bool = True,
    ) -> AgentResult:
        """
        撰写单章

        Args:
            chapter_num: 章节号
            blueprint: 章节大纲（可选）
            auto_audit: 是否自动审计
            auto_polish: 是否自动润色

        Returns:
            写作结果
        """
        if not self.novel_ctx:
            raise RuntimeError("请先调用 create_novel 创建小说")

        self._report_progress("writing", f"正在撰写第{chapter_num}章...")

        # 获取已完成章节内容（用于上下文）
        completed_chapters = {}
        for ch_num in self.novel_ctx.snapshot.progress.completed_chapters:
            content = self.coordinator.state_manager.load_chapter(
                self.novel_ctx.snapshot.title, ch_num
            )
            if content:
                completed_chapters[str(ch_num)] = content

        # 构建 Agent 上下文
        agent_ctx = self._build_agent_context()
        agent_ctx.extra["chapter_num"] = chapter_num
        agent_ctx.extra["chapter_blueprint"] = blueprint
        # 从用户配置中获取字数，默认3000
        word_count = self._parse_word_count(
            self.novel_ctx.snapshot.user_guidance
        )
        agent_ctx.extra["word_count"] = word_count
        agent_ctx.extra["completed_chapters"] = completed_chapters
        agent_ctx.extra["state_manager"] = self.coordinator.state_manager
        agent_ctx.extra["novel_title"] = self.novel_ctx.snapshot.title
        agent_ctx.extra["global_summary"] = (
            self.novel_ctx.snapshot.global_summary
        )  # 传递设计大纲
        agent_ctx.knowledge = self.knowledge

        # 写作
        write_result = await self.writer.execute(agent_ctx)

        if not write_result.success:
            self._report_progress("error", f"写作失败: {write_result.error}")
            return write_result

        content = write_result.content

        # 审计
        if auto_audit:
            self._report_progress("auditing", f"正在审计第{chapter_num}章...")

            audit_ctx = self._build_agent_context()
            audit_ctx.user_input = content
            audit_ctx.extra["audit_type"] = "quick"

            audit_result = await self.auditor.execute(audit_ctx)

            if audit_result.issues:
                severe_issues = audit_result.get_severe_issues()
                if severe_issues:
                    self._report_progress(
                        "warning", f"发现{len(severe_issues)}个严重问题，尝试修正..."
                    )
                    # TODO: 自动修正或要求重写

        # 润色
        if auto_polish:
            self._report_progress("polishing", f"正在润色第{chapter_num}章...")

            polish_ctx = self._build_agent_context()
            polish_ctx.user_input = content
            polish_ctx.extra["polish_level"] = "medium"

            polish_result = await self.polisher.execute(polish_ctx)

            if polish_result.success:
                content = polish_result.content

        # 保存章节
        self.coordinator.complete_chapter(
            self.novel_ctx,
            chapter_num,
            content,
            write_result.chapter_title,
        )

        # 更新知识库
        if self.knowledge:
            # 生成智能摘要
            summary = self._generate_chapter_summary(content)
            await self.knowledge.add_chapter_summary(
                chapter_num=chapter_num,
                title=write_result.chapter_title,
                summary=summary,
            )

        self._report_progress("chapter_complete", f"第{chapter_num}章完成")

        if self._on_chapter_complete:
            self._on_chapter_complete(chapter_num, content)

        return AgentResult(
            success=True,
            content=content,
            chapter_num=chapter_num,
            chapter_title=write_result.chapter_title,
        )

    async def write_all_chapters(
        self,
        start: int = 1,
        auto_audit: bool = True,
        auto_polish: bool = True,
    ) -> list[AgentResult]:
        """
        批量撰写章节

        Args:
            start: 起始章节号
            auto_audit: 是否自动审计
            auto_polish: 是否自动润色

        Returns:
            所有章节的写作结果
        """
        if not self.novel_ctx:
            raise RuntimeError("请先调用 create_novel 创建小说")

        total = self.novel_ctx.snapshot.progress.total_chapters
        results = []

        for chapter_num in range(start, total + 1):
            result = await self.write_chapter(
                chapter_num,
                auto_audit=auto_audit,
                auto_polish=auto_polish,
            )
            results.append(result)

            if not result.success:
                break

        return results

    async def load_novel(self, title: str) -> NovelContext | None:
        """
        加载已有小说

        Args:
            title: 小说标题

        Returns:
            小说上下文
        """
        self.novel_ctx = self.coordinator.load_novel(title)

        if self.novel_ctx:
            # 恢复小说专属知识库
            db_path = self._get_knowledge_db_path(title)
            self.knowledge = await create_knowledge_base(
                llm_provider=self.llm,
                db_path=db_path,
            )
            # 知识库数据已在 db 中持久化，无需额外恢复

        return self.novel_ctx

    def save_checkpoint(self) -> str:
        """保存检查点"""
        if not self.novel_ctx:
            raise RuntimeError("没有正在进行的小说")

        return self.coordinator.save_novel(self.novel_ctx)

    def get_resume_info(self) -> dict:
        """获取续传信息"""
        if not self.novel_ctx:
            return {"action": "none", "message": "没有正在进行的小说"}

        return self.coordinator.get_resume_info(self.novel_ctx)

    def _build_agent_context(self) -> AgentContext:
        """构建 Agent 上下文"""
        if self.novel_ctx is None:
            raise RuntimeError("小说上下文未初始化")
        ctx = self.novel_ctx
        return AgentContext(
            graph=ctx.graph,
            timeline=ctx.timeline,
            world_map=ctx.world_map,
            characters=ctx.characters,
            user_input=ctx.snapshot.user_prompt,
            extra={
                "user_guidance": ctx.snapshot.user_guidance,
                "global_summary": ctx.global_summary,
                "current_chapter": ctx.snapshot.progress.current_chapter,
                "total_chapters": ctx.snapshot.progress.total_chapters,
            },
            llm=self.llm,
            knowledge=self.knowledge,
        )

    def _report_progress(self, stage: str, message: str) -> None:
        """报告进度"""
        if self._on_progress:
            self._on_progress(stage, message)

    def _parse_word_count(self, user_guidance: str | None) -> int:
        """从用户配置中解析每章字数"""
        import re

        if not user_guidance:
            return 3000

        # 尝试匹配 "每章约XXX字" 或 "每章XXX字"
        match = re.search(r"每章(?:约)?(\d+)字", user_guidance)
        if match:
            return int(match.group(1))

        return 3000

    def _generate_chapter_summary(self, content: str) -> str:
        """生成章节摘要

        提取开头、中间关键段落和结尾，形成结构化摘要
        """
        if not content:
            return ""

        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        if not paragraphs:
            return content[:500]

        # 提取开头（前2段）
        opening = "\n".join(paragraphs[:2])

        # 提取中间（如果有足够段落，取中间2段）
        middle = ""
        if len(paragraphs) > 6:
            mid_idx = len(paragraphs) // 2
            middle = "\n".join(paragraphs[mid_idx : mid_idx + 2])

        # 提取结尾（最后2段）
        ending = "\n".join(paragraphs[-2:]) if len(paragraphs) > 2 else ""

        # 组合摘要
        parts = []
        if opening:
            parts.append(f"【开头】\n{opening[:200]}")
        if middle:
            parts.append(f"【中段】\n{middle[:150]}")
        if ending:
            parts.append(f"【结尾】\n{ending[:150]}")

        summary = "\n\n".join(parts)
        return summary[:800] if len(summary) > 800 else summary

    async def close(self) -> None:
        """关闭生成器"""
        if self.knowledge:
            await self.knowledge.close()


async def create_generator(
    llm_config: dict,
    save_dir: str = "./novels",
    knowledge_db: str = "./novel_memory.db",
) -> NovelGenerator:
    """
    创建小说生成器

    Args:
        llm_config: LLM 配置
        save_dir: 保存目录
        knowledge_db: 知识库路径

    Returns:
        NovelGenerator 实例
    """
    return NovelGenerator(
        llm_config=llm_config,
        save_dir=save_dir,
        knowledge_db=knowledge_db,
    )
