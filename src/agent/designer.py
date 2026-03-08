"""设计师 Agent - 负责小说架构设计

使用雪花写作法，分阶段设计：
1. 核心种子 - 一句话概括故事本质
2. 角色动力学 - 角色设定与弧光
3. 世界构建 - 世界观设定
4. 情节架构 - 三幕式结构
5. 章节蓝图 - 目录与大纲
"""

from src.llm.provider import ToolCallLoop

from .base import AgentContext, AgentResult, BaseAgent
from .prompt_loader import prompt_library
from .tools import get_all_tools


class Designer(BaseAgent):
    """设计师 Agent - 使用工具调用构建设计"""

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

    def _get_design_system_prompt(self, context: AgentContext) -> str:
        """获取设计系统提示词"""
        total_chapters = context.extra.get("total_chapters", 20)
        word_count = context.extra.get("word_count_per_chapter", 3000)

        return f"""你是专业小说架构师，负责使用工具构建设计蓝图。

【任务目标】
根据用户需求，调用工具构建设计：
1. set_seed - 设置故事核心种子
2. add_character - 添加角色（主角、配角、反派等）
3. add_location - 添加地点到世界地图
4. set_world - 设置世界观设定
5. add_event - 添加关键事件到时间轴
6. add_chapter - 添加章节大纲
7. complete_design - 完成设计并提交

【约束条件】
- 总章节：约{total_chapters}章
- 每章字数：约{word_count}字
- 必须严格遵循用户需求中的设定
- 设计完成后必须调用 complete_design 提交

【设计流程】
1. 先调用 set_seed 设置故事核心
2. 调用 add_character 添加主要角色（至少主角和反派）
3. 调用 add_location 添加关键地点
4. 调用 set_world 设置世界观（如有特殊设定）
5. 调用 add_event 添加关键情节事件
6. 调用 add_chapter 为每章添加大纲
7. 最后调用 complete_design 完成设计

重要：所有设计数据通过工具调用自动结构化存储，无需输出文本格式。"""

    def _publish_design_progress(self, context: AgentContext, tool_name: str) -> None:
        if not context.live_tracker:
            return

        tool_labels = {
            "set_seed": "设置故事核心",
            "add_character": "添加角色",
            "add_location": "添加地点",
            "set_world": "完善世界观",
            "add_event": "补充关键事件",
            "add_chapter": "生成章节蓝图",
            "add_relation": "补充角色关系",
            "complete_design": "完成设计",
        }
        blueprint = context.extra.get("blueprint", {})
        message = (
            f"正在设计架构：{tool_labels.get(tool_name, tool_name)}"
            f" | 角色{len(context.characters)}"
            f" 地点{len(context.world_map.locations) if context.world_map else 0}"
            f" 章节{len(blueprint)}"
        )
        context.live_tracker.publish_progress("designing", message, running=True)

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行设计任务（工具调用模式）

        Args:
            context: 执行上下文，需要包含:
                - user_input: 用户需求描述
                - extra.get("total_chapters"): 总章节数
                - extra.get("word_count_per_chapter"): 每章字数
                - extra.get("existing_content"): 现有章节内容（用于反向构建设计）

        Returns:
            设计结果
        """
        self._context = context

        user_input = context.user_input
        if not user_input:
            return AgentResult(
                success=False,
                error="缺少用户需求描述",
            )

        # 检查是否是从现有内容构建设计
        existing_content = context.extra.get("existing_content")
        existing_design = context.extra.get("existing_design")
        prompt_preview = user_input
        if existing_design:
            prompt_preview += f"\n\n【现有设计参考】\n{existing_design[:1200]}"
        self._publish_start(
            context,
            context_summary=(
                f"总章节: {context.extra.get('total_chapters', 20)}\n"
                f"用户指导:\n{context.extra.get('user_guidance', '')}"
            ),
            prompt=prompt_preview[:4000],
            meta={"mode": "design"},
        )
        if existing_content:
            result = await self._design_from_content(
                context, existing_content, existing_design
            )
            self._publish_result(
                context,
                status="completed" if result.success else "failed",
                output=result.content[:12000],
                error=result.error,
                meta={"mode": "design_from_content"},
            )
            return result

        # 检查是否是扩展设计任务
        user_guidance = context.extra.get("user_guidance", "")
        global_summary = context.extra.get("global_summary", "")
        is_expand_task = "扩展任务" in user_guidance and global_summary

        if is_expand_task:
            result = await self._expand_design(
                context, existing_design or "", user_guidance
            )
            self._publish_result(
                context,
                status="completed" if result.success else "failed",
                output=result.content[:12000],
                error=result.error,
                meta={"mode": "expand_design"},
            )
            return result

        try:
            # 使用工具调用模式进行设计
            result = await self._design_with_tools(context)
            self._publish_result(
                context,
                status="completed" if result.success else "failed",
                output=result.content[:12000],
                error=result.error,
                meta={"mode": "tool_call_design"},
            )
            return result
        except Exception as e:
            result = AgentResult(
                success=False,
                error=f"设计过程出错: {e!s}",
            )
            self._publish_result(
                context,
                status="failed",
                error=result.error,
                meta={"mode": "tool_call_design"},
            )
            return result

    async def _design_with_tools(self, context: AgentContext) -> AgentResult:
        """使用工具调用模式构建设计"""
        user_input = context.user_input
        total_chapters = context.extra.get("total_chapters", 20)
        word_count = context.extra.get("word_count_per_chapter", 3000)
        user_guidance = context.extra.get("user_guidance", "")

        # 获取设计工具
        tools = get_all_tools(mode="design")

        # 构建用户提示
        user_prompt = f"""请根据以下需求设计小说：

【用户需求】
{user_input}

【约束条件】
- 总章节：{total_chapters}章
- 每章字数：约{word_count}字"""

        if user_guidance:
            user_prompt += f"\n\n【用户额外要求】\n{user_guidance}"

        user_prompt += """

【设计要求】
1. 调用 set_seed 设置故事核心（必填：core）
2. 调用 add_character 添加角色（至少添加主角和反派）
3. 调用 add_location 添加关键地点
4. 如有特殊世界观，调用 set_world 设置
5. 调用 add_event 添加关键情节事件
6. 调用 add_chapter 为每章添加大纲
7. 最后调用 complete_design 完成设计

请开始设计！"""

        # 创建工具调用循环
        loop = ToolCallLoop(
            tools=tools,  # type: ignore[arg-type]
            context=context,
            max_iterations=50,  # 设计可能需要更多迭代
            mode="design",  # 设计模式
            on_tool_call=lambda name, args: (
                self._publish_tool_call(context, tool_name=name, arguments=args),
                self._publish_design_progress(context, name),
            ),
            on_tool_result=lambda name, result: self._publish_tool_result(
                context,
                tool_name=name,
                success=result.success,
                content=result.content,
                issues=result.issues,
                data=result.data if isinstance(result.data, dict) else None,
            ),
            on_retry_wait=lambda retry, wait, err: self._publish_progress(
                context,
                message=f"请求限流或超时，第{retry}次退避等待 {wait} 秒",
                meta={
                    "step": "retry_wait",
                    "retry": retry,
                    "wait_seconds": wait,
                    "error": str(err)[:240],
                },
            ),
        )

        # 执行工具调用
        system_prompt = self._get_design_system_prompt(context)
        final_content = await loop.run(
            provider=self.llm,  # type: ignore[arg-type]
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 检查是否有结构化工具调用数据 - 没有就是失败
        has_seed = bool(context.extra.get("seed"))
        has_blueprint = bool(context.extra.get("blueprint"))
        has_characters = bool(context.characters)

        if not has_seed and not has_blueprint and not has_characters:
            return AgentResult(
                success=False,
                error="设计失败：LLM 未调用任何设计工具，未产生结构化数据。",
            )

        # 从结构化数据生成设计摘要
        final_content = self._generate_summary_from_tools(context)

        # 收集图结构数据
        nodes_to_add = []
        timepoints_to_add = []

        if context.graph:
            for node in context.graph.nodes.values():
                nodes_to_add.append(node)
        if context.timeline:
            for tp in context.timeline.points.values():
                timepoints_to_add.append(tp)

        return AgentResult(
            success=True,
            content=final_content,
            nodes_to_add=nodes_to_add,
            timepoints_to_add=timepoints_to_add,
        )

    def _generate_summary_from_tools(self, context: AgentContext) -> str:
        """从工具调用结果生成设计摘要"""
        lines = ["═══════════════════════════════════════"]
        lines.append("【小说设计蓝图】")
        lines.append("═══════════════════════════════════════")

        # 核心种子
        seed = context.extra.get("seed", {})
        if seed:
            lines.append("\n【核心种子】")
            lines.append(f"├── 故事核心: {seed.get('core', '未设置')}")
            if seed.get("conflict"):
                lines.append(f"├── 核心冲突: {seed['conflict']}")
            if seed.get("theme"):
                lines.append(f"├── 主题内核: {seed['theme']}")
            if seed.get("tone"):
                lines.append(f"└── 情感基调: {seed['tone']}")

        # 世界观
        world = context.extra.get("world", {})
        if world:
            lines.append("\n【世界观设定】")
            lines.append(f"├── 背景: {world.get('setting', '未设置')}")
            if world.get("rules"):
                lines.append(f"├── 规则: {world['rules']}")
            if world.get("factions"):
                lines.append(f"└── 势力: {world['factions']}")

        # 角色 - 详细版
        if context.characters:
            lines.append("\n【角色设定】")
            chars_list = list(context.characters.items())
            for i, (_char_id, char) in enumerate(chars_list):
                is_last = i == len(chars_list) - 1
                prefix = "└──" if is_last else "├──"

                role = char.attrs.get("role", "未知")
                desc = char.attrs.get("description", "")
                personality = char.attrs.get("personality", "")
                background = char.attrs.get("background", "")
                goals = char.attrs.get("goals", "")
                appearances = char.attrs.get("appearances", [])
                abilities = list(char.abilities.keys()) if char.abilities else []
                dialogue_style = char.attrs.get("dialogue_style", "")
                arc = char.attrs.get("arc", "")

                # 角色名和定位
                lines.append(f"{prefix} {char.name}（{role}）")

                # 详细信息
                sub_prefix = "    └──" if is_last else "│   └──"
                sub_prefix_mid = "    ├──" if is_last else "│   ├──"

                if desc:
                    lines.append(f"{sub_prefix_mid} 简介: {desc}")
                if personality:
                    lines.append(f"{sub_prefix_mid} 性格: {personality}")
                if background:
                    lines.append(f"{sub_prefix_mid} 背景: {background}")
                if goals:
                    lines.append(f"{sub_prefix_mid} 目标: {goals}")
                if appearances:
                    if isinstance(appearances, list):
                        ch_str = ", ".join(map(str, appearances))
                        lines.append(f"{sub_prefix_mid} 出场章节: {ch_str}")
                    else:
                        lines.append(f"{sub_prefix_mid} 出场章节: {appearances}")
                if abilities:
                    lines.append(f"{sub_prefix_mid} 能力: {', '.join(abilities)}")
                if dialogue_style:
                    lines.append(f"{sub_prefix_mid} 对话风格: {dialogue_style}")
                if arc:
                    lines.append(f"{sub_prefix} 弧线: {arc}")

        # 角色关系网（关联章节和事件）
        relations = context.extra.get("relations", [])
        if relations:
            lines.append("\n【角色关系演变】")
            for i, rel in enumerate(relations):
                is_last = i == len(relations) - 1
                prefix = "└──" if is_last else "├──"
                sub_prefix = "    └──" if is_last else "│   └──"
                sub_prefix_mid = "    ├──" if is_last else "│   ├──"

                chapter_info = (
                    f"第{rel.get('chapter', '?')}章" if rel.get("chapter") else ""
                )
                rel_type = rel.get("type", "未知")
                char1 = rel.get("char1", "")
                char2 = rel.get("char2", "")
                lines.append(f"{prefix} {char1} ↔ {char2}（{rel_type}）{chapter_info}")
                if rel.get("event"):
                    lines.append(f"{sub_prefix_mid} 触发事件: {rel['event']}")
                if rel.get("change"):
                    lines.append(f"{sub_prefix_mid} 变化: {rel['change']}")
                if rel.get("description"):
                    lines.append(f"{sub_prefix} 描述: {rel['description']}")

        # 地点 - 详细版
        if context.world_map and context.world_map.locations:
            lines.append("\n【世界地图】")
            locs_list = list(context.world_map.locations.items())
            for i, (_loc_id, loc) in enumerate(locs_list):
                is_last = i == len(locs_list) - 1
                prefix = "└──" if is_last else "├──"

                lines.append(f"{prefix} {loc.name}（{loc.type.value}）")

                sub_prefix = "    └──" if is_last else "│   └──"
                sub_prefix_mid = "    ├──" if is_last else "│   ├──"

                if loc.description:
                    lines.append(f"{sub_prefix_mid} 描述: {loc.description}")

                significance = loc.attrs.get("significance", "")
                if significance:
                    lines.append(f"{sub_prefix_mid} 剧情意义: {significance}")

                chapters = loc.attrs.get("chapters", [])
                if chapters:
                    if isinstance(chapters, list):
                        lines.append(
                            f"{sub_prefix} 涉及章节: {', '.join(map(str, chapters))}"
                        )
                    else:
                        lines.append(f"{sub_prefix} 涉及章节: {chapters}")

        # 章节蓝图 - 详细版
        blueprint = context.extra.get("blueprint", {})
        if blueprint:
            lines.append("\n【章节蓝图】")
            ch_nums = sorted(
                blueprint.keys(), key=lambda x: int(x) if str(x).isdigit() else 0
            )
            for i, ch_num in enumerate(ch_nums):
                is_last = i == len(ch_nums) - 1
                prefix = "└──" if is_last else "├──"

                ch = blueprint[ch_num]
                lines.append(f"{prefix} 第{ch_num}章「{ch.get('title', '未命名')}」")

                sub_prefix = "    └──" if is_last else "│   └──"
                sub_prefix_mid = "    ├──" if is_last else "│   ├──"

                if ch.get("summary"):
                    lines.append(f"{sub_prefix_mid} 摘要: {ch['summary']}")
                if ch.get("pov"):
                    lines.append(f"{sub_prefix_mid} 视角: {ch['pov']}")

                # 出场角色
                chars = ch.get("characters", [])
                if chars:
                    if isinstance(chars, list):
                        lines.append(f"{sub_prefix_mid} 出场角色: {', '.join(chars)}")
                    else:
                        lines.append(f"{sub_prefix_mid} 出场角色: {chars}")

                # 涉及地点
                locs = ch.get("locations", [])
                if locs:
                    if isinstance(locs, list):
                        lines.append(f"{sub_prefix_mid} 涉及地点: {', '.join(locs)}")
                    else:
                        lines.append(f"{sub_prefix_mid} 涉及地点: {locs}")

                if ch.get("key_events"):
                    lines.append(f"{sub_prefix_mid} 关键事件: {ch['key_events']}")

                if ch.get("emotional_arc"):
                    lines.append(f"{sub_prefix_mid} 情感弧线: {ch['emotional_arc']}")

                # 场景列表
                scenes = ch.get("scenes", [])
                if scenes:
                    if isinstance(scenes, list):
                        lines.append(f"{sub_prefix_mid} 场景: {', '.join(scenes)}")
                    else:
                        lines.append(f"{sub_prefix_mid} 场景: {scenes}")

                # 冲突点
                conflicts = ch.get("conflicts", [])
                if conflicts:
                    if isinstance(conflicts, list):
                        lines.append(f"{sub_prefix_mid} 冲突: {', '.join(conflicts)}")
                    else:
                        lines.append(f"{sub_prefix_mid} 冲突: {conflicts}")

                # 伏笔
                foreshadows = ch.get("foreshadows", [])
                if foreshadows:
                    if isinstance(foreshadows, list):
                        lines.append(f"{sub_prefix} 伏笔: {', '.join(foreshadows)}")
                    else:
                        lines.append(f"{sub_prefix} 伏笔: {foreshadows}")

        lines.append("\n═══════════════════════════════════════")
        return "\n".join(lines)

    async def _design_from_content(
        self,
        context: AgentContext,
        existing_content: dict[int, str],
        existing_design: str | None = None,
    ) -> AgentResult:
        """
        从现有章节内容反向构建设计（保留现有设计主线）

        Args:
            context: Agent 上下文
            existing_content: 现有章节内容 {章节号: 内容}
            existing_design: 现有设计大纲（作为参考主线）

        Returns:
            设计结果
        """
        # 1. 合并现有章节内容
        content_summary = []
        for ch_num in sorted(existing_content.keys()):
            content = existing_content[ch_num]
            # 截取前2000字以避免太长
            preview = content[:2000] if len(content) > 2000 else content
            content_summary.append(f"【第{ch_num}章】\n{preview}...")

        combined_content = "\n\n".join(content_summary)

        # 2. 构建分析提示
        total_chapters = context.extra.get("total_chapters", 20)
        word_count = context.extra.get("word_count_per_chapter", 3000)
        user_input = context.user_input or "从现有内容反向构建设计"

        # 3. 获取设计工具
        tools = get_all_tools(mode="design")

        # 4. 构建用户提示
        design_ref = ""
        if existing_design:
            design_ref = f"""
【现有设计大纲（必须保留主线！）】
{existing_design}
"""

        user_prompt = f"""请根据以下内容，构建更完整的小说设计：

【小说标题】
{context.extra.get("novel_title", "未知")}

【用户需求】
{user_input}
{design_ref}
【已完成的章节内容】
{combined_content}

【约束条件】
- 已完成章节：{len(existing_content)}章
- 总章节：{total_chapters}章
- 每章字数：约{word_count}字

【设计要求】"""

        # 动态设计要求
        if existing_design:
            design_req = "\n1. 必须保留现有设计的主线和核心设定！"
        else:
            design_req = "\n1. 分析现有章节，推断故事主线"

        user_prompt += f"""{design_req}
2. 调用 set_seed 设置故事核心
3. 调用 add_character 添加角色（从内容中提取，补全对话风格和角色弧线）
4. 调用 add_location 添加地点
5. 调用 add_event 添加关键事件
6. 调用 add_relation 添加角色关系（标注章节节点和变化）
7. 调用 add_chapter 为每章添加详细大纲（场景、冲突、伏笔）
8. 最后调用 complete_design 完成设计

请开始设计！"""

        # 5. 创建工具调用循环
        loop = ToolCallLoop(
            tools=tools,  # type: ignore[arg-type]
            context=context,
            max_iterations=60,  # 可能需要更多迭代
            mode="design",
            on_tool_call=lambda name, args: (
                self._publish_tool_call(context, tool_name=name, arguments=args),
                self._publish_design_progress(context, name),
            ),
            on_tool_result=lambda name, result: self._publish_tool_result(
                context,
                tool_name=name,
                success=result.success,
                content=result.content,
                issues=result.issues,
                data=result.data if isinstance(result.data, dict) else None,
            ),
            on_retry_wait=lambda retry, wait, err: self._publish_progress(
                context,
                message=f"请求限流或超时，第{retry}次退避等待 {wait} 秒",
                meta={
                    "step": "retry_wait",
                    "retry": retry,
                    "wait_seconds": wait,
                    "error": str(err)[:240],
                },
            ),
        )

        # 6. 执行工具调用循环
        system_prompt = self._get_design_system_prompt(context)
        await loop.run(
            provider=self.llm,  # type: ignore[arg-type]
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 7. 检查是否有结构化工具调用数据
        has_seed = bool(context.extra.get("seed"))
        has_blueprint = bool(context.extra.get("blueprint"))
        has_characters = bool(context.characters)

        if not has_seed and not has_blueprint and not has_characters:
            return AgentResult(
                success=False,
                error="设计失败：LLM 未调用任何设计工具，未产生结构化数据。",
            )

        # 8. 生成设计摘要
        summary = self._generate_summary_from_tools(context)

        # 9. 收集图结构数据
        nodes_to_add = []
        timepoints_to_add = []

        if context.graph:
            for node in context.graph.nodes.values():
                nodes_to_add.append(node)
        if context.timeline:
            for tp in context.timeline.points.values():
                timepoints_to_add.append(tp)

        return AgentResult(
            success=True,
            content=summary,
            nodes_to_add=nodes_to_add,
            timepoints_to_add=timepoints_to_add,
        )

    async def _expand_design(
        self, context: AgentContext, existing_design: str, user_guidance: str
    ) -> AgentResult:
        """
        扩展设计：在保留原有设定的基础上扩展章节规划

        Args:
            context: Agent 上下文
            existing_design: 已有的设计内容
            user_guidance: 用户指导（包含扩展任务信息）

        Returns:
            扩展后的设计结果
        """
        import re

        # 解析原有章节数和目标章节数
        match = re.search(r"原有(\d+)章.*扩展到(\d+)章", user_guidance)
        if not match:
            return AgentResult(success=False, error="无法解析扩展任务参数")

        old_chapters = int(match.group(1))
        new_chapters = int(match.group(2))

        # 1. 生成新的章节蓝图
        context.extra["accumulated_design"] = existing_design
        blueprint_result = await self._design_blueprint(context)
        if not blueprint_result.success:
            return blueprint_result

        new_blueprint = blueprint_result.content

        # 2. 解析新章节内容，提取新增元素
        expand_result = await self._extract_expand_elements(
            context, existing_design, new_blueprint, old_chapters, new_chapters
        )

        # 3. 合并原有设计和新的蓝图
        if "【blueprint】" in existing_design:
            # 保留 blueprint 之前的内容
            parts = existing_design.split("【blueprint】")
            final_content = parts[0].strip() + f"\n\n【blueprint】\n{new_blueprint}"
        else:
            # 没有找到 blueprint 标记，追加新的蓝图
            final_content = (
                existing_design.strip() + f"\n\n【blueprint】\n{new_blueprint}"
            )

        return AgentResult(
            success=True,
            content=final_content,
            nodes_to_add=expand_result.get("nodes", []),
            edges_to_add=expand_result.get("edges", []),
            timepoints_to_add=expand_result.get("timepoints", []),
        )

    async def _extract_expand_elements(
        self,
        context: AgentContext,
        existing_design: str,
        new_blueprint: str,
        old_chapters: int,
        new_chapters: int,
    ) -> dict:
        """
        从新的章节蓝图中提取需要添加的元素

        Args:
            context: Agent 上下文
            existing_design: 已有的设计内容
            new_blueprint: 新生成的章节蓝图
            old_chapters: 原有章节数
            new_chapters: 目标章节数

        Returns:
            包含 nodes, edges, timepoints 的字典
        """
        import re

        from src.core.character import CharacterCard
        from src.core.graph import Node, NodeType
        from src.core.graph.timeline import TimePoint
        from src.core.map import Location, LocationType

        nodes: list[Node] = []
        edges: list = []  # 预留给未来的边
        timepoints: list[TimePoint] = []

        # 获取现有角色和地点（避免重复添加）
        existing_characters = (
            set(context.characters.keys()) if context.characters else set()
        )
        existing_locations = set()
        if context.world_map:
            for loc in context.world_map.locations.values():
                existing_locations.add(loc.name)

        # 使用 LLM 提取新增元素
        extract_prompt = f"""请分析以下新章节规划，提取需要添加的元素。

【原有设计】
{existing_design[:2000]}...

【新增章节规划】
{new_blueprint}

【原有章节数】{old_chapters}
【目标章节数】{new_chapters}

请提取：
1. 新角色（不在原有设计中的角色）
2. 新地点（不在原有设计中的地点）
3. 重大事件（新增章节中的关键情节节点）

【输出格式】
## 新增角色
- 角色名 | 身份 | 简介

## 新增地点
- 地点名 | 类型 | 简介

## 新增事件
- 第X章 | 事件名 | 涉及角色 | 事件简介

如果没有新增内容，输出"无新增元素"。"""

        extract_result = await self._call_llm(extract_prompt)

        # 解析 LLM 输出，添加到数据结构
        lines = extract_result.split("\n")
        current_section = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if "## 新增角色" in line:
                current_section = "character"
            elif "## 新增地点" in line:
                current_section = "location"
            elif "## 新增事件" in line:
                current_section = "event"
            elif line.startswith("- "):
                content = line[2:].strip()
                if current_section == "character":
                    parts = content.split("|")
                    if len(parts) >= 2:
                        char_name = parts[0].strip()
                        if char_name and char_name not in existing_characters:
                            char_id = f"char_{char_name}"
                            char_role = parts[1].strip() if len(parts) > 1 else "配角"
                            char_desc = parts[2].strip() if len(parts) > 2 else ""
                            card = CharacterCard(
                                id=char_id,
                                name=char_name,
                                attrs={"role": char_role, "description": char_desc},
                            )
                            context.characters[char_id] = card
                            # 添加角色节点
                            node = Node(
                                id=f"node_{char_id}",
                                type=NodeType.CHARACTER,
                                attrs={"name": char_name, "role": char_role},
                            )
                            nodes.append(node)

                elif current_section == "location":
                    parts = content.split("|")
                    if len(parts) >= 2:
                        loc_name = parts[0].strip()
                        if loc_name and loc_name not in existing_locations:
                            loc_type_str = (
                                parts[1].strip() if len(parts) > 1 else "地点"
                            )
                            # 映射地点类型
                            loc_type_map = {
                                "城市": LocationType.CITY,
                                "城镇": LocationType.CITY,
                                "建筑": LocationType.BUILDING,
                                "区域": LocationType.REGION,
                                "国家": LocationType.REGION,
                            }
                            loc_type = loc_type_map.get(
                                loc_type_str, LocationType.REGION
                            )
                            loc = Location(
                                id=f"loc_{loc_name}",
                                name=loc_name,
                                type=loc_type,
                                description=parts[2].strip() if len(parts) > 2 else "",
                            )
                            if context.world_map:
                                context.world_map.add_location(loc)
                            existing_locations.add(loc_name)

                elif current_section == "event":
                    parts = content.split("|")
                    if len(parts) >= 2:
                        chapter_info = parts[0].strip()
                        event_name = parts[1].strip()
                        # 提取章节号
                        chapter_match = re.search(r"第(\d+)章", chapter_info)
                        if chapter_match:
                            chapter_num = int(chapter_match.group(1))
                            if chapter_num > old_chapters:
                                # 添加时间点和事件节点
                                tp = TimePoint(
                                    id=f"tp_ch{chapter_num}_{event_name}",
                                    label=f"第{chapter_num}章: {event_name}",
                                    attrs={"chapter": chapter_num, "event": event_name},
                                )
                                timepoints.append(tp)

                                event_node = Node(
                                    id=f"event_ch{chapter_num}_{event_name}",
                                    type=NodeType.EVENT,
                                    attrs={
                                        "name": event_name,
                                        "chapter": chapter_num,
                                        "description": parts[3].strip()
                                        if len(parts) > 3
                                        else "",
                                    },
                                    time_point_id=tp.id,
                                )
                                nodes.append(event_node)

        return {"nodes": nodes, "edges": edges, "timepoints": timepoints}

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
        user_guidance = context.extra.get("user_guidance", "")

        # 检查是否是扩展任务
        is_expand = "扩展任务" in user_guidance

        if is_expand:
            # 扩展模式：只规划新增的章节
            import re

            match = re.search(r"原有(\d+)章.*扩展到(\d+)章", user_guidance)
            if match:
                old_chapters = int(match.group(1))
                new_chapters = int(match.group(2))
                prompt = f"""请基于以下信息，为小说扩展章节蓝图。

【用户原始需求】
{context.user_input}

【已有的完整设计】
{accumulated}

【扩展任务】
- 原有{old_chapters}章已规划完成
- 需要扩展到{new_chapters}章
- 请继续规划第{old_chapters + 1}章到第{new_chapters}章
- 保持与已有设定的一致性
- 延续故事主线，发展新的支线

【输出格式】
章节蓝图（续）
│
├── 第{old_chapters + 1}章 [标题]
│   ├── 定位：[角色/事件/主题]
│   ├── 作用：[推进/转折/揭示/铺垫]
│   ├── 悬念：[信息差/道德困境/时间压力]
│   ├── 大纲：[一句话，100字内]
│
├── 第{old_chapters + 2}章 [标题]
│   └── ...
...

如果章节数量较多（超过50章），请分卷规划：
卷名
├── 第X-Y章：[本卷主题]
│   ├── 核心事件
│   ├── 角色发展
│   └── 伏笔埋设

仅输出新增章节的规划内容。"""
            else:
                prompt = f"""请基于已有设计，扩展章节蓝图。

【已有设计】
{accumulated}

【目标】
总共{total_chapters}章

请继续扩展章节规划。"""
        else:
            # 正常设计模式
            # 根据章节数量决定输出格式
            if total_chapters <= 50:
                format_hint = f"""【设计要求】
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
..."""
            else:
                # 大规模章节：分卷规划
                format_hint = f"""【设计要求】
- 必须与角色设定和世界观保持一致
- 总共{total_chapters}章，需要分卷规划
- 每10-30章构成一卷
- 每卷有明确的主题和核心冲突
- 最后1-2卷是高潮和结局

【输出格式】
章节蓝图
│
├── 第一卷 [卷名]（第1-X章）
│   ├── 主题：[本卷核心主题]
│   ├── 核心冲突：[本卷主要矛盾]
│   ├── 开篇事件：[...]
│   ├── 高潮事件：[...]
│   ├── 结尾悬念：[...]
│   └── 关键章节：
│       ├── 第1章 [标题]：[一句话大纲]
│       ├── 第X章 [标题]：[一句话大纲]
│       └── ...
│
├── 第二卷 [卷名]（第X+1-Y章）
│   └── ...
...

总计{total_chapters}章。"""

            prompt = f"""请基于以下信息，设计小说的章节蓝图。

【用户原始需求】
{context.user_input}

【已确定的核心设定】
{accumulated if accumulated else "无"}

{format_hint}

仅输出章节蓝图内容，不要解释。"""

        content = await self._call_llm(prompt, system=self._system_prompt)

        return AgentResult(
            success=True,
            content=content,
        )

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt
