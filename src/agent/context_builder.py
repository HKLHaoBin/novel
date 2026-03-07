"""上下文构建器 - 将图、时间轴、地图转换为结构化文本

为 Agent 提供清晰的上下文指导，确保写作时有据可依
"""

from typing import Any


def build_full_context(context: Any) -> str:
    """
    构建完整上下文文本

    Args:
        context: AgentContext

    Returns:
        结构化的上下文描述
    """
    from src.core.graph import NodeType

    parts = []

    # ========== 设计大纲（优先级最高）==========
    if hasattr(context, "extra") and context.extra.get("global_summary"):
        parts.append("═" * 40)
        parts.append("【小说设计大纲】")
        parts.append("═" * 40)
        parts.append(context.extra["global_summary"])

    # ========== 世界观 ==========
    if context.graph:
        world_nodes = context.graph.find_nodes_by_type(NodeType.WORLD)
        if world_nodes:
            parts.append("═" * 40)
            parts.append("【世界观设定】")
            parts.append("═" * 40)

            for node in world_nodes:
                name = node.attrs.get("name", node.id)
                parts.append(f"\n{name}")

                # 规则体系
                rules = node.attrs.get("rules", [])
                if rules:
                    parts.append("├──规则体系")
                    for i, rule in enumerate(
                        rules if isinstance(rules, list) else [rules]
                    ):
                        marker = "│  └──" if i == len(rules) - 1 else "│  ├──"
                        parts.append(f"{marker}{rule}")

                # 势力分布
                forces = node.attrs.get("forces", [])
                if forces:
                    parts.append("├──主要势力")
                    for i, force in enumerate(
                        forces if isinstance(forces, list) else [forces]
                    ):
                        marker = "│  └──" if i == len(forces) - 1 else "│  ├──"
                        parts.append(f"{marker}{force}")

                # 描述
                desc = node.attrs.get("description", "")
                if desc:
                    parts.append(f"└──描述: {desc}")

    # ========== 主线/支线 ==========
    if context.graph:
        main_plots = context.graph.find_nodes_by_type(NodeType.MAIN_PLOT)
        sub_plots = context.graph.find_nodes_by_type(NodeType.SUB_PLOT)

        if main_plots or sub_plots:
            parts.append("\n" + "═" * 40)
            parts.append("【情节线索】")
            parts.append("═" * 40)

            if main_plots:
                parts.append("\n主线")
                for node in main_plots:
                    theme = node.attrs.get("theme", "")
                    conflict = node.attrs.get("conflict", "")
                    stages = node.attrs.get("stages", [])

                    parts.append(f"├──主题: {theme}")
                    parts.append(f"├──核心冲突: {conflict}")
                    if stages:
                        parts.append("└──阶段")
                        for j, stage in enumerate(
                            stages if isinstance(stages, list) else [stages]
                        ):
                            marker = "   └──" if j == len(stages) - 1 else "   ├──"
                            parts.append(f"{marker}{stage}")

            if sub_plots:
                parts.append("\n支线")
                for node in sub_plots:
                    name = node.attrs.get("name", node.id)
                    parts.append(f"├──{name}")

    # ========== 角色卡 ==========
    if context.characters:
        parts.append("\n" + "═" * 40)
        parts.append("【角色信息】")
        parts.append("═" * 40)

        for char in context.characters.values():
            parts.append(f"\n{char.name}")
            parts.append(f"├──基础: {char.gender}, {char.age}")
            parts.append(f"├──性格: {char.personality}")

            # 能力
            public_abilities = char.get_public_abilities()
            hidden_abilities = char.get_hidden_abilities()
            future_abilities = char.get_future_abilities()

            if public_abilities:
                parts.append("├──已知能力")
                for i, ab in enumerate(public_abilities):
                    marker = (
                        "│  └──"
                        if i == len(public_abilities) - 1
                        and not hidden_abilities
                        and not future_abilities
                        else "│  ├──"
                    )
                    parts.append(
                        f"{marker}{ab.name}: {ab.description[:30]}..."
                        if len(ab.description) > 30
                        else f"{marker}{ab.name}: {ab.description}"
                    )

            if hidden_abilities:
                parts.append("├──隐藏能力（读者未知）")
                for i, ab in enumerate(hidden_abilities):
                    marker = (
                        "│  └──"
                        if i == len(hidden_abilities) - 1 and not future_abilities
                        else "│  ├──"
                    )
                    parts.append(f"{marker}{ab.name}")

            if future_abilities:
                parts.append("├──未来能力（待解锁）")
                for i, ab in enumerate(future_abilities):
                    marker = "│  └──" if i == len(future_abilities) - 1 else "│  ├──"
                    parts.append(f"{marker}{ab.name}")

            # 最近行为
            if char.last_action:
                parts.append(f"├──最近行为: {char.last_action}")
                if char.last_result:
                    parts.append(f"├──行为结果: {char.last_result}")

            # 备注
            if char.notes:
                parts.append("└──备注")
                for note in char.notes[-3:]:  # 最近3条
                    parts.append(
                        f"   └──{note[:50]}..." if len(note) > 50 else f"   └──{note}"
                    )
            else:
                parts.append("└──备注: 无")

    # ========== 时间轴 ==========
    if context.timeline:
        points = context.timeline.get_ordered_points()
        if points:
            parts.append("\n" + "═" * 40)
            parts.append("【时间轴】")
            parts.append("═" * 40)
            parts.append("")

            for i, p in enumerate(points):
                is_current = p.id == context.current_point_id
                marker = "└──" if i == len(points) - 1 else "├──"
                current_mark = " ◀当前" if is_current else ""
                parts.append(f"{marker}{p.label}{current_mark}")

                # 显示角色位置
                if p.character_locations:
                    for char_id, loc_id in p.character_locations.items():
                        char = context.characters.get(char_id)
                        loc = (
                            context.world_map.get_location(loc_id)
                            if context.world_map
                            else None
                        )
                        prefix = "   └──" if i == len(points) - 1 else "│  └──"
                        char_name = char.name if char else char_id
                        loc_name = loc.name if loc else loc_id
                        parts.append(f"{prefix}{char_name} 在 {loc_name}")

    # ========== 地图 ==========
    if context.world_map and context.world_map.locations:
        parts.append("\n" + "═" * 40)
        parts.append("【地图结构】")
        parts.append("═" * 40)
        parts.append("")

        # 找出顶级地点（无父级）
        root_locs = [
            loc for loc in context.world_map.locations.values() if not loc.parent_id
        ]

        def render_location(loc, prefix=""):
            """递归渲染地点树"""
            lines = []
            children = context.world_map.get_children(loc.id)

            lines.append(f"{prefix}├──{loc.name} ({loc.type.value})")

            for i, child in enumerate(children):
                child_prefix = prefix + ("   " if i == len(children) - 1 else "│  ")
                lines.extend(render_location(child, child_prefix))

            return lines

        for loc in root_locs:
            parts.extend(render_location(loc))

    # ========== 当前时间点详细信息 ==========
    if context.current_point_id and context.timeline:
        point = context.timeline.get_point(context.current_point_id)
        if point:
            parts.append("\n" + "═" * 40)
            parts.append(f"【当前时间点: {point.label}】")
            parts.append("═" * 40)
            parts.append("")

            # 所有角色位置
            parts.append("角色位置分布:")
            if point.character_locations:
                for char_id, loc_id in point.character_locations.items():
                    char = context.characters.get(char_id)
                    loc = (
                        context.world_map.get_location(loc_id)
                        if context.world_map
                        else None
                    )
                    char_name = char.name if char else char_id
                    loc_name = loc.name if loc else loc_id
                    parts.append(f"├──{char_name} → {loc_name}")
            else:
                parts.append("└──暂无位置记录")

            # 该时间点的节点
            if point.node_ids:
                parts.append("\n涉及节点:")
                for i, node_id in enumerate(point.node_ids):
                    node = context.graph.get_node(node_id) if context.graph else None
                    marker = "└──" if i == len(point.node_ids) - 1 else "├──"
                    node_info = f"{node_id} ({node.type.value})" if node else node_id
                    parts.append(f"{marker}{node_info}")

    return "\n".join(parts)


def build_quick_reference(context: Any) -> str:
    """
    构建快速参考卡（精简版）

    用于作家快速查阅关键信息
    """
    parts = ["【快速参考】"]

    # 当前时间点
    if context.current_point_id and context.timeline:
        point = context.timeline.get_point(context.current_point_id)
        if point:
            parts.append(f"时间: {point.label}")

    # 角色位置速查
    if context.timeline and context.current_point_id:
        point = context.timeline.get_point(context.current_point_id)
        if point and point.character_locations:
            locs = []
            for char_id, loc_id in point.character_locations.items():
                char = context.characters.get(char_id)
                loc = (
                    context.world_map.get_location(loc_id)
                    if context.world_map
                    else None
                )
                char_name = char.name if char else char_id
                loc_name = loc.name if loc else loc_id
                locs.append(f"{char_name}@{loc_name}")
            parts.append(f"位置: {', '.join(locs)}")

    # 待处理事项
    pending = []
    if context.characters:
        for char in context.characters.values():
            if char.last_action and not char.last_result:
                pending.append(f"{char.name}待处理")
            if char.get_future_abilities():
                pending.append(f"{char.name}有待解锁能力")

    if pending:
        parts.append(f"待处理: {', '.join(pending[:3])}")

    return "\n".join(parts)


def build_uncertainty_guidance() -> str:
    """
    构建不确定时的查询引导

    当作家拿不定主意时，提示使用工具查询
    """
    from .tools import build_tools_description

    return f"""
═══════════════════════════════════════════════════════
⚠️ 当你不确定时，请使用工具查询！

【常见不确定场景】
├── 不确定角色当前在哪？→ 使用 query_location 查询地点
├── 不确定角色有什么能力？→ 使用 query_character 查询角色
├── 不确定角色之间的关系？→ 使用 query_relationships 查询关系
├── 不确定时间顺序？→ 使用 query_timeline 查询时间轴
├── 不确定是否一致？→ 使用 check_consistency 检查一致性
└── 不知道下一步写什么？→ 使用 suggest_next 获取建议

{build_tools_description()}

【使用示例】
当你在写作过程中需要确认信息时，可以这样思考：
"我需要确认张三现在在哪里" → 先查询位置再写作
"我需要确认李四的能力是否已公开" → 先查询角色再决定是否展示
"我需要确认王五和张三的关系" → 先查询关系再写对话

记住：宁可多查询一次，也不要写出矛盾的内容！
═══════════════════════════════════════════════════════
"""
