"""作家 Agent - 负责章节内容撰写

核心能力：
1. 根据大纲撰写章节正文
2. 集成上下文构建器
3. 引导使用工具查询避免错误
"""

from .base import AgentContext, AgentResult, BaseAgent
from .context_builder import build_full_context, build_uncertainty_guidance
from .prompt_loader import prompt_library


class Writer(BaseAgent):
    """作家 Agent"""
    
    name = "Writer"
    description = "专业小说作家，擅长生动场景描写、自然对话设计和扣人心弦的情节推进"
    
    def __init__(self, llm=None):
        """初始化作家"""
        super().__init__(llm=llm)
        self._load_prompts()
    
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
        
        try:
            # 构建上下文
            ctx_text = build_full_context(context)
            uncertainty_guide = build_uncertainty_guidance()
            
            # 判断是第一章还是后续章节
            is_first_chapter = chapter_num == 1
            
            if is_first_chapter:
                content = await self._write_first_chapter(
                    context, ctx_text, uncertainty_guide, blueprint, word_count
                )
            else:
                content = await self._write_chapter(
                    context, ctx_text, uncertainty_guide, blueprint, chapter_num, word_count
                )
            
            # 提取章节标题
            title = self._extract_title(content, chapter_num)
            
            return AgentResult(
                success=True,
                content=content,
                chapter_num=chapter_num,
                chapter_title=title,
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"写作过程出错: {str(e)}",
            )
    
    async def _write_first_chapter(
        self,
        context: AgentContext,
        ctx_text: str,
        uncertainty_guide: str,
        blueprint: str,
        word_count: int,
    ) -> str:
        """撰写第一章"""
        
        prompt = f"""请撰写小说的第一章。

【世界观与设定】
{ctx_text}

【章节大纲】
{blueprint if blueprint else '根据设定自由发挥，开篇要吸引人'}

【目标字数】
{word_count}字左右

【第一章特殊要求】
1. 开篇黄金500字：
   - 前100字：建立场景氛围
   - 100-300字：引入主角特征（通过行动而非介绍）
   - 300-500字：出现第一个冲突/悬念点
   - 500字后：进入正题
2. 埋下贯穿全文的伏笔（至少1个）
3. 章末悬念钩子，吸引继续阅读

{uncertainty_guide}

【输出要求】
- 直接输出章节正文，不要标题
- 使用标准的小说格式（对话用「」）
- 场景描写生动，对话自然流畅
- 注意节奏控制，张弛有度
- 字数控制在{word_count}字左右"""
        
        content = await self._call_llm(
            prompt, 
            system=self._system_prompt,
            max_tokens=word_count + 500,
        )
        
        return content
    
    async def _write_chapter(
        self,
        context: AgentContext,
        ctx_text: str,
        uncertainty_guide: str,
        blueprint: str,
        chapter_num: int,
        word_count: int,
    ) -> str:
        """撰写后续章节"""
        
        # 获取上一章摘要
        prev_summary = ""
        if context.knowledge:
            try:
                memories = await context.knowledge.retrieve(f"第{chapter_num-1}章摘要", top_k=2)
                if memories:
                    prev_summary = "\n".join(m.get("summary", m.get("content", "")) for m in memories)
            except Exception:
                pass
        
        prompt = f"""请撰写小说的第{chapter_num}章。

【世界观与设定】
{ctx_text}

【上一章摘要】
{prev_summary if prev_summary else "无历史记录"}

【本章大纲】
{blueprint if blueprint else "根据上下文继续推进情节，确保故事连贯"}

【目标字数】
{word_count}字左右

【写作要求】
1. 承接上文：自然过渡，不生硬
2. 推进情节：每章都要有实质进展
3. 角色一致：行为符合已建立的人设
4. 场景合理：地点转换要有交代
5. 时间清晰：让读者知道是什么时间
6. 情感节奏：根据大纲调整张弛

{uncertainty_guide}

【输出要求】
- 直接输出章节正文，不要标题
- 使用标准的小说格式
- 确保内容连贯，不与前文矛盾
- 字数控制在{word_count}字左右"""
        
        content = await self._call_llm(
            prompt,
            system=self._system_prompt,
            max_tokens=word_count + 500,
        )
        
        return content
    
    def _extract_title(self, content: str, chapter_num: int) -> str:
        """从内容中提取标题"""
        lines = content.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            # 如果第一行包含章节信息
            if '第' in first_line and '章' in first_line:
                # 尝试提取标题
                parts = first_line.split('章', 1)
                if len(parts) > 1:
                    return parts[1].strip().replace('《', '').replace('》', '')
        
        return ""
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt


# 场景模板
SCENE_TEMPLATES = {
    "action": """
【动作场景技巧】
- 用短句加快节奏
- 多用动词少用形容词
- 删减过渡语
- 增强感官冲击
""",
    "dialogue": """
【对话场景技巧】
- 对话要自然口语化
- 增加动作描写增强画面
- 体现角色性格差异
- 每句对话都要有存在意义
""",
    "description": """
【描写场景技巧】
- 远景→中景→近景→动态
- 五感并用
- 避免信息倾倒
- 选取典型细节
""",
    "emotion": """
【情感场景技巧】
- 用行动展示情感
- 控制情感强度节奏
- 适当留白引发共鸣
- 避免过度煽情
""",
}
