"""设计师 Agent - 负责小说架构设计

使用雪花写作法，分阶段设计：
1. 核心种子 - 一句话概括故事本质
2. 角色动力学 - 角色设定与弧光
3. 世界构建 - 世界观设定
4. 情节架构 - 三幕式结构
5. 章节蓝图 - 目录与大纲
"""

from .base import AgentContext, AgentResult, BaseAgent
from .prompt_loader import prompt_library


class Designer(BaseAgent):
    """设计师 Agent"""

    name = "Designer"
    description = "专业小说架构师，精通雪花写作法、角色弧光理论和三幕式情节设计"
    _system_prompt: str
    _metadata: dict

    def __init__(self, llm=None):
        """初始化设计师"""
        super().__init__(llm=llm)
        self._load_prompts()

    def _load_prompts(self):
        """加载提示词模板"""
        self._system_prompt = prompt_library.get_system_prompt("designer")
        self._metadata = prompt_library.get_metadata("designer")
        self.name = self._metadata.get("name", "Designer")
        self.description = self._metadata.get("description", "")

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行设计任务

        Args:
            context: 执行上下文，需要包含:
                - user_input: 用户需求描述
                - extra.get("phase"): 当前阶段
                  (seed/character/world/plot/blueprint/full)

        Returns:
            设计结果
        """
        self._context = context

        phase = context.extra.get("phase", "full")
        user_input = context.user_input

        if not user_input:
            return AgentResult(
                success=False,
                error="缺少用户需求描述",
            )

        try:
            if phase == "full":
                return await self._full_design(context)
            elif phase == "seed":
                return await self._design_seed(context, user_input)
            elif phase == "character":
                return await self._design_characters(context)
            elif phase == "world":
                return await self._design_world(context)
            elif phase == "plot":
                return await self._design_plot(context)
            elif phase == "blueprint":
                return await self._design_blueprint(context)
            else:
                return AgentResult(
                    success=False,
                    error=f"未知的设计阶段: {phase}",
                )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"设计过程出错: {e!s}",
            )

    async def _full_design(self, context: AgentContext) -> AgentResult:
        """完整设计流程"""
        results: list[AgentResult] = []
        accumulated_content = ""  # 累积的设计内容

        # seed 阶段需要额外参数
        seed_result = await self._design_seed(
            context, context.user_input, accumulated_content
        )
        if not seed_result.success:
            return seed_result
        results.append(seed_result)
        accumulated_content += f"\n\n【核心种子】\n{seed_result.content}"

        # 后续阶段，传递累积的内容
        from collections.abc import Callable, Coroutine
        from typing import Any

        PhaseFunc = Callable[[AgentContext], Coroutine[Any, Any, AgentResult]]
        phases: list[tuple[str, PhaseFunc]] = [
            ("character", self._design_characters),
            ("world", self._design_world),
            ("plot", self._design_plot),
            ("blueprint", self._design_blueprint),
        ]

        for phase_name, phase_func in phases:
            # 将累积内容传入 context.extra
            context.extra["accumulated_design"] = accumulated_content
            result = await phase_func(context)
            if not result.success:
                return result
            results.append(result)
            accumulated_content += f"\n\n【{phase_name}】\n{result.content}"

        return AgentResult(
            success=True,
            content=accumulated_content,
            nodes_to_add=[n for r in results for n in r.nodes_to_add],
            edges_to_add=[e for r in results for e in r.edges_to_add],
            timepoints_to_add=[t for r in results for t in r.timepoints_to_add],
        )

    async def _design_seed(
        self, context: AgentContext, user_input: str, accumulated: str = ""
    ) -> AgentResult:
        """设计核心种子"""
        total_chapters = context.extra.get("total_chapters", 20)
        word_count = context.extra.get("word_count_per_chapter", 3000)
        # 获取用户的额外指导（如修改意见）
        user_guidance = context.extra.get("user_guidance", "")

        # 构建完整的用户需求
        full_user_input = user_input
        if user_guidance:
            full_user_input = f"{user_input}\n\n【用户额外要求】\n{user_guidance}"

        prompt = f"""请根据以下需求，设计小说的核心种子。

【用户需求】
{full_user_input}

【约束条件】
- 总章节：约{total_chapters}章
- 每章字数：约{word_count}字
- 必须包含显性冲突与潜在危机
- 使用25-100字精准表达
- 必须严格遵循用户需求中的设定（时代背景、角色身份等）

【输出格式】
核心种子
├── 故事核心：[一句话，25-100字]
├── 核心冲突：[主角想要什么] vs [什么阻止他]
├── 主题内核：[探讨的人性/社会命题]
├── 情感基调：[热血/治愈/悬疑/悲剧/...]
├── 危机层次：
│   ├── 显性危机：[...]
│   ├── 潜在危机：[...]
│   └── 隐藏危机：[...]
└── 目标读者：[...]

仅输出核心种子内容，不要解释。"""

        content = await self._call_llm(prompt, system=self._system_prompt)

        return AgentResult(
            success=True,
            content=content,
        )

    async def _design_characters(self, context: AgentContext) -> AgentResult:
        """设计角色"""
        # 获取累积的设计内容和用户原始需求
        accumulated = context.extra.get("accumulated_design", "")
        user_guidance = context.user_input

        prompt = f"""请基于以下信息，设计小说的主要角色。

【用户原始需求】
{user_guidance}

【已确定的核心设定】
{accumulated if accumulated else "无"}

【设计要求】
- 必须严格遵循用户原始需求中的角色设定（姓名、身份、时代背景等）
- 设计3-6个核心角色
- 每个角色必须有：驱动力三角、角色弧线、关系网
- 角色之间必须有价值观冲突和合作纽带

【输出格式】
角色设计
│
├── 主角：[名字]（必须使用用户指定的名字！）
│   ├── 基本信息：年龄|性别|职业|外貌
│   ├── 背景秘密：[...]
│   ├── 驱动力三角：
│   │   ├── 表面追求：[物质目标]
│   │   ├── 深层渴望：[情感需求]
│   │   └── 灵魂需求：[哲学层面]
│   ├── 角色弧线：[初始] → [触发] → [失调] → [蜕变] → [最终]
│   ├── 性格特征：优点[...] 缺陷[...]
│   └── 关系网：[...]
│
├── 重要配角：[名字]
│   └── ...

仅输出角色设计内容，不要解释。"""

        content = await self._call_llm(prompt, system=self._system_prompt)

        return AgentResult(
            success=True,
            content=content,
        )

    async def _design_world(self, context: AgentContext) -> AgentResult:
        """设计世界观"""
        accumulated = context.extra.get("accumulated_design", "")

        prompt = f"""请基于以下信息，设计小说的世界观。

【用户原始需求】
{context.user_input}

【已确定的核心设定】
{accumulated if accumulated else "无"}

【设计要求】
- 必须与用户需求的年代背景一致
- 构建三维交织的世界观：物理、社会、隐喻
- 每个维度至少3个可与角色决策互动的动态元素
- 世界观服务于叙事

【输出格式】
世界观设定
│
├── 物理维度
│   ├── 空间结构：[地理×阶层分布]
│   ├── 时间轴：[关键历史事件]
│   └── 法则体系：[规则与漏洞]
│
├── 社会维度
│   ├── 权力断层：[可引发冲突的矛盾]
│   ├── 文化禁忌：[可打破的禁忌及后果]
│   └── 经济命脉：[资源争夺焦点]
│
└── 隐喻维度
    ├── 视觉符号：[反复出现的意象]
    ├── 环境映射：[气候→心理]
    └── 建筑暗示：[风格→文明困境]

仅输出世界观内容，不要解释。"""

        content = await self._call_llm(prompt, system=self._system_prompt)

        return AgentResult(
            success=True,
            content=content,
        )

    async def _design_plot(self, context: AgentContext) -> AgentResult:
        """设计情节架构"""
        accumulated = context.extra.get("accumulated_design", "")

        prompt = f"""请基于以下信息，设计小说的情节架构。

【用户原始需求】
{context.user_input}

【已确定的核心设定】
{accumulated if accumulated else "无"}

【设计要求】
- 必须与角色设定和世界观保持一致
- 使用三幕式结构
- 第一幕约25%，第二幕约50%，第三幕约25%
- 高潮必须回应所有主线问题

【输出格式】
情节架构
│
├── 第一幕：触发（约25%）
│   ├── 日常世界：[...]
│   ├── 触发事件：[...]
│   └── 跨越门槛：[...]
│
├── 第二幕：对抗（约50%）
│   ├── 试炼盟友：[...]
│   ├── 中点转折：[认知颠覆点]
│   ├── 危机加深：[...]
│   └── 灵魂黑夜：[...]
│
└── 第三幕：解决（约25%）
    ├── 终极之战：[...]
    ├── 高潮时刻：[...]
    └── 新的平衡：[...]

仅输出情节架构内容，不要解释。"""

        content = await self._call_llm(prompt, system=self._system_prompt)

        return AgentResult(
            success=True,
            content=content,
        )

    async def _design_blueprint(self, context: AgentContext) -> AgentResult:
        """设计章节蓝图"""
        accumulated = context.extra.get("accumulated_design", "")
        total_chapters = context.extra.get("total_chapters", 20)

        prompt = f"""请基于以下信息，设计小说的章节蓝图。

【用户原始需求】
{context.user_input}

【已确定的核心设定】
{accumulated if accumulated else "无"}

【设计要求】
- 必须与角色设定和世界观保持一致
- 总共{total_chapters}章
- 每3-5章构成一个悬念单元
- 每章100字大纲
- 在第{total_chapters}章前不要出现结局章节

【输出格式】
章节蓝图
│
├── 第1章 [标题]
│   ├── 定位：[角色/事件/主题]
│   ├── 作用：[推进/转折/揭示/铺垫]
│   ├── 悬念：[信息差/道德困境/时间压力]
│   ├── 伏笔：[埋设/强化/回收]
│   ├── 认知颠覆：★☆☆☆☆
│   └── 大纲：[一句话，100字内]
│
├── 第2章 [标题]
│   └── ...
...

仅输出章节蓝图内容，不要解释。"""

        content = await self._call_llm(prompt, system=self._system_prompt)

        return AgentResult(
            success=True,
            content=content,
        )

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt
