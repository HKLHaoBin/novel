"""文笔优化师 Agent - 负责文字润色

润色原则：最小化改动，保持原意和风格
1. 删除多余虚词 - 的、了、着、呢、嘛
2. 修正明显语病 - 病句、错字
3. 优化节奏 - 避免连续长句/短句
4. 减少重复用词 - 同一段落重复词汇
5. 保持字数 - 润色后字数不能少于原文
"""

from .base import AgentContext, AgentResult, BaseAgent
from .prompt_loader import prompt_library


class Polisher(BaseAgent):
    """文笔优化师 Agent"""

    name = "Polisher"
    description = "文笔优化师，专注于文字润色、节奏调整和风格统一，让文字更具感染力"
    _system_prompt: str
    _metadata: dict

    def __init__(self, llm=None):
        """初始化优化师"""
        super().__init__(llm=llm)
        self._load_prompts()

    def _load_prompts(self):
        """加载提示词模板"""
        self._system_prompt = prompt_library.get_system_prompt("polisher")
        self._metadata = prompt_library.get_metadata("polisher")
        self.name = self._metadata.get("name", "Polisher")
        self.description = self._metadata.get("description", "")

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行润色任务

        Args:
            context: 执行上下文，需要包含:
                - user_input: 待润色的内容
                - extra.get("min_word_count"): 最小字数（默认原文字数）
                - extra.get("style"): 风格参考（可选）

        Returns:
            润色结果
        """
        self._context = context

        content = context.user_input
        if not content:
            return AgentResult(
                success=False,
                error="缺少待润色的内容",
            )

        original_word_count = len(content)
        min_word_count = context.extra.get("min_word_count", original_word_count)

        try:
            polished = await self._polish(content, min_word_count)

            # 验证字数
            polished_count = len(polished)
            if polished_count < min_word_count:
                # 字数不足，返回原文
                return AgentResult(
                    success=True,
                    content=content,
                    extra={
                        "original_count": original_word_count,
                        "polished_count": polished_count,
                        "min_count": min_word_count,
                        "fallback": True,
                        "reason": (
                            f"润色后字数{polished_count}"
                            f"不足目标{min_word_count}，使用原文"
                        ),
                    },
                )

            return AgentResult(
                success=True,
                content=polished,
                extra={
                    "original_count": original_word_count,
                    "polished_count": polished_count,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"润色过程出错: {e!s}",
            )

    async def _polish(self, content: str, min_word_count: int) -> str:
        """
        执行润色 - 最小化改动原则

        Args:
            content: 原文
            min_word_count: 最小字数

        Returns:
            润色后的内容
        """
        prompt = f"""请对以下内容进行润色。

【原文】
{content}

【原文字数】
{len(content)}字

【最小字数要求】
{min_word_count}字（润色后不能少于此字数）

【润色原则 - 最小化改动】
1. 删除多余虚词：删减不必要的"的""了""着""呢""嘛"
2. 修正明显语病：病句、错字、标点错误
3. 优化节奏：避免连续长句或短句，调整句式变化
4. 减少重复：同一段落内重复用词替换为同义词
5. 保持字数：润色后字数不能少于原文

【禁止事项】
- ❌ 大幅改写句子结构
- ❌ 改变原文意思
- ❌ 删减有效内容
- ❌ 添加原文没有的内容
- ❌ 改变作者的写作风格
- ❌ 追求"文学性"而过度润色

【润色示例】
原文：他轻轻地推开了那扇古老的门，门发出了吱呀的声音。
润色：他轻推古门，吱呀一声。
（删除多余的"地""了""那扇""的"，优化节奏）

原文：她感到很开心很高兴很快乐。
润色：她感到开心愉悦。
（减少重复，删除多余程度词）

【输出要求】
- 直接输出润色后的内容
- 不要任何解释或说明
- 不要markdown格式
- 保持原文段落结构
- 字数≥{min_word_count}字"""

        result = await self._call_llm(
            prompt,
            system=self._system_prompt,
            max_tokens=len(content) + 500,
        )

        return result

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt


# 便捷方法
async def quick_polish(llm, content: str, min_word_count: int = 0) -> str:
    """
    快速润色

    Args:
        llm: LLM 提供者
        content: 待润色内容
        min_word_count: 最小字数（默认原文字数）

    Returns:
        润色后的内容
    """
    if min_word_count == 0:
        min_word_count = len(content)

    polisher = Polisher(llm=llm)
    result = await polisher.execute(
        AgentContext(
            graph=None,
            timeline=None,
            world_map=None,
            characters={},
            user_input=content,
            extra={"min_word_count": min_word_count},
        )
    )
    return result.content if result.success else content
