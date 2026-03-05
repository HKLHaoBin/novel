"""文笔优化师 Agent - 负责文字润色

五个润色维度：
1. 流畅性 - 句子是否通顺
2. 生动性 - 描写是否生动
3. 感染力 - 情感是否打动人
4. 文学性 - 是否有文采
5. 节奏感 - 张弛是否合理
"""

from .base import AgentContext, AgentResult, BaseAgent
from .prompt_loader import prompt_library


class Polisher(BaseAgent):
    """文笔优化师 Agent"""
    
    name = "Polisher"
    description = "文笔优化师，专注于文字润色、节奏调整和风格统一，让文字更具感染力"
    
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
                - extra.get("polish_level"): 润色强度 (light/medium/deep)
                - extra.get("focus"): 润色重点 (flow/vivid/emotion/literary/rhythm/all)
                
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
        
        polish_level = context.extra.get("polish_level", "medium")
        focus = context.extra.get("focus", "all")
        
        try:
            polished = await self._polish(content, polish_level, focus)
            
            return AgentResult(
                success=True,
                content=polished,
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"润色过程出错: {str(e)}",
            )
    
    async def _polish(
        self, 
        content: str, 
        level: str = "medium",
        focus: str = "all"
    ) -> str:
        """执行润色"""
        
        level_descriptions = {
            "light": "轻微润色：保持原文风格，仅修正明显问题，改动<10%",
            "medium": "中等润色：优化表达，提升整体质量，改动10-30%",
            "deep": "深度润色：大幅改写，追求文学效果，改动30-50%",
        }
        
        focus_descriptions = {
            "flow": "流畅性：句子通顺、衔接自然、节奏舒适",
            "vivid": "生动性：感官描写、具体细节、画面感",
            "emotion": "感染力：情感真挚、代入感强、共鸣触发",
            "literary": "文学性：用词精准、修辞恰当、诗意瞬间",
            "rhythm": "节奏感：长短变化、张弛有度、呼吸感",
            "all": "全面润色：流畅性、生动性、感染力、文学性、节奏感",
        }
        
        level_desc = level_descriptions.get(level, level_descriptions["medium"])
        focus_desc = focus_descriptions.get(focus, focus_descriptions["all"])
        
        prompt = f"""请对以下内容进行润色。

【原文】
{content}

【润色强度】
{level_desc}

【润色重点】
{focus_desc}

【润色原则】
1. 保持原意：不改变情节和人物行为
2. 保持风格：不改变作者的写作风格
3. 保持节奏：不改变故事的节奏感
4. 自然无痕：润色后要自然，看不出痕迹

【润色要点】
- 流畅性：修正病句、优化衔接、消除冗余
- 生动性：增加细节、强化感官、使用比喻
- 感染力：深化情感、增强张力、引发共鸣
- 文学性：优化措辞、恰当修辞、提升文采
- 节奏感：调整句式、控制速度、张弛有度

【禁止事项】
- ❌ 改变情节走向
- ❌ 改变角色性格
- ❌ 过度润色导致堆砌
- ❌ 强加自己的风格

【输出要求】
- 直接输出润色后的内容
- 不要任何解释或说明
- 不要使用markdown格式
- 保持原文的段落结构
- 字数与原文相近"""
        
        result = await self._call_llm(
            prompt, 
            system=self._system_prompt,
            max_tokens=len(content) + 1000,
        )
        
        return result
    
    async def polish_with_comparison(
        self,
        content: str,
        level: str = "medium",
    ) -> dict:
        """
        润色并返回对比
        
        Args:
            content: 原文
            level: 润色强度
            
        Returns:
            包含原文、润色后、改动的字典
        """
        polished = await self._polish(content, level)
        
        return {
            "original": content,
            "polished": polished,
            "word_count_original": len(content),
            "word_count_polished": len(polished),
        }
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt


# 便捷方法
async def quick_polish(llm, content: str, level: str = "medium") -> str:
    """
    快速润色
    
    Args:
        llm: LLM 提供者
        content: 待润色内容
        level: 润色强度
        
    Returns:
        润色后的内容
    """
    polisher = Polisher(llm=llm)
    result = await polisher.execute(AgentContext(
        graph=None,
        timeline=None,
        world_map=None,
        characters={},
        user_input=content,
        extra={"polish_level": level},
    ))
    return result.content if result.success else content