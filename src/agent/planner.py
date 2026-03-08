"""章节规划师 Agent - 负责为作家提炼章节脉络

核心能力：
1. 从海量设计中筛选关键信息
2. 构建起承转合的章节脉络
3. 管理伏笔的埋设、强化和回收
4. 为Writer提供精炼的创作指南（500字左右）
"""

from .base import AgentContext, AgentResult, BaseAgent
from .prompt_loader import prompt_library


class Planner(BaseAgent):
    """章节规划师 Agent"""

    name = "Planner"
    description = (
        "章节规划师，精通起承转合、节奏控制和伏笔布局，为作家提供精炼的章节脉络"
    )
    _system_prompt: str
    _metadata: dict

    def __init__(self, llm=None):
        """初始化规划师"""
        super().__init__(llm=llm)
        self._load_prompts()

    def _load_prompts(self):
        """加载提示词模板"""
        self._system_prompt = prompt_library.get_system_prompt("planner")
        self._metadata = prompt_library.get_metadata("planner")
        self.name = self._metadata.get("name", "Planner")
        self.description = self._metadata.get("description", "")

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行规划任务

        Args:
            context: 执行上下文，需要包含:
                - extra.get("chapter_num"): 当前章节号
                - extra.get("previous_chapter"): 上章内容
                - extra.get("blueprint"): 章节蓝图
                - extra.get("global_summary"): 设计大纲
                - characters: 角色信息
                - world_map: 地点信息

        Returns:
            规划结果（约500字的章节脉络）
        """
        self._context = context

        chapter_num = context.extra.get("chapter_num", 1)
        previous_chapter = context.extra.get("previous_chapter", "")
        blueprint = context.extra.get("blueprint", {})

        try:
            # 筛选当前章节相关信息
            filtered_context = self.filter_context(context, chapter_num, blueprint)

            # 生成章节脉络
            outline = await self._generate_outline(
                chapter_num=chapter_num,
                previous_chapter=previous_chapter,
                filtered_context=filtered_context,
                blueprint=blueprint,
            )

            return AgentResult(
                success=True,
                content=outline,
                chapter_num=chapter_num,
            )

        except Exception as e:
            import traceback

            return AgentResult(
                success=False,
                error=f"规划过程出错: {e!s}\n{traceback.format_exc()}",
            )

    def filter_context(
        self, context: AgentContext, chapter_num: int, blueprint: dict
    ) -> dict:
        """
        筛选当前章节相关的上下文

        Args:
            context: 完整上下文
            chapter_num: 当前章节号
            blueprint: 章节蓝图

        Returns:
            精简的上下文信息
        """
        # 获取本章蓝图
        ch_blueprint = blueprint.get(str(chapter_num), blueprint.get(chapter_num, {}))

        # 筛选角色
        relevant_characters = {}
        ch_characters = ch_blueprint.get("characters", "")
        if ch_characters:
            # 支持字符串或列表
            if isinstance(ch_characters, list):
                char_names = [c.strip() for c in ch_characters]
            else:
                char_names = [c.strip() for c in ch_characters.split(",")]
            for name in char_names:
                if name and name in context.characters:
                    char = context.characters[name]
                    relevant_characters[name] = {
                        "role": char.attrs.get("role", "配角"),
                        "personality": char.personality,
                        "background": char.attrs.get("background", ""),
                        "abilities": (
                            list(char.abilities.keys()) if char.abilities else []
                        ),
                        "dialogue_style": char.attrs.get("dialogue_style", ""),
                    }

        # 筛选地点
        relevant_locations = {}
        ch_locations = ch_blueprint.get("locations", "")
        if ch_locations and context.world_map:
            # 支持字符串或列表
            if isinstance(ch_locations, list):
                loc_names = [loc.strip() for loc in ch_locations]
            else:
                loc_names = [loc.strip() for loc in ch_locations.split(",")]
            for loc_name in loc_names:
                if not loc_name:
                    continue
                for _, loc in context.world_map.locations.items():
                    if loc.name == loc_name:
                        relevant_locations[loc_name] = {
                            "type": loc.type.value,
                            "description": loc.description,
                            "significance": loc.attrs.get("significance", ""),
                        }
                        break

        # 筛选关系变化
        relevant_relations = []
        relations = context.extra.get("relations", [])
        for rel in relations:
            rel_chapter = rel.get("chapter", "")
            # 检查是否是本章的关系变化
            if rel_chapter:
                try:
                    # 支持单章节或章节范围
                    if "-" in str(rel_chapter):
                        # 范围，如 "5-10"
                        parts = rel_chapter.split("-")
                        if int(parts[0]) <= chapter_num <= int(parts[1]):
                            relevant_relations.append(rel)
                    elif int(rel_chapter) == chapter_num:
                        relevant_relations.append(rel)
                except (ValueError, TypeError):
                    pass

        return {
            "chapter_blueprint": ch_blueprint,
            "characters": relevant_characters,
            "locations": relevant_locations,
            "relations": relevant_relations,
        }

    async def _generate_outline(
        self,
        chapter_num: int,
        previous_chapter: str,
        filtered_context: dict,
        blueprint: dict,
    ) -> str:
        """
        生成章节脉络

        Args:
            chapter_num: 当前章节号
            previous_chapter: 上章内容
            filtered_context: 筛选后的上下文
            blueprint: 章节蓝图

        Returns:
            章节脉络（约500字）
        """
        ch_blueprint = filtered_context["chapter_blueprint"]

        # 构建提示
        if chapter_num == 1:
            return await self._plan_first_chapter(filtered_context, ch_blueprint)
        else:
            return await self._plan_chapter(
                chapter_num, previous_chapter, filtered_context, ch_blueprint, blueprint
            )

    async def _plan_first_chapter(
        self, filtered_context: dict, ch_blueprint: dict
    ) -> str:
        """规划第一章"""

        characters = filtered_context["characters"]
        locations = filtered_context["locations"]

        # 构建角色信息
        char_info = ""
        for name, info in characters.items():
            char_info += f"- {name}（{info['role']}）：{info.get('personality', '')}\n"

        # 构建地点信息
        loc_info = ""
        for name, info in locations.items():
            loc_info += f"- {name}（{info['type']}）：{info.get('description', '')}\n"

        user_prompt = f"""请为第一章规划脉络。

【本章蓝图】
- 标题：{ch_blueprint.get('title', '未命名')}
- 摘要：{ch_blueprint.get('summary', '')}
- 视角：{ch_blueprint.get('pov', '')}
- 关键事件：{ch_blueprint.get('key_events', '')}

【出场角色】
{char_info or '无'}

【涉及地点】
{loc_info or '无'}

【规划要求】
1. 第一章需要开篇抓人（前500字有冲突/悬念）
2. 自然引入主角和世界观
3. 埋下至少一个贯穿全文的伏笔
4. 结尾留悬念钩子

请按模板输出第一章脉络（约500字）。"""

        return await self._call_llm(
            prompt=user_prompt,
            system=self._system_prompt,
            temperature=0.7,
            max_tokens=800,
        )

    async def _plan_chapter(
        self,
        chapter_num: int,
        previous_chapter: str,
        filtered_context: dict,
        ch_blueprint: dict,
        blueprint: dict,
    ) -> str:
        """规划后续章节"""

        characters = filtered_context["characters"]
        locations = filtered_context["locations"]
        relations = filtered_context["relations"]

        # 上章结尾（取最后500字）
        prev_ending = previous_chapter[-500:] if previous_chapter else "无"

        # 构建角色信息
        char_info = ""
        for name, info in characters.items():
            char_info += f"- {name}（{info['role']}）：{info.get('personality', '')}\n"
            if info.get("dialogue_style"):
                char_info += f"  对话风格：{info['dialogue_style']}\n"

        # 构建地点信息
        loc_info = ""
        for name, info in locations.items():
            loc_info += f"- {name}（{info['type']}）：{info.get('description', '')}\n"

        # 构建关系变化
        rel_info = ""
        for rel in relations:
            char1 = rel.get("char1", "")
            char2 = rel.get("char2", "")
            rel_type = rel.get("type", "")
            change = rel.get("change", "")
            rel_info += f"- {char1} ↔ {char2}（{rel_type}）：{change}\n"

        # 下一章信息（用于铺垫）
        next_blueprint = blueprint.get(
            str(chapter_num + 1), blueprint.get(chapter_num + 1, {})
        )
        next_info = ""
        if next_blueprint:
            next_info = f"""
【下章预告】
- 标题：{next_blueprint.get('title', '')}
- 摘要：{next_blueprint.get('summary', '')}"""

        user_prompt = f"""请为第{chapter_num}章规划脉络。

【上章结尾】
{prev_ending}

【本章蓝图】
- 标题：{ch_blueprint.get('title', '未命名')}
- 摘要：{ch_blueprint.get('summary', '')}
- 视角：{ch_blueprint.get('pov', '')}
- 关键事件：{ch_blueprint.get('key_events', '')}
- 情感弧线：{ch_blueprint.get('emotional_arc', '')}
- 场景：{ch_blueprint.get('scenes', '')}
- 冲突：{ch_blueprint.get('conflicts', '')}
- 伏笔：{ch_blueprint.get('foreshadows', '')}

【出场角色】
{char_info or '无'}

【涉及地点】
{loc_info or '无'}

【本章关系变化】
{rel_info or '无'}
{next_info}

【规划要求】
1. 承接上章结尾，自然过渡
2. 推进情节，有实质进展
3. 处理伏笔任务（埋设/强化/回收）
4. 结尾留悬念钩子

请按模板输出第{chapter_num}章脉络（约500字）。"""

        return await self._call_llm(
            prompt=user_prompt,
            system=self._system_prompt,
            temperature=0.7,
            max_tokens=800,
        )

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt
