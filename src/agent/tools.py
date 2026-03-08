"""Agent 工具系统 - 提供查询和更新能力

工具列表：
1. 查询类（Query）
   - query_character: 查询角色信息
   - query_location: 查询地点信息
   - query_timeline: 查询时间点信息
   - query_events: 查询事件
   - query_relationships: 查询角色关系

2. 更新类（Update）
   - update_character: 更新角色状态
   - update_location: 更新角色位置
   - add_event: 添加新事件

3. 辅助类（Helper）
   - check_consistency: 快速一致性检查
   - suggest_next: 建议下一步发展
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolType(Enum):
    """工具类型"""

    QUERY = "query"  # 查询类
    UPDATE = "update"  # 更新类
    HELPER = "helper"  # 辅助类


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    content: str
    issues: list[str] = field(default_factory=list)
    data: Any = None
    suggestions: list[str] = field(default_factory=list)


@dataclass
class Tool:
    """工具定义"""

    name: str
    description: str
    tool_type: ToolType
    parameters: dict[str, str]  # 参数名 -> 参数描述
    execute: Callable


# =============== 章节查询工具 ===============


def complete(context: Any, content: str = "") -> ToolResult:
    """
    完成任务并提交最终内容

    Args:
        context: AgentContext
        content: 最终完成的章节内容

    Returns:
        完成确认
    """
    return ToolResult(
        success=True,
        content="任务已完成",
        data={"final_content": content, "completed": True},
    )


async def query_previous_chapter(
    context: Any, chapter_num: int | str | None = None
) -> ToolResult:
    """
    查询已完成章节的内容

    Args:
        context: AgentContext
        chapter_num: 章节号（可选，默认查询上一章）

    Returns:
        章节内容
    """
    # 从 context.extra 获取状态管理器和小说标题
    state_manager = context.extra.get("state_manager")
    novel_title = context.extra.get("novel_title")
    current_chapter = context.extra.get("chapter_num", 1)

    # 确保类型正确
    if isinstance(chapter_num, str):
        chapter_num = int(chapter_num) if chapter_num.isdigit() else None
    if isinstance(current_chapter, str):
        current_chapter = int(current_chapter) if current_chapter.isdigit() else 1

    # 确定要查询的章节
    target_chapter = chapter_num if chapter_num is not None else current_chapter - 1

    if target_chapter < 1:
        return ToolResult(
            success=False,
            content="没有更早的章节",
            suggestions=["这是第一章，没有前文内容"],
        )

    # 尝试从知识库获取
    if context.knowledge:
        try:
            memories = await context.knowledge.retrieve(
                f"第{target_chapter}章", top_k=3
            )
            if memories:
                content = "\n\n".join(m.get("content", "") for m in memories)
                return ToolResult(
                    success=True,
                    content=f"第{target_chapter}章内容（从知识库）:\n{content[:2000]}..."
                    if len(content) > 2000
                    else f"第{target_chapter}章内容:\n{content}",
                )
        except Exception:
            pass

    # 从文件系统获取
    if state_manager and novel_title:
        try:
            content = state_manager.load_chapter(novel_title, target_chapter)
            if content:
                return ToolResult(
                    success=True,
                    content=f"第{target_chapter}章内容:\n{content[:2000]}..."
                    if len(content) > 2000
                    else f"第{target_chapter}章内容:\n{content}",
                )
        except Exception:
            pass

    # 从 context.extra 获取已完成的章节
    completed_chapters = context.extra.get("completed_chapters", {})
    if str(target_chapter) in completed_chapters:
        ch_content = completed_chapters[str(target_chapter)]
        return ToolResult(
            success=True,
            content=f"第{target_chapter}章内容:\n{ch_content[:2000]}..."
            if len(ch_content) > 2000
            else f"第{target_chapter}章内容:\n{ch_content}",
        )

    return ToolResult(
        success=False,
        content=f"未找到第{target_chapter}章内容",
        suggestions=["该章节可能尚未完成", "检查章节号是否正确"],
    )


async def query_chapter_outline(
    context: Any, chapter_num: int | str | None = None
) -> ToolResult:
    """
    查询章节大纲

    Args:
        context: AgentContext
        chapter_num: 章节号（可选，默认查询当前章节）

    Returns:
        章节大纲
    """
    # 从 context.extra 获取信息
    current_chapter = context.extra.get("chapter_num", 1)

    # 确保类型正确
    if isinstance(chapter_num, str):
        chapter_num = int(chapter_num) if chapter_num.isdigit() else None
    if isinstance(current_chapter, str):
        current_chapter = int(current_chapter) if current_chapter.isdigit() else 1

    target_chapter = chapter_num if chapter_num is not None else current_chapter
    global_summary = context.extra.get("global_summary", "")
    total_chapters = context.extra.get("total_chapters", 0)

    # 尝试从知识库获取大纲
    if context.knowledge:
        try:
            memories = await context.knowledge.retrieve(
                f"章节大纲 第{target_chapter}章", top_k=2
            )
            if memories:
                outline = "\n".join(m.get("content", "") for m in memories)
                return ToolResult(
                    success=True, content=f"第{target_chapter}章大纲:\n{outline}"
                )
        except Exception:
            pass

    # 从全局设计中提取
    if global_summary:
        lines = global_summary.split("\n")
        outline_lines = []
        in_chapter = False
        chapter_marker = f"第{target_chapter}章"

        for line in lines:
            if chapter_marker in line or f"章节{target_chapter}" in line:
                in_chapter = True
            elif in_chapter and (
                "第" in line and "章" in line and chapter_marker not in line
            ):
                break
            elif in_chapter:
                outline_lines.append(line)

        if outline_lines:
            return ToolResult(
                success=True,
                content=f"第{target_chapter}章大纲:\n" + "\n".join(outline_lines[:20]),
            )

    # 返回通用指导
    return ToolResult(
        success=True,
        content=f"第{target_chapter}章大纲:\n（未找到具体大纲，请参考全局设定自由发挥）\n\n全局设定摘要:\n{global_summary[:1000]}..."
        if global_summary
        else f"第{target_chapter}章大纲:\n未找到大纲，请根据上下文自由创作",
        suggestions=[
            f"当前进度: 第{current_chapter}/{total_chapters}章",
            "可以先用 query_previous_chapter 查看前文",
            "可以用 query_timeline 了解时间线",
        ],
    )


async def query_all_chapters(context: Any) -> ToolResult:
    """
    查询所有已完成章节的摘要

    Args:
        context: AgentContext

    Returns:
        所有章节摘要
    """
    context.extra.get("completed_chapters", {})
    state_manager = context.extra.get("state_manager")
    novel_title = context.extra.get("novel_title")

    summaries = []

    # 从知识库获取各章摘要
    if context.knowledge:
        try:
            # 获取章节列表
            current = context.extra.get("chapter_num", 1)
            for ch in range(1, current):
                memories = await context.knowledge.retrieve(f"第{ch}章摘要", top_k=1)
                if memories:
                    summary = memories[0].get(
                        "summary", memories[0].get("content", "")
                    )[:300]
                    summaries.append(f"第{ch}章: {summary}")
        except Exception:
            pass

    if not summaries and state_manager and novel_title:
        # 尝试从文件系统
        chapters = state_manager.list_chapters(novel_title)
        for ch in chapters:
            summaries.append(f"第{ch['chapter_num']}章: {ch.get('title', '')}")

    if not summaries:
        return ToolResult(
            success=False, content="暂无已完成章节", suggestions=["开始创作第一章"]
        )

    return ToolResult(
        success=True,
        content="已完成章节摘要:\n" + "\n".join(f"├──{s}" for s in summaries),
    )


# =============== 查询类工具 ===============


def query_character(context: Any, character_id: str) -> ToolResult:
    """
    查询角色详细信息

    Args:
        context: AgentContext
        character_id: 角色ID或名称

    Returns:
        角色完整信息
    """
    # 安全检查
    if not context.characters:
        return ToolResult(
            success=False,
            content="暂无角色信息",
            suggestions=["小说尚未创建角色，请先完成设计阶段"],
        )

    char = context.characters.get(character_id)

    # 支持按名称查询
    if not char:
        for cid, c in context.characters.items():
            if hasattr(c, "name") and c.name == character_id:
                char = c
                character_id = cid
                break

    if not char:
        available_names = []
        for c in context.characters.values():
            if hasattr(c, "name"):
                available_names.append(c.name)
        return ToolResult(
            success=False,
            content=f"未找到角色: {character_id}",
            suggestions=[f"可用角色: {', '.join(available_names)}"]
            if available_names
            else ["暂无角色"],
        )

    # 构建结构化输出
    lines = [
        f"角色：{char.name}",
        "├──基础信息",
        f"│  ├──性别: {char.gender if hasattr(char, 'gender') else '未知'}",
        f"│  ├──年龄: {char.age if hasattr(char, 'age') else '未知'}",
        f"│  └──性格: {char.personality if hasattr(char, 'personality') else '未知'}",
        "├──能力",
    ]

    abilities = char.abilities if hasattr(char, "abilities") else {}
    for ability in abilities.values() if abilities else []:
        status = []
        if hasattr(ability, "is_future") and ability.is_future:
            status.append("未来获得")
        elif hasattr(ability, "is_public") and not ability.is_public:
            status.append("未公开")
        else:
            status.append("已公开")

        status_str = f"（{', '.join(status)}）" if status else ""
        desc = ability.description if hasattr(ability, "description") else ""
        name = ability.name if hasattr(ability, "name") else str(ability)
        lines.append(f"│  ├──{name}{status_str}: {desc}")

    notes = char.notes if hasattr(char, "notes") else []
    lines.append("├──备注")
    for note in notes[-5:]:  # 最近5条备注
        lines.append(f"│  └──{note}")

    last_action = char.last_action if hasattr(char, "last_action") else ""
    last_result = char.last_result if hasattr(char, "last_result") else ""
    lines.append(f"├──最近行为: {last_action}")
    lines.append(f"└──行为结果: {last_result}")

    return ToolResult(success=True, content="\n".join(lines), data=char)


def query_location(context: Any, location_id: str) -> ToolResult:
    """
    查询地点详细信息

    Args:
        context: AgentContext
        location_id: 地点ID或名称

    Returns:
        地点完整信息及当前在场角色
    """
    if not context.world_map:
        return ToolResult(success=False, content="暂无地图信息")

    loc = context.world_map.get_location(location_id)

    # 支持按名称查询
    if not loc:
        loc = context.world_map.find_location_by_name(location_id)

    if not loc:
        available_names = []
        if hasattr(context.world_map, "locations"):
            for location in context.world_map.locations.values():
                if hasattr(location, "name"):
                    available_names.append(location.name)
        return ToolResult(
            success=False,
            content=f"未找到地点: {location_id}",
            suggestions=[f"可用地点: {', '.join(available_names)}"]
            if available_names
            else ["暂无地点"],
        )

    # 构建结构化输出
    loc_type = loc.type if hasattr(loc, "type") else None
    loc_type_value = (
        loc_type.value if loc_type and hasattr(loc_type, "value") else "未知"
    )

    lines = [
        f"地点：{loc.name if hasattr(loc, 'name') else location_id}",
        f"├──类型: {loc_type_value}",
        f"├──描述: {loc.description if hasattr(loc, 'description') else '无'}",
    ]

    # 父级地点
    parent_id = loc.parent_id if hasattr(loc, "parent_id") else None
    if parent_id and hasattr(context.world_map, "get_location"):
        parent = context.world_map.get_location(parent_id)
        if parent and hasattr(parent, "name"):
            lines.append(f"├──上级地点: {parent.name}")

    # 子级地点
    if hasattr(context.world_map, "get_children"):
        children = context.world_map.get_children(
            loc.id if hasattr(loc, "id") else location_id
        )
        if children:
            lines.append("├──下级地点")
            for i, child in enumerate(children):
                marker = "└──" if i == len(children) - 1 else "│  ├──"
                child_name = child.name if hasattr(child, "name") else str(child)
                lines.append(f"{marker}{child_name}")

    # 相邻地点
    if hasattr(context.world_map, "get_adjacent_locations"):
        adjacent = context.world_map.get_adjacent_locations(
            loc.id if hasattr(loc, "id") else location_id
        )
        if adjacent:
            lines.append("├──相邻地点")
            adj_names = [a.name if hasattr(a, "name") else str(a) for a in adjacent]
            lines.append(f"│  └──{', '.join(adj_names)}")

    # 当前在场角色
    characters_here = []
    current_point_id = (
        context.current_point_id if hasattr(context, "current_point_id") else None
    )
    if context.timeline and current_point_id and hasattr(context.timeline, "get_point"):
        point = context.timeline.get_point(current_point_id)
        if point and hasattr(point, "character_locations"):
            loc_id = loc.id if hasattr(loc, "id") else location_id
            for char_id, lid in point.character_locations.items():
                if lid == loc_id:
                    char = (
                        context.characters.get(char_id) if context.characters else None
                    )
                    characters_here.append(
                        char.name if char and hasattr(char, "name") else char_id
                    )

    if characters_here:
        lines.append("└──当前在场角色")
        lines.append(f"   └──{', '.join(characters_here)}")
    else:
        lines.append("└──当前在场角色: 无")

    return ToolResult(success=True, content="\n".join(lines), data=loc)


def query_timeline(context: Any, point_id: str | None = None) -> ToolResult:
    """
    查询时间轴信息

    Args:
        context: AgentContext
        point_id: 时间点ID（可选，不提供则返回整个时间轴）

    Returns:
        时间轴结构化信息
    """
    if not context.timeline:
        return ToolResult(success=False, content="暂无时间轴信息")

    current_point_id = (
        context.current_point_id if hasattr(context, "current_point_id") else None
    )

    if point_id:
        if not hasattr(context.timeline, "get_point"):
            return ToolResult(success=False, content="时间轴不支持查询")

        point = context.timeline.get_point(point_id)
        if not point:
            return ToolResult(success=False, content=f"未找到时间点: {point_id}")

        prev_point = (
            context.timeline.get_prev(point_id)
            if hasattr(context.timeline, "get_prev")
            else None
        )
        next_point = (
            context.timeline.get_next(point_id)
            if hasattr(context.timeline, "get_next")
            else None
        )

        lines = [
            f"时间点：{point.label if hasattr(point, 'label') else point_id}",
        ]
        prev_label = prev_point.label if prev_point else "无"
        if prev_point and hasattr(prev_point, "label"):
            prev_label = prev_point.label
        lines.append(f"├──前一时间点: {prev_label}")
        next_label = next_point.label if next_point else "无"
        if next_point and hasattr(next_point, "label"):
            next_label = next_point.label
        lines.append(f"├──后一时间点: {next_label}")
        lines.append("├──涉及节点")

        node_ids = point.node_ids if hasattr(point, "node_ids") else []
        for i, node_id in enumerate(node_ids):
            marker = "│  └──" if i == len(node_ids) - 1 else "│  ├──"
            node = (
                context.graph.get_node(node_id)
                if context.graph and hasattr(context.graph, "get_node")
                else None
            )
            node_type = (
                node.type.value
                if node and hasattr(node, "type") and hasattr(node.type, "value")
                else "未知"
            )
            lines.append(f"{marker}{node_id} ({node_type})")

        lines.append("└──角色位置")
        char_locs = (
            point.character_locations if hasattr(point, "character_locations") else {}
        )
        for char_id, loc_id in char_locs.items():
            char = context.characters.get(char_id) if context.characters else None
            loc = (
                context.world_map.get_location(loc_id)
                if context.world_map and hasattr(context.world_map, "get_location")
                else None
            )
            char_name = char.name if char and hasattr(char, "name") else char_id
            loc_name = loc.name if loc and hasattr(loc, "name") else loc_id
            lines.append(f"   └──{char_name} 在 {loc_name}")

        return ToolResult(success=True, content="\n".join(lines), data=point)

    else:
        # 返回整个时间轴
        if not hasattr(context.timeline, "get_ordered_points"):
            return ToolResult(success=False, content="时间轴不支持列表查询")

        points = context.timeline.get_ordered_points()
        lines = ["时间轴"]

        for i, p in enumerate(points):
            is_current = hasattr(p, "id") and p.id == current_point_id
            marker = "└──" if i == len(points) - 1 else "├──"
            current_mark = " ★当前" if is_current else ""
            label = p.label if hasattr(p, "label") else str(p)
            lines.append(f"{marker}{label}{current_mark}")

            # 显示该时间点的角色位置
            char_locs = (
                p.character_locations if hasattr(p, "character_locations") else {}
            )
            if char_locs:
                for char_id, loc_id in char_locs.items():
                    char = (
                        context.characters.get(char_id) if context.characters else None
                    )
                    loc = (
                        context.world_map.get_location(loc_id)
                        if context.world_map
                        and hasattr(context.world_map, "get_location")
                        else None
                    )
                    prefix = "   └──" if i == len(points) - 1 else "│  └──"
                    char_name = char.name if char and hasattr(char, "name") else char_id
                    loc_name = loc.name if loc and hasattr(loc, "name") else loc_id
                    lines.append(f"{prefix}{char_name} 在 {loc_name}")

        return ToolResult(success=True, content="\n".join(lines))


def query_events(context: Any, event_type: str | None = None) -> ToolResult:
    """
    查询事件

    Args:
        context: AgentContext
        event_type: 事件类型过滤（可选）

    Returns:
        事件列表
    """
    if not context.graph:
        return ToolResult(success=False, content="无图结构信息")

    from src.core.graph import NodeType

    events = context.graph.find_nodes_by_type(NodeType.EVENT)

    if not events:
        return ToolResult(success=False, content="暂无事件记录")

    lines = ["事件列表"]

    for i, event in enumerate(events):
        marker = "└──" if i == len(events) - 1 else "├──"
        name = event.attrs.get("name", event.id)
        desc = event.attrs.get("description", "")
        time_point = ""

        if event.time_point_id and context.timeline:
            point = context.timeline.get_point(event.time_point_id)
            if point:
                time_point = f" [{point.label}]"

        lines.append(f"{marker}{name}{time_point}")
        if desc:
            prefix = "   " if i == len(events) - 1 else "│  "
            lines.append(
                f"{prefix}└──{desc[:50]}..." if len(desc) > 50 else f"{prefix}└──{desc}"
            )

    return ToolResult(success=True, content="\n".join(lines))


def query_relationships(context: Any, character_id: str) -> ToolResult:
    """
    查询角色关系网

    Args:
        context: AgentContext
        character_id: 角色ID或名称

    Returns:
        角色的关系网络
    """
    if not context.graph:
        return ToolResult(success=False, content="无图结构信息")

    from src.core.graph import NodeType

    # 找到角色节点
    char_node = None
    char_nodes = context.graph.find_nodes_by_type(NodeType.CHARACTER)

    for node in char_nodes:
        if node.id == character_id or node.attrs.get("name") == character_id:
            char_node = node
            break

    if not char_node:
        return ToolResult(success=False, content=f"未找到角色: {character_id}")

    char_card = context.characters.get(char_node.id)
    char_name = char_card.name if char_card else char_node.id

    lines = [f"角色关系：{char_name}"]

    # 出边（该角色对其他角色的关系）
    out_edges = context.graph.find_edges_by_source(char_node.id)
    if out_edges:
        lines.append("├──对外关系")
        for i, edge in enumerate(out_edges):
            target_node = context.graph.get_node(edge.target_id)
            target_card = (
                context.characters.get(edge.target_id) if target_node else None
            )
            target_name = target_card.name if target_card else edge.target_id

            marker = "│  └──" if i == len(out_edges) - 1 else "│  ├──"
            lines.append(f"{marker}→ {target_name} ({edge.type.value})")

    # 入边（其他角色对该角色的关系）
    in_edges = context.graph.find_edges_by_target(char_node.id)
    if in_edges:
        lines.append("└──被关系")
        for i, edge in enumerate(in_edges):
            source_node = context.graph.get_node(edge.source_id)
            source_card = (
                context.characters.get(edge.source_id) if source_node else None
            )
            source_name = source_card.name if source_card else edge.source_id

            marker = "   └──" if i == len(in_edges) - 1 else "   ├──"
            lines.append(f"{marker}← {source_name} ({edge.type.value})")

    if not out_edges and not in_edges:
        lines.append("└──暂无关系记录")

    return ToolResult(success=True, content="\n".join(lines))


# =============== 更新类工具 ===============


def update_character(
    context: Any,
    character_id: str,
    action: str = "",
    result: str = "",
    note: str = "",
    ability_unlock: str = "",
    ability_reveal: str = "",
) -> ToolResult:
    """
    更新角色状态

    Args:
        context: AgentContext
        character_id: 角色ID或名称
        action: 最近行为
        result: 行为结果
        note: 新增备注
        ability_unlock: 解锁能力名称
        ability_reveal: 揭示能力名称

    Returns:
        更新结果
    """
    char = context.characters.get(character_id)

    if not char:
        for cid, c in context.characters.items():
            if c.name == character_id:
                char = c
                character_id = cid
                break

    if not char:
        return ToolResult(success=False, content=f"未找到角色: {character_id}")

    updates = []

    if action:
        char.update_last_action(action, result or "")
        updates.append(f"更新行为: {action}")
        if result:
            updates.append(f"行为结果: {result}")

    if note:
        char.add_note(note)
        updates.append(
            f"新增备注: {note[:30]}..." if len(note) > 30 else f"新增备注: {note}"
        )

    if ability_unlock:
        if char.unlock_ability(ability_unlock):
            updates.append(f"解锁能力: {ability_unlock}")
        else:
            updates.append(f"解锁能力失败（不存在或已解锁）: {ability_unlock}")

    if ability_reveal:
        if char.reveal_ability(ability_reveal):
            updates.append(f"揭示能力: {ability_reveal}")
        else:
            updates.append(f"揭示能力失败（不存在或已公开）: {ability_reveal}")

    if not updates:
        return ToolResult(success=False, content="未提供更新内容")

    return ToolResult(
        success=True,
        content=f"角色 {char.name} 更新成功:\n" + "\n".join(f"├──{u}" for u in updates),
        data=char,
    )


def update_location(context: Any, character_id: str, location_id: str) -> ToolResult:
    """
    更新角色位置

    Args:
        context: AgentContext
        character_id: 角色ID或名称
        location_id: 目标地点ID或名称

    Returns:
        更新结果
    """
    if not context.timeline or not context.current_point_id:
        return ToolResult(success=False, content="无当前时间点，无法更新位置")

    char = context.characters.get(character_id)
    if not char:
        for cid, c in context.characters.items():
            if c.name == character_id:
                char = c
                character_id = cid
                break

    if not char:
        return ToolResult(success=False, content=f"未找到角色: {character_id}")

    loc = None
    if context.world_map:
        loc = context.world_map.get_location(location_id)
        if not loc:
            loc = context.world_map.find_location_by_name(location_id)

    if context.world_map and not loc:
        loc_names = [loc.name for loc in context.world_map.locations.values()]
        return ToolResult(
            success=False,
            content=f"未找到地点: {location_id}",
            suggestions=[f"可用地点: {', '.join(loc_names)}"],
        )

    loc_name = loc.name if loc else location_id

    # 获取原位置
    old_loc_id = context.timeline.get_character_location(
        context.current_point_id, character_id
    )
    old_loc = (
        context.world_map.get_location(old_loc_id)
        if old_loc_id and context.world_map
        else None
    )
    old_loc_name = old_loc.name if old_loc else old_loc_id or "未知"

    # 更新位置
    context.timeline.set_character_location(
        context.current_point_id, character_id, loc.id if loc else location_id
    )

    return ToolResult(
        success=True,
        content=(
            f"角色 {char.name} 位置已更新:\n"
            f"├──原位置: {old_loc_name}\n"
            f"└──新位置: {loc_name}"
        ),
    )


def add_event(
    context: Any,
    event_name: str,
    description: str,
    involved_characters: list[str] | None = None,
    location_id: str = "",
    time_point_id: str = "",
) -> ToolResult:
    """
    添加新事件

    Args:
        context: AgentContext
        event_name: 事件名称
        description: 事件描述
        involved_characters: 涉及角色列表
        location_id: 发生地点
        time_point_id: 时间点

    Returns:
        添加结果
    """
    import uuid

    from src.core.graph import Edge, EdgeType, Node, NodeType

    if not context.graph:
        return ToolResult(success=False, content="无图结构，无法添加事件")

    # 创建事件节点
    event_id = f"event_{uuid.uuid4().hex[:8]}"
    event_node = Node(
        id=event_id,
        type=NodeType.EVENT,
        attrs={"name": event_name, "description": description},
    )

    # 设置时间点
    if time_point_id:
        event_node.time_point_id = time_point_id
    elif context.current_point_id:
        event_node.time_point_id = context.current_point_id

    context.graph.add_node(event_node)

    # 创建角色关联
    edges_created = []
    if involved_characters:
        for char_name in involved_characters:
            # 查找角色
            char_id = None
            for cid, c in context.characters.items():
                if c.name == char_name:
                    char_id = cid
                    break

            if char_id:
                edge_id = f"edge_{uuid.uuid4().hex[:8]}"
                edge = Edge(
                    id=edge_id,
                    type=EdgeType.INVOLVES,
                    source_id=event_id,
                    target_id=char_id,
                )
                context.graph.add_edge(edge)
                edges_created.append(char_name)

    lines = [
        f"事件创建成功: {event_name}",
        f"├──事件ID: {event_id}",
        f"├──描述: {description[:50]}..."
        if len(description) > 50
        else f"├──描述: {description}",
    ]

    if edges_created:
        lines.append(f"└──涉及角色: {', '.join(edges_created)}")
    else:
        lines.append("└──涉及角色: 无")

    return ToolResult(success=True, content="\n".join(lines), data=event_node)


# =============== 辅助类工具 ===============


def check_consistency(context: Any, check_type: str = "all") -> ToolResult:
    """
    快速一致性检查

    Args:
        context: AgentContext
        check_type: 检查类型 (all/position/timeline/character)

    Returns:
        检查结果
    """
    issues = []

    # 检查角色位置
    if (
        check_type in ("all", "position")
        and context.timeline
        and context.current_point_id
    ):
        point = context.timeline.get_point(context.current_point_id)
        if point and context.world_map:
            for char_id, loc_id in point.character_locations.items():
                loc = context.world_map.get_location(loc_id)
                if not loc:
                    issues.append(
                        f"[位置] 角色 {char_id} 的位置 {loc_id} 不存在于地图中"
                    )

    if check_type in ("all", "timeline") and context.timeline:
        # 检查时间点连续性
        points = context.timeline.get_ordered_points()
        for _i, p in enumerate(points):
            if p.prev_id:
                prev = context.timeline.get_point(p.prev_id)
                if prev and prev.next_id != p.id:
                    issues.append(f"[时间] 时间点 {p.label} 的前驱链接不一致")
            if p.next_id:
                next_p = context.timeline.get_point(p.next_id)
                if next_p and next_p.prev_id != p.id:
                    issues.append(f"[时间] 时间点 {p.label} 的后继链接不一致")

    if not issues:
        return ToolResult(
            success=True,
            content="一致性检查通过，未发现问题",
            suggestions=["可以继续进行创作"],
        )

    return ToolResult(
        success=False,
        content=f"发现 {len(issues)} 个问题:\n" + "\n".join(f"├──{i}" for i in issues),
        issues=issues,
    )


def suggest_next(context: Any, current_situation: str = "") -> ToolResult:
    """
    建议下一步发展

    Args:
        context: AgentContext
        current_situation: 当前情境描述

    Returns:
        发展建议
    """
    suggestions = []
    current_point_id = (
        context.current_point_id if hasattr(context, "current_point_id") else None
    )

    # 基于时间轴建议
    if context.timeline and hasattr(context.timeline, "get_ordered_points"):
        points = context.timeline.get_ordered_points()
        if current_point_id:
            current_idx = None
            for i, p in enumerate(points):
                p_id = p.id if hasattr(p, "id") else None
                if p_id == current_point_id:
                    current_idx = i
                    break

            if current_idx is not None:
                if current_idx < len(points) - 1:
                    next_point = points[current_idx + 1]
                    label = (
                        next_point.label
                        if hasattr(next_point, "label")
                        else str(next_point)
                    )
                    suggestions.append(f"下一时间点: {label}")
                else:
                    suggestions.append("已达时间轴末尾，可考虑创建新时间点")

    # 基于角色状态建议
    if context.characters:
        for char_id, char in context.characters.items():
            last_action = char.last_action if hasattr(char, "last_action") else ""
            last_result = char.last_result if hasattr(char, "last_result") else ""
            name = char.name if hasattr(char, "name") else char_id

            if last_action and not last_result:
                suggestions.append(f"角色 {name} 有待处理的行动: {last_action}")

            if hasattr(char, "get_future_abilities"):
                future_abilities = char.get_future_abilities()
                if future_abilities:
                    ability_names = []
                    for a in future_abilities:
                        if hasattr(a, "name"):
                            ability_names.append(a.name)
                        else:
                            ability_names.append(str(a))
                    suggestions.append(
                        f"角色 {name} 有待解锁的能力: {', '.join(ability_names)}"
                    )

    # 基于伏笔建议
    if context.graph and hasattr(context.graph, "find_nodes_by_type"):
        from src.core.graph import NodeType

        foreshadows = context.graph.find_nodes_by_type(NodeType.FORESHADOW)
        if foreshadows:
            unrevealed = []
            for f in foreshadows:
                attrs = f.attrs if hasattr(f, "attrs") else {}
                revealed = attrs.get("revealed", False)
                if not revealed:
                    name = attrs.get("name", f.id if hasattr(f, "id") else str(f))
                    unrevealed.append(name)
            if unrevealed:
                suggestions.append(f"待揭示的伏笔: {', '.join(unrevealed[:3])}")

    if not suggestions:
        suggestions.append("暂无特定建议，可根据剧情需要自由发展")

    return ToolResult(
        success=True,
        content="下一步发展建议:\n" + "\n".join(f"├──{s}" for s in suggestions),
        suggestions=suggestions,
    )


# =============== 设计工具 ===============


def parse_chapter_range(chapter_str: str) -> list[int]:
    """
    解析章节范围字符串

    支持格式:
    - "1,3,5" -> [1, 3, 5]
    - "1-5" -> [1, 2, 3, 4, 5]
    - "1,3-5,8" -> [1, 3, 4, 5, 8]

    Args:
        chapter_str: 章节范围字符串

    Returns:
        章节号列表
    """
    chapters = []
    parts = [p.strip() for p in chapter_str.split(",") if p.strip()]

    for part in parts:
        if "-" in part:
            # 范围格式: 1-5
            start_end = part.split("-")
            if len(start_end) == 2:
                try:
                    start = int(start_end[0].strip())
                    end = int(start_end[1].strip())
                    chapters.extend(range(start, end + 1))
                except ValueError:
                    pass
        else:
            # 单个章节
            try:
                chapters.append(int(part))
            except ValueError:
                pass

    return sorted(set(chapters))


def design_add_character(
    context: Any,
    name: str,
    role: str = "配角",
    description: str = "",
    personality: str = "",
    background: str = "",
    appearances: str = "",
    goals: str = "",
    abilities: str = "",
    dialogue_style: str = "",
    arc: str = "",
) -> ToolResult:
    """
    添加角色到设计中

    Args:
        context: AgentContext
        name: 角色名称
        role: 角色定位（主角/反派/配角/龙套）
        description: 角色简介
        personality: 性格特点
        background: 背景故事
        appearances: 出场章节（逗号分隔，如 "1,3,5-8"）
        goals: 角色目标
        abilities: 角色能力（逗号分隔）
        dialogue_style: 对话风格（说话特点、口头禅）
        arc: 角色弧线（成长变化路径）
    """
    from src.core.character import CharacterCard, Ability

    # 确保 characters 存在（不创建新 dict，保持引用）
    if context.characters is None:
        context.characters = {}

    # 检查是否已存在（按名字检查）
    for _existing_id, existing_char in context.characters.items():
        if existing_char.name == name:
            return ToolResult(
                success=False,
                content=f"角色 '{name}' 已存在",
                suggestions=["使用不同的角色名，或使用 update_character 更新现有角色"],
            )

    char_id = f"char_{name}"
    char = CharacterCard(
        id=char_id,
        name=name,
        attrs={
            "role": role,
            "description": description,
            "personality": personality,
            "background": background,
            "goals": goals,
            "dialogue_style": dialogue_style,
            "arc": arc,
        },
    )

    # 解析出场章节
    if appearances:
        chapters = parse_chapter_range(appearances)
        char.attrs["appearances"] = chapters

    # 解析能力
    if abilities:
        ability_list = [a.strip() for a in abilities.split(",") if a.strip()]
        for ab_name in ability_list:
            ab_id = f"ability_{ab_name}"
            char.abilities[ab_id] = Ability(
                name=ab_name,
                is_public=True,
            )

    context.characters[char_id] = char

    return ToolResult(
        success=True,
        content=f"已添加角色: {name}（{role}），出场章节: {appearances or '未指定'}",
        data={"character_id": char_id, "character": char},
    )


def design_add_location(
    context: Any,
    name: str,
    loc_type: str = "其他",
    description: str = "",
    significance: str = "",
    chapters: str = "",
    parent: str = "",
) -> ToolResult:
    """
    添加地点到世界地图

    Args:
        context: AgentContext
        name: 地点名称
        loc_type: 地点类型（城市/建筑/自然/室内/其他）
        description: 地点描述
        significance: 剧情意义
        chapters: 涉及章节（逗号分隔，如 "1,3,5-8"）
        parent: 父级地点名称
    """
    from src.core.map import Location, LocationType, WorldMap

    # 确保 world_map 存在
    if context.world_map is None:
        context.world_map = WorldMap()

    # 检查是否已存在
    for loc in context.world_map.locations.values():
        if loc.name == name:
            return ToolResult(
                success=False,
                content=f"地点 '{name}' 已存在",
                suggestions=["使用不同的地点名"],
            )

    type_map = {
        "世界": LocationType.WORLD,
        "大陆": LocationType.CONTINENT,
        "国家": LocationType.COUNTRY,
        "区域": LocationType.REGION,
        "城市": LocationType.CITY,
        "区": LocationType.DISTRICT,
        "建筑": LocationType.BUILDING,
        "房间": LocationType.ROOM,
        "其他": LocationType.OTHER,
    }
    location_type = type_map.get(loc_type, LocationType.OTHER)

    # 查找父级地点
    parent_id = None
    if parent:
        for loc in context.world_map.locations.values():
            if loc.name == parent:
                parent_id = loc.id
                break

    loc_id = f"loc_{name}"
    loc = Location(
        id=loc_id,
        name=name,
        type=location_type,
        description=description,
        parent_id=parent_id,
    )

    # 解析涉及章节
    if chapters:
        chapter_list = parse_chapter_range(chapters)
        loc.attrs["chapters"] = chapter_list

    if significance:
        loc.attrs["significance"] = significance

    context.world_map.add_location(loc)

    return ToolResult(
        success=True,
        content=f"已添加地点: {name}（{loc_type}），涉及章节: {chapters or '未指定'}",
        data={"location_id": loc_id, "location": loc},
    )


def design_add_relation(
    context: Any,
    char1: str,
    char2: str,
    relation_type: str = "",
    description: str = "",
    chapter: str = "",
    event: str = "",
    change: str = "",
) -> ToolResult:
    """
    添加角色关系变化（关联章节和事件）

    Args:
        context: AgentContext
        char1: 角色名称1
        char2: 角色名称2
        relation_type: 关系类型（师徒/仇敌/恋人/盟友/亲属）
        description: 关系描述
        chapter: 发生章节（关系变化的节点）
        event: 触发事件（什么事件导致关系变化）
        change: 变化描述（从什么状态变成什么状态）
    """
    if "relations" not in context.extra:
        context.extra["relations"] = []

    relation = {
        "char1": char1,
        "char2": char2,
        "type": relation_type,
        "description": description,
        "chapter": chapter,
        "event": event,
        "change": change,
    }
    context.extra["relations"].append(relation)

    return ToolResult(
        success=True,
        content=f"已添加关系变化: 第{chapter}章 {char1} ↔ {char2}（{relation_type}）- {change}",
        data={"relation": relation},
    )


def design_add_event(
    context: Any,
    name: str,
    chapter: int,
    description: str = "",
    characters: str = "",
    location: str = "",
) -> ToolResult:
    """
    添加事件到时间轴和图结构

    Args:
        context: AgentContext
        name: 事件名称
        chapter: 所在章节
        description: 事件描述
        characters: 涉及角色（逗号分隔）
        location: 发生地点
    """
    from src.core.graph import Node, NodeType
    from src.core.graph.timeline import TimePoint

    # 类型转换
    if isinstance(chapter, str):
        chapter = int(chapter) if chapter.isdigit() else 1

    # 添加时间点
    tp_id = f"tp_ch{chapter}_{name}"
    tp = TimePoint(
        id=tp_id,
        label=f"第{chapter}章: {name}",
        attrs={"chapter": chapter, "event": name, "description": description},
    )
    context.timeline.append(tp)

    # 添加事件节点
    event_id = f"event_ch{chapter}_{name}"
    event_node = Node(
        id=event_id,
        type=NodeType.EVENT,
        attrs={
            "name": name,
            "chapter": chapter,
            "description": description,
            "characters": characters,
            "location": location,
        },
        time_point_id=tp_id,
    )
    context.graph.add_node(event_node)

    return ToolResult(
        success=True,
        content=f"已添加事件: 第{chapter}章「{name}」",
        data={"event_id": event_id, "timepoint_id": tp_id},
    )


def design_set_seed(
    context: Any,
    core: str,
    conflict: str = "",
    theme: str = "",
    tone: str = "",
) -> ToolResult:
    """
    设置故事核心种子

    Args:
        context: AgentContext
        core: 故事核心（一句话概括）
        conflict: 核心冲突
        theme: 主题内核
        tone: 情感基调
    """
    seed_data = {
        "core": core,
        "conflict": conflict,
        "theme": theme,
        "tone": tone,
    }
    context.extra["seed"] = seed_data

    return ToolResult(
        success=True,
        content=f"已设置故事核心: {core[:50]}...",
        data=seed_data,
    )


def design_add_chapter(
    context: Any,
    chapter_num: int,
    title: str,
    summary: str = "",
    pov: str = "",
    key_events: str = "",
    characters: str = "",
    locations: str = "",
    emotional_arc: str = "",
    scenes: str = "",
    conflicts: str = "",
    foreshadows: str = "",
) -> ToolResult:
    """
    添加章节大纲（完整版）

    Args:
        context: AgentContext
        chapter_num: 章节号
        title: 章节标题
        summary: 章节摘要（100字内）
        pov: 视角角色
        key_events: 关键事件（逗号分隔）
        characters: 出场角色（逗号分隔）
        locations: 涉及地点（逗号分隔）
        emotional_arc: 情感弧线（如 "紧张→悬疑→释放"）
        scenes: 场景列表（逗号分隔，如 "开场-客栈,对峙-街道,结局-山林"）
        conflicts: 冲突点（逗号分隔）
        foreshadows: 伏笔（逗号分隔，格式：埋设/回收-内容）
    """
    from src.core.graph.timeline import TimePoint

    if isinstance(chapter_num, str):
        chapter_num = int(chapter_num) if chapter_num.isdigit() else 1

    if "blueprint" not in context.extra:
        context.extra["blueprint"] = {}

    # 解析角色和地点列表
    char_list = [c.strip() for c in characters.split(",") if c.strip()] if characters else []
    loc_list = [l.strip() for l in locations.split(",") if l.strip()] if locations else []
    scene_list = [s.strip() for s in scenes.split(",") if s.strip()] if scenes else []
    conflict_list = [c.strip() for c in conflicts.split(",") if c.strip()] if conflicts else []
    foreshadow_list = [f.strip() for f in foreshadows.split(",") if f.strip()] if foreshadows else []

    # 存储章节蓝图
    context.extra["blueprint"][chapter_num] = {
        "title": title,
        "summary": summary,
        "pov": pov,
        "key_events": key_events,
        "characters": char_list,
        "locations": loc_list,
        "emotional_arc": emotional_arc,
        "scenes": scene_list,
        "conflicts": conflict_list,
        "foreshadows": foreshadow_list,
    }

    # 创建对应的时间点
    tp_id = f"tp_ch{chapter_num}"
    tp = TimePoint(
        id=tp_id,
        label=f"第{chapter_num}章: {title}",
        attrs={
            "chapter": chapter_num,
            "summary": summary,
            "key_events": key_events,
            "emotional_arc": emotional_arc,
        },
    )

    # 设置角色位置
    if char_list and loc_list:
        for char_name in char_list:
            # 查找角色 ID
            char_id = None
            if context.characters:
                for cid, char in context.characters.items():
                    if char.name == char_name:
                        char_id = cid
                        break
            if char_id and loc_list:
                # 默认第一个地点
                loc_id = None
                if context.world_map:
                    for lid, loc in context.world_map.locations.items():
                        if loc.name == loc_list[0]:
                            loc_id = lid
                            break
                if loc_id:
                    tp.character_locations[char_id] = loc_id

    # 添加到时间轴
    context.timeline.append(tp)

    return ToolResult(
        success=True,
        content=f"已添加第{chapter_num}章: 「{title}」\n  角色: {', '.join(char_list) or '未指定'}\n  地点: {', '.join(loc_list) or '未指定'}",
        data={"chapter_num": chapter_num, "title": title, "timepoint_id": tp_id},
    )


def design_set_world(
    context: Any,
    setting: str,
    rules: str = "",
    factions: str = "",
    technology: str = "",
) -> ToolResult:
    """
    设置世界观设定

    Args:
        context: AgentContext
        setting: 时代背景/世界类型
        rules: 世界规则（魔法体系/科技水平等）
        factions: 势力分布
        technology: 技术水平/特殊能力体系
    """
    world_data = {
        "setting": setting,
        "rules": rules,
        "factions": factions,
        "technology": technology,
    }
    context.extra["world"] = world_data

    return ToolResult(
        success=True,
        content=f"已设置世界观: {setting}",
        data=world_data,
    )


def design_complete(context: Any, summary: str = "") -> ToolResult:
    """
    完成设计，提交最终设计摘要

    Args:
        context: AgentContext
        summary: 设计摘要（可选，将自动生成）
    """
    # 收集所有设计数据
    seed = context.extra.get("seed", {})
    world = context.extra.get("world", {})
    blueprint = context.extra.get("blueprint", {})

    # 生成设计摘要
    if not summary:
        lines = ["═" * 50]
        lines.append("【小说设计蓝图】")
        lines.append("═" * 50)

        # 核心种子
        if seed:
            lines.append("\n📌【核心种子】")
            lines.append(f"   故事核心: {seed.get('core', '未设置')}")
            if seed.get("conflict"):
                lines.append(f"   核心冲突: {seed['conflict']}")
            if seed.get("theme"):
                lines.append(f"   主题内核: {seed['theme']}")
            if seed.get("tone"):
                lines.append(f"   情感基调: {seed['tone']}")

        # 世界观设定
        if world:
            lines.append("\n🌍【世界观设定】")
            lines.append(f"   背景: {world.get('setting', '未设置')}")
            if world.get("rules"):
                lines.append(f"   规则: {world['rules']}")
            if world.get("factions"):
                lines.append(f"   势力: {world['factions']}")

        # 地点信息
        if context.world_map and context.world_map.locations:
            lines.append("\n🗺️【地点设定】")
            for loc_id, loc in context.world_map.locations.items():
                chapters = loc.attrs.get("chapters", [])
                ch_str = f" [章节: {','.join(map(str, chapters))}]" if chapters else ""
                lines.append(f"   • {loc.name}（{loc.type.value}）{ch_str}")
                if loc.description:
                    lines.append(f"     {loc.description[:50]}{'...' if len(loc.description) > 50 else ''}")

        # 角色信息（含出场章节）
        if context.characters:
            lines.append("\n👥【角色设定】")
            for char_id, char in context.characters.items():
                role = char.attrs.get("role", "未知")
                appearances = char.attrs.get("appearances", [])
                ap_str = f" [出场: {','.join(map(str, appearances))}]" if appearances else ""
                lines.append(f"   • {char.name}（{role}）{ap_str}")
                if char.attrs.get("goals"):
                    lines.append(f"     目标: {char.attrs['goals']}")
                if char.abilities:
                    ab_names = [ab.name for ab in char.abilities]
                    lines.append(f"     能力: {', '.join(ab_names)}")

        # 时间线
        if context.timeline and context.timeline.points:
            lines.append("\n⏱️【时间线】")
            for tp in context.timeline.points[:10]:  # 最多显示10个
                lines.append(f"   • {tp.label}")
            if len(context.timeline.points) > 10:
                lines.append(f"   ... 共 {len(context.timeline.points)} 个时间点")

        # 章节蓝图（含角色和地点）
        if blueprint:
            lines.append("\n📖【章节蓝图】")
            for ch_num in sorted(blueprint.keys()):
                ch = blueprint[ch_num]
                lines.append(f"\n   第{ch_num}章「{ch.get('title', '未命名')}」")
                if ch.get("summary"):
                    lines.append(f"   摘要: {ch['summary'][:60]}{'...' if len(ch['summary']) > 60 else ''}")
                if ch.get("characters"):
                    lines.append(f"   角色: {', '.join(ch['characters'])}")
                if ch.get("locations"):
                    lines.append(f"   地点: {', '.join(ch['locations'])}")
                if ch.get("emotional_arc"):
                    lines.append(f"   情感: {ch['emotional_arc']}")

        lines.append("\n" + "═" * 50)
        lines.append(f"✅ 设计完成：{len(context.characters)} 角色, {len(context.world_map.locations) if context.world_map else 0} 地点, {len(blueprint)} 章节")
        lines.append("═" * 50)
        summary = "\n".join(lines)

    return ToolResult(
        success=True,
        content="设计已完成",
        data={"final_content": summary, "completed": True},
    )


def get_design_tools() -> dict[str, Tool]:
    """获取设计相关工具"""
    return {
        "add_character": Tool(
            name="add_character",
            description="添加角色到小说设定中（完整版，包含对话风格和角色弧线）",
            tool_type=ToolType.UPDATE,
            parameters={
                "name": "角色名称（必填）",
                "role": "角色定位：主角/反派/配角/龙套（默认配角）",
                "description": "角色简介",
                "personality": "性格特点",
                "background": "背景故事",
                "appearances": "出场章节（逗号分隔，如 1,3,5-8，重要！）",
                "goals": "角色目标",
                "abilities": "角色能力（逗号分隔）",
                "dialogue_style": "对话风格（说话特点、口头禅）",
                "arc": "角色弧线（成长变化路径）",
            },
            execute=design_add_character,
        ),
        "add_location": Tool(
            name="add_location",
            description="添加地点到世界地图",
            tool_type=ToolType.UPDATE,
            parameters={
                "name": "地点名称（必填）",
                "loc_type": "地点类型：城市/建筑/自然/室内/其他（默认其他）",
                "description": "地点描述",
                "significance": "剧情意义",
                "chapters": "涉及章节（逗号分隔，如 1,3,5-8）",
                "parent": "父级地点名称（用于构建层级）",
            },
            execute=design_add_location,
        ),
        "add_event": Tool(
            name="add_event",
            description="添加事件到时间轴",
            tool_type=ToolType.UPDATE,
            parameters={
                "name": "事件名称（必填）",
                "chapter": "所在章节号（必填）",
                "description": "事件描述",
                "characters": "涉及角色（逗号分隔）",
                "location": "发生地点",
            },
            execute=design_add_event,
        ),
        "set_seed": Tool(
            name="set_seed",
            description="设置故事核心种子",
            tool_type=ToolType.UPDATE,
            parameters={
                "core": "故事核心，一句话概括（必填）",
                "conflict": "核心冲突",
                "theme": "主题内核",
                "tone": "情感基调",
            },
            execute=design_set_seed,
        ),
        "add_chapter": Tool(
            name="add_chapter",
            description="添加章节大纲（完整版，包含场景和冲突）",
            tool_type=ToolType.UPDATE,
            parameters={
                "chapter_num": "章节号（必填）",
                "title": "章节标题（必填）",
                "summary": "章节摘要（100字内）",
                "pov": "视角角色",
                "key_events": "关键事件（逗号分隔）",
                "characters": "出场角色（逗号分隔，重要！）",
                "locations": "涉及地点（逗号分隔，重要！）",
                "emotional_arc": "情感弧线（如：紧张→悬疑→释放）",
                "scenes": "场景列表（逗号分隔，如：开场-客栈,对峙-街道）",
                "conflicts": "冲突点（逗号分隔）",
                "foreshadows": "伏笔（逗号分隔，如：埋设-神秘信物,回收-真相揭露）",
            },
            execute=design_add_chapter,
        ),
        "add_relation": Tool(
            name="add_relation",
            description="添加角色关系变化（关联章节和事件）",
            tool_type=ToolType.UPDATE,
            parameters={
                "char1": "角色名称1（必填）",
                "char2": "角色名称2（必填）",
                "relation_type": "关系类型：师徒/仇敌/恋人/盟友/亲属",
                "description": "关系描述",
                "chapter": "发生章节（关系变化的节点）",
                "event": "触发事件（什么事件导致关系变化）",
                "change": "变化描述（从什么状态变成什么状态）",
            },
            execute=design_add_relation,
        ),
        "set_world": Tool(
            name="set_world",
            description="设置世界观设定",
            tool_type=ToolType.UPDATE,
            parameters={
                "setting": "时代背景/世界类型（必填）",
                "rules": "世界规则（魔法体系/科技水平等）",
                "factions": "势力分布",
                "technology": "技术水平/特殊能力体系",
            },
            execute=design_set_world,
        ),
        "complete_design": Tool(
            name="complete_design",
            description="完成设计并提交最终结果。设计完成后必须调用此工具！",
            tool_type=ToolType.QUERY,
            parameters={"summary": "设计摘要（可选，将自动生成）"},
            execute=design_complete,
        ),
    }


# =============== 工具注册 ===============


def get_all_tools(mode: str = "write") -> dict[str, Tool]:
    """
    获取可用工具

    Args:
        mode: 工具模式
            - "write": 写作工具（默认）
            - "design": 设计工具
    """
    if mode == "design":
        return get_design_tools()
    return {
        # 完成工具（必须首先调用以结束任务）
        "complete": Tool(
            name="complete",
            description="完成任务并提交最终内容。当你完成写作后，必须调用此工具提交内容！",
            tool_type=ToolType.QUERY,
            parameters={"content": "最终完成的章节内容（必填）"},
            execute=complete,
        ),
        # 章节查询工具
        "query_previous_chapter": Tool(
            name="query_previous_chapter",
            description="查询已完成章节的内容，用于获取前文上下文",
            tool_type=ToolType.QUERY,
            parameters={"chapter_num": "章节号（可选，默认查询上一章）"},
            execute=query_previous_chapter,
        ),
        "query_chapter_outline": Tool(
            name="query_chapter_outline",
            description="查询指定章节的大纲/剧情要点",
            tool_type=ToolType.QUERY,
            parameters={"chapter_num": "章节号（可选，默认查询当前章节）"},
            execute=query_chapter_outline,
        ),
        "query_all_chapters": Tool(
            name="query_all_chapters",
            description="查询所有已完成章节的摘要列表",
            tool_type=ToolType.QUERY,
            parameters={},
            execute=query_all_chapters,
        ),
        # 角色查询工具
        "query_character": Tool(
            name="query_character",
            description="查询角色的详细信息，包括能力、状态、备注等",
            tool_type=ToolType.QUERY,
            parameters={"character_id": "角色ID或名称"},
            execute=query_character,
        ),
        "query_location": Tool(
            name="query_location",
            description="查询地点的详细信息，包括层级关系、相邻地点、当前在场角色",
            tool_type=ToolType.QUERY,
            parameters={"location_id": "地点ID或名称"},
            execute=query_location,
        ),
        "query_timeline": Tool(
            name="query_timeline",
            description="查询时间轴信息，可查询单个时间点或整个时间轴",
            tool_type=ToolType.QUERY,
            parameters={"point_id": "时间点ID（可选）"},
            execute=query_timeline,
        ),
        "query_events": Tool(
            name="query_events",
            description="查询事件列表",
            tool_type=ToolType.QUERY,
            parameters={"event_type": "事件类型过滤（可选）"},
            execute=query_events,
        ),
        "query_relationships": Tool(
            name="query_relationships",
            description="查询角色之间的关系网络",
            tool_type=ToolType.QUERY,
            parameters={"character_id": "角色ID或名称"},
            execute=query_relationships,
        ),
        "update_character": Tool(
            name="update_character",
            description="更新角色状态，包括行为、备注、能力解锁/揭示",
            tool_type=ToolType.UPDATE,
            parameters={
                "character_id": "角色ID或名称",
                "action": "最近行为（可选）",
                "result": "行为结果（可选）",
                "note": "新增备注（可选）",
                "ability_unlock": "解锁能力名称（可选）",
                "ability_reveal": "揭示能力名称（可选）",
            },
            execute=update_character,
        ),
        "update_location": Tool(
            name="update_location",
            description="更新角色当前位置",
            tool_type=ToolType.UPDATE,
            parameters={
                "character_id": "角色ID或名称",
                "location_id": "目标地点ID或名称",
            },
            execute=update_location,
        ),
        "add_event": Tool(
            name="add_event",
            description="添加新事件到图中",
            tool_type=ToolType.UPDATE,
            parameters={
                "event_name": "事件名称",
                "description": "事件描述",
                "involved_characters": "涉及角色列表（可选）",
                "location_id": "发生地点（可选）",
                "time_point_id": "时间点（可选）",
            },
            execute=add_event,
        ),
        "check_consistency": Tool(
            name="check_consistency",
            description="快速一致性检查，检测位置、时间等问题",
            tool_type=ToolType.HELPER,
            parameters={"check_type": "检查类型: all/position/timeline/character"},
            execute=check_consistency,
        ),
        "suggest_next": Tool(
            name="suggest_next",
            description="基于当前状态建议下一步发展方向",
            tool_type=ToolType.HELPER,
            parameters={"current_situation": "当前情境描述（可选）"},
            execute=suggest_next,
        ),
    }


def build_tools_description() -> str:
    """构建工具描述文本，用于提示词中"""
    tools = get_all_tools()

    lines = ["可用工具列表:"]

    for i, (name, tool) in enumerate(tools.items()):
        marker = "└──" if i == len(tools) - 1 else "├──"
        lines.append(f"{marker}{name}: {tool.description}")

        params = [f"{k}({v})" for k, v in tool.parameters.items()]
        prefix = "   " if i == len(tools) - 1 else "│  "
        lines.append(f"{prefix}└──参数: {', '.join(params)}")

    return "\n".join(lines)
