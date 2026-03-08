"""作家 Agent - 负责章节内容撰写

核心能力：
1. 根据大纲撰写章节正文
2. 使用工具主动查询上下文（通过 function calling）
3. 集成上下文构建器
"""

from src.llm.provider import ToolCallLoop

from .base import AgentContext, AgentResult, BaseAgent
from .context_builder import build_full_context
from .prompt_loader import prompt_library
from .tools import get_all_tools


class Writer(BaseAgent):
    """作家 Agent"""

    name = "Writer"
    description = "专业小说作家，擅长生动场景描写、自然对话设计和扣人心弦的情节推进"
    _system_prompt: str
    _metadata: dict

    def __init__(self, llm=None):
        """初始化作家"""
        super().__init__(llm=llm)
        self._load_prompts()
        self._tools = get_all_tools()

    def _load_prompts(self):
        """加载提示词模板"""
        self._system_prompt = prompt_library.get_system_prompt("writer")
        self._metadata = prompt_library.get_metadata("writer")
        self.name = self._metadata.get("name", "Writer")
        self.description = self._metadata.get("description", "")

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行写作任务

        Args:
            context: 执行上下文，需要包含:
                - extra.get("chapter_num"): 章节号
                - extra.get("chapter_blueprint"): 章节蓝图/大纲
                - extra.get("word_count"): 目标字数（默认3000）

        Returns:
            写作结果
        """
        self._context = context

        chapter_num = context.extra.get("chapter_num", 1)
        blueprint = context.extra.get("chapter_blueprint", "")
        word_count = context.extra.get("word_count", 3000)
        self._publish_start(
            context,
            context_summary=(
                f"章节: 第{chapter_num}章\n"
                f"目标字数: {word_count}\n"
                f"角色数: {len(context.characters)}"
            ),
            prompt=str(blueprint)[:4000],
            meta={"chapter_num": chapter_num, "word_count": word_count},
        )

        try:
            # 构建基础上下文
            ctx_text = build_full_context(context)

            # 判断是第一章还是后续章节
            is_first_chapter = chapter_num == 1

            tool_title = None

            if is_first_chapter:
                content, tool_title = await self._write_first_chapter(
                    context, ctx_text, blueprint, word_count
                )
            else:
                content, tool_title = await self._write_chapter(
                    context, ctx_text, blueprint, chapter_num, word_count
                )

            # 优先使用工具设置的标题
            if tool_title:
                title = tool_title
            else:
                # 回退到从内容提取
                title = self._extract_title(content, chapter_num)

            result = AgentResult(
                success=True,
                content=content,
                chapter_num=chapter_num,
                chapter_title=title,
            )
            self._publish_result(
                context,
                status="completed",
                output=content[:12000],
                meta={"chapter_num": chapter_num, "chapter_title": title},
            )
            return result

        except Exception as e:
            import traceback

            result = AgentResult(
                success=False,
                error=f"写作过程出错: {e!s}\n{traceback.format_exc()}",
            )
            self._publish_result(
                context,
                status="failed",
                error=result.error,
                meta={"chapter_num": chapter_num},
            )
            return result

    async def _write_first_chapter(
        self,
        context: AgentContext,
        ctx_text: str,
        blueprint: str,
        word_count: int,
    ) -> tuple[str, str | None]:
        """撰写第一章

        Returns:
            (内容, 标题) 元组
        """

        system_prompt = f"""你是专业小说作家。

【当前任务】撰写小说第一章

【世界观与设定】
{ctx_text}

【工具使用指南】
你可以使用以下工具：
- query_character(角色名): 查询角色详细信息
- query_location(地点名): 查询地点信息
- query_timeline(): 查询时间轴
- suggest_next(): 获取下一步建议
- set_chapter_title(标题): 设置章节标题（建议在开始时调用）
- complete(content, title, end): 提交内容

【分段提交机制】（重要！）
为避免输出截断，请分段提交内容：
- 每写约2000字，调用 complete(content, title, end=False) 提交一段
- 最后一段调用 complete(content, title, end=True) 表示章节结束
- 示例：
  1. complete("前2000字内容...", "章节标题", end=False)
  2. complete("中间2000字...", end=False)
  3. complete("最后部分...", end=True)

【第一章特殊要求】
1. 开篇黄金500字：建立场景氛围 → 引入主角 → 出现冲突/悬念
2. 埋下贯穿全文的伏笔（至少1个）
3. 章末悬念钩子，吸引继续阅读
4. 必须设置一个独特的章节标题

【输出要求】
- 使用标准的小说格式（对话用「」）
- 字数控制在{word_count}字左右"""

        user_prompt = f"""请撰写第一章。

【章节大纲】
{blueprint if blueprint else "根据设定自由发挥，开篇要吸引人"}

【目标字数】
{word_count}字左右

【工作流程】
1. 先调用 set_chapter_title 设置一个独特的章节标题
2. 使用工具查询必要的角色和设定信息
3. 开始写作，每约2000字调用 complete(content, title, end=False) 提交一段
4. 最后一段调用 complete(content, title, end=True) 完成章节"""

        # 使用工具调用循环
        tool_loop = ToolCallLoop(
            tools=self._tools,
            context=context,
            max_iterations=100,
            on_tool_call=lambda n, a: self._publish_tool_call(
                context, tool_name=n, arguments=a
            ),
            on_tool_result=lambda n, r: self._publish_tool_result(
                context,
                tool_name=n,
                success=r.success,
                content=r.content,
                issues=r.issues,
            ),
        )

        if self.llm is None:
            raise RuntimeError("LLM provider 未设置")

        content = await tool_loop.run(
            provider=self.llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=word_count + 500,
        )

        return content, tool_loop.chapter_title

    async def _write_chapter(
        self,
        context: AgentContext,
        ctx_text: str,
        blueprint: str,
        chapter_num: int,
        word_count: int,
    ) -> tuple[str, str | None]:
        """撰写后续章节（带工具调用）

        Returns:
            (内容, 标题) 元组
        """

        system_prompt = f"""你是专业小说作家。

【当前任务】撰写小说第{chapter_num}章

【世界观与设定】
{ctx_text}

【工具使用指南】
- query_previous_chapter(章节号): 查询前文内容
- query_all_chapters(): 查询所有已完成章节摘要
- query_chapter_outline(章节号): 查询章节大纲
- query_character(角色名): 查询角色当前状态
- query_events(): 查询已发生事件
- query_timeline(): 查询时间轴
- suggest_next(): 获取下一步发展建议
- set_chapter_title(标题): 设置章节标题（建议在开始时调用）
- complete(content, title, end): 提交内容

【分段提交机制】（重要！）
为避免输出截断，请分段提交内容：
- 每写约2000字，调用 complete(content, title, end=False) 提交一段
- 最后一段调用 complete(content, title, end=True) 表示章节结束
- 示例：
  1. complete("前2000字内容...", "章节标题", end=False)
  2. complete("中间2000字...", end=False)
  3. complete("最后部分...", end=True)

【强制要求 - 必须按顺序执行】
1. 首先调用 query_previous_chapter({chapter_num - 1}) 获取上一章完整内容
2. 调用 set_chapter_title 设置一个独特的章节标题（不要与前面章节重复）
3. 根据前文内容确保风格、角色、情节连贯
4. 分段提交内容，最后一段设置 end=True

【写作要求】
1. 承接上文：风格统一、自然过渡
2. 推进情节：有实质进展
3. 角色一致：人名、性格、行为统一
4. 场景合理：地点转换有交代
5. 标题创新：每章标题必须独特，不能与前面章节重复

【输出格式】
字数控制在{word_count}字左右。"""

        user_prompt = f"""请撰写第{chapter_num}章。

【本章大纲】
{blueprint if blueprint else "根据上下文继续推进情节"}

【目标字数】
{word_count}字左右

【执行步骤 - 严格按顺序】
步骤1: 调用 query_previous_chapter({chapter_num - 1}) 查看上一章内容
步骤2: 调用 set_chapter_title 设置一个独特的章节标题
步骤3: 确认上一章的风格、角色名字、情节发展
步骤4: 开始写作，每约2000字调用 complete(content, title, end=False) 提交一段
步骤5: 最后一段调用 complete(content, title, end=True) 完成章节"""

        # 使用工具调用循环
        tool_loop = ToolCallLoop(
            tools=self._tools,
            context=context,
            max_iterations=100,
            on_tool_call=lambda n, a: self._publish_tool_call(
                context, tool_name=n, arguments=a
            ),
            on_tool_result=lambda n, r: self._publish_tool_result(
                context,
                tool_name=n,
                success=r.success,
                content=r.content,
                issues=r.issues,
            ),
        )

        if self.llm is None:
            raise RuntimeError("LLM provider 未设置")

        content = await tool_loop.run(
            provider=self.llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=word_count + 500,
        )

        return content, tool_loop.chapter_title

    def _extract_title(self, content: str, chapter_num: int) -> str:
        """从内容中提取标题"""
        import re

        lines = content.strip().split("\n")
        if lines:
            first_line = lines[0].strip()
            # 匹配 "第X章 标题" 或 "第X章：标题" 或 "第X章标题"
            # 支持全角/半角冒号、空格分隔，或无分隔符
            match = re.match(r"第\d+章[：:\s]*(.+)$", first_line)
            if match:
                title = match.group(1).strip()
                # 清理标题中的非法字符（保留空格）
                title = re.sub(r"[。：:，,！!？?；;　]+", "", title).strip()
                # 限制长度
                if len(title) > 20:
                    title = title[:20]
                return title

        return ""

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt
