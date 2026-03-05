"""小说生成器 - 主流程编排

整合所有模块，实现完整的小说生成流程：
1. 设计阶段 - Designer
2. 写作阶段 - Writer
3. 审计阶段 - Auditor
4. 润色阶段 - Polisher
"""

from typing import Callable

from src.agent import Designer, Writer, Auditor, Polisher, AgentContext, AgentResult
from src.core import NovelContext, NovelCoordinator
from src.llm import LLMProvider, KnowledgeBase, create_knowledge_base


class NovelGenerator:
    """小说生成器"""
    
    def __init__(
        self,
        llm_config: dict,
        save_dir: str = "./novels",
        knowledge_db: str = "./novel_memory.db",
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
            knowledge_db: 知识库数据库路径
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
        
        # 初始化知识库
        self.knowledge_db = knowledge_db
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
        self.novel_ctx.snapshot.user_guidance = f"共{total_chapters}章，每章约{word_count_per_chapter}字"
        
        # 初始化知识库
        self.knowledge = await create_knowledge_base(
            llm_provider=self.llm,
            db_path=self.knowledge_db,
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
        agent_ctx.extra["total_chapters"] = self.novel_ctx.snapshot.progress.total_chapters
        
        # 执行设计
        result = await self.designer.execute(agent_ctx)
        
        if result.success:
            # 保存设计结果到 snapshot
            self.novel_ctx.snapshot.global_summary = result.content
            
            # 保存 snapshot
            self.coordinator.state_manager.save_draft(self.novel_ctx.snapshot)
            
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
                self.novel_ctx.snapshot, 
                phase=GenerationPhase.BLUEPRINT
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
        agent_ctx.extra["word_count"] = 3000  # TODO: 从配置读取
        agent_ctx.extra["completed_chapters"] = completed_chapters
        agent_ctx.extra["state_manager"] = self.coordinator.state_manager
        agent_ctx.extra["novel_title"] = self.novel_ctx.snapshot.title
        agent_ctx.extra["global_summary"] = self.novel_ctx.snapshot.global_summary  # 传递设计大纲
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
                    self._report_progress("warning", f"发现{len(severe_issues)}个严重问题，尝试修正...")
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
            await self.knowledge.add_chapter_summary(
                chapter_num=chapter_num,
                title=write_result.chapter_title,
                summary=content[:500],  # TODO: 生成真正的摘要
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
            # 恢复知识库
            self.knowledge = await create_knowledge_base(
                llm_provider=self.llm,
                db_path=self.knowledge_db,
            )
        
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
