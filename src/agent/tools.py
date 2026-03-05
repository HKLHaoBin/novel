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

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ToolType(Enum):
    """工具类型"""
    QUERY = "query"       # 查询类
    UPDATE = "update"     # 更新类
    HELPER = "helper"     # 辅助类


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
    char = context.characters.get(character_id)
    
    # 支持按名称查询
    if not char:
        for cid, c in context.characters.items():
            if c.name == character_id:
                char = c
                character_id = cid
                break
    
    if not char:
        return ToolResult(
            success=False,
            content=f"未找到角色: {character_id}",
            suggestions=[f"可用角色: {', '.join(c.name for c in context.characters.values())}"]
        )
    
    # 构建结构化输出
    lines = [
        f"角色：{char.name}",
        "├──基础信息",
        f"│  ├──性别: {char.gender}",
        f"│  ├──年龄: {char.age}",
        f"│  └──性格: {char.personality}",
        "├──能力",
    ]
    
    for ability in char.abilities.values():
        status = []
        if ability.is_future:
            status.append("未来获得")
        elif not ability.is_public:
            status.append("未公开")
        else:
            status.append("已公开")
        
        status_str = f"（{', '.join(status)}）" if status else ""
        lines.append(f"│  ├──{ability.name}{status_str}: {ability.description}")
    
    lines.append("├──备注")
    for note in char.notes[-5:]:  # 最近5条备注
        lines.append(f"│  └──{note}")
    
    lines.append(f"├──最近行为: {char.last_action}")
    lines.append(f"└──行为结果: {char.last_result}")
    
    return ToolResult(
        success=True,
        content="\n".join(lines),
        data=char
    )


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
        return ToolResult(success=False, content="无地图信息")
    
    loc = context.world_map.get_location(location_id)
    
    # 支持按名称查询
    if not loc:
        loc = context.world_map.find_location_by_name(location_id)
    
    if not loc:
        return ToolResult(
            success=False,
            content=f"未找到地点: {location_id}",
            suggestions=[f"可用地点: {', '.join(loc.name for loc in context.world_map.locations.values())}"]
        )
    
    # 构建结构化输出
    lines = [
        f"地点：{loc.name}",
        f"├──类型: {loc.type.value}",
        f"├──描述: {loc.description}",
    ]
    
    # 父级地点
    if loc.parent_id:
        parent = context.world_map.get_location(loc.parent_id)
        if parent:
            lines.append(f"├──上级地点: {parent.name}")
    
    # 子级地点
    children = context.world_map.get_children(loc.id)
    if children:
        lines.append("├──下级地点")
        for i, child in enumerate(children):
            marker = "└──" if i == len(children) - 1 else "│  ├──"
            lines.append(f"{marker}{child.name}")
    
    # 相邻地点
    adjacent = context.world_map.get_adjacent_locations(loc.id)
    if adjacent:
        lines.append("├──相邻地点")
        adj_names = [a.name for a in adjacent]
        lines.append(f"│  └──{', '.join(adj_names)}")
    
    # 当前在场角色
    characters_here = []
    if context.timeline and context.current_point_id:
        point = context.timeline.get_point(context.current_point_id)
        if point:
            for char_id, loc_id in point.character_locations.items():
                if loc_id == loc.id:
                    char = context.characters.get(char_id)
                    characters_here.append(char.name if char else char_id)
    
    if characters_here:
        lines.append("└──当前在场角色")
        lines.append(f"   └──{', '.join(characters_here)}")
    else:
        lines.append("└──当前在场角色: 无")
    
    return ToolResult(
        success=True,
        content="\n".join(lines),
        data=loc
    )


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
        return ToolResult(success=False, content="无时间轴信息")
    
    if point_id:
        point = context.timeline.get_point(point_id)
        if not point:
            return ToolResult(success=False, content=f"未找到时间点: {point_id}")
        
        lines = [
            f"时间点：{point.label}",
            f"├──前一时间点: {context.timeline.get_prev(point_id).label if context.timeline.get_prev(point_id) else '无'}",
            f"├──后一时间点: {context.timeline.get_next(point_id).label if context.timeline.get_next(point_id) else '无'}",
            "├──涉及节点",
        ]
        
        for i, node_id in enumerate(point.node_ids):
            marker = "│  └──" if i == len(point.node_ids) - 1 else "│  ├──"
            node = context.graph.get_node(node_id) if context.graph else None
            lines.append(f"{marker}{node_id} ({node.type.value if node else '未知'})")
        
        lines.append("└──角色位置")
        for char_id, loc_id in point.character_locations.items():
            char = context.characters.get(char_id)
            loc = context.world_map.get_location(loc_id) if context.world_map else None
            char_name = char.name if char else char_id
            loc_name = loc.name if loc else loc_id
            lines.append(f"   └──{char_name} 在 {loc_name}")
        
        return ToolResult(success=True, content="\n".join(lines), data=point)
    
    else:
        # 返回整个时间轴
        points = context.timeline.get_ordered_points()
        lines = ["时间轴"]
        
        for i, p in enumerate(points):
            is_current = p.id == context.current_point_id
            marker = "└──" if i == len(points) - 1 else "├──"
            current_mark = " ★当前" if is_current else ""
            lines.append(f"{marker}{p.label}{current_mark}")
            
            # 显示该时间点的角色位置
            if p.character_locations:
                for char_id, loc_id in p.character_locations.items():
                    char = context.characters.get(char_id)
                    loc = context.world_map.get_location(loc_id) if context.world_map else None
                    prefix = "   └──" if i == len(points) - 1 else "│  └──"
                    lines.append(f"{prefix}{char.name if char else char_id} 在 {loc.name if loc else loc_id}")
        
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
        name = event.attrs.get('name', event.id)
        desc = event.attrs.get('description', '')
        time_point = ""
        
        if event.time_point_id and context.timeline:
            point = context.timeline.get_point(event.time_point_id)
            if point:
                time_point = f" [{point.label}]"
        
        lines.append(f"{marker}{name}{time_point}")
        if desc:
            prefix = "   " if i == len(events) - 1 else "│  "
            lines.append(f"{prefix}└──{desc[:50]}..." if len(desc) > 50 else f"{prefix}└──{desc}")
    
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
        if node.id == character_id or node.attrs.get('name') == character_id:
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
            target_card = context.characters.get(edge.target_id) if target_node else None
            target_name = target_card.name if target_card else edge.target_id
            
            marker = "│  └──" if i == len(out_edges) - 1 else "│  ├──"
            lines.append(f"{marker}→ {target_name} ({edge.type.value})")
    
    # 入边（其他角色对该角色的关系）
    in_edges = context.graph.find_edges_by_target(char_node.id)
    if in_edges:
        lines.append("└──被关系")
        for i, edge in enumerate(in_edges):
            source_node = context.graph.get_node(edge.source_id)
            source_card = context.characters.get(edge.source_id) if source_node else None
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
    ability_reveal: str = ""
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
        updates.append(f"新增备注: {note[:30]}..." if len(note) > 30 else f"新增备注: {note}")
    
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
        data=char
    )


def update_location(
    context: Any,
    character_id: str,
    location_id: str
) -> ToolResult:
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
        return ToolResult(
            success=False,
            content=f"未找到地点: {location_id}",
            suggestions=[f"可用地点: {', '.join(loc.name for loc in context.world_map.locations.values())}"]
        )
    
    loc_name = loc.name if loc else location_id
    
    # 获取原位置
    old_loc_id = context.timeline.get_character_location(context.current_point_id, character_id)
    old_loc = context.world_map.get_location(old_loc_id) if old_loc_id and context.world_map else None
    old_loc_name = old_loc.name if old_loc else old_loc_id or "未知"
    
    # 更新位置
    context.timeline.set_character_location(context.current_point_id, character_id, loc.id if loc else location_id)
    
    return ToolResult(
        success=True,
        content=f"角色 {char.name} 位置已更新:\n├──原位置: {old_loc_name}\n└──新位置: {loc_name}"
    )


def add_event(
    context: Any, event_name: str, description: str, involved_characters: list[str] | None = None, location_id: str = '', time_point_id: str = '') -> ToolResult:
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
    from src.core.graph import Edge, EdgeType, Node, NodeType
    import uuid
    
    if not context.graph:
        return ToolResult(success=False, content="无图结构，无法添加事件")
    
    # 创建事件节点
    event_id = f"event_{uuid.uuid4().hex[:8]}"
    event_node = Node(
        id=event_id,
        type=NodeType.EVENT,
        attrs={
            "name": event_name,
            "description": description
        }
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
                    target_id=char_id
                )
                context.graph.add_edge(edge)
                edges_created.append(char_name)
    
    lines = [
        f"事件创建成功: {event_name}",
        f"├──事件ID: {event_id}",
        f"├──描述: {description[:50]}..." if len(description) > 50 else f"├──描述: {description}",
    ]
    
    if edges_created:
        lines.append(f"└──涉及角色: {', '.join(edges_created)}")
    else:
        lines.append("└──涉及角色: 无")
    
    return ToolResult(
        success=True,
        content="\n".join(lines),
        data=event_node
    )


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
    
    if check_type in ("all", "position"):
        # 检查角色位置
        if context.timeline and context.current_point_id:
            point = context.timeline.get_point(context.current_point_id)
            if point:
                for char_id, loc_id in point.character_locations.items():
                    if context.world_map:
                        loc = context.world_map.get_location(loc_id)
                        if not loc:
                            issues.append(f"[位置] 角色 {char_id} 的位置 {loc_id} 不存在于地图中")
    
    if check_type in ("all", "timeline"):
        # 检查时间点连续性
        if context.timeline:
            points = context.timeline.get_ordered_points()
            for i, p in enumerate(points):
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
            suggestions=["可以继续进行创作"]
        )
    
    return ToolResult(
        success=False,
        content=f"发现 {len(issues)} 个问题:\n" + "\n".join(f"├──{i}" for i in issues),
        issues=issues
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
    
    # 基于时间轴建议
    if context.timeline:
        points = context.timeline.get_ordered_points()
        if context.current_point_id:
            current_idx = None
            for i, p in enumerate(points):
                if p.id == context.current_point_id:
                    current_idx = i
                    break
            
            if current_idx is not None:
                if current_idx < len(points) - 1:
                    next_point = points[current_idx + 1]
                    suggestions.append(f"下一时间点: {next_point.label}")
                else:
                    suggestions.append("已达时间轴末尾，可考虑创建新时间点")
    
    # 基于角色状态建议
    if context.characters:
        for char_id, char in context.characters.items():
            if char.last_action and not char.last_result:
                suggestions.append(f"角色 {char.name} 有待处理的行动: {char.last_action}")
            
            future_abilities = char.get_future_abilities()
            if future_abilities:
                suggestions.append(f"角色 {char.name} 有待解锁的能力: {', '.join(a.name for a in future_abilities)}")
    
    # 基于伏笔建议
    if context.graph:
        from src.core.graph import NodeType
        foreshadows = context.graph.find_nodes_by_type(NodeType.FORESHADOW)
        if foreshadows:
            unrevealed = [f.attrs.get('name', f.id) for f in foreshadows 
                         if not f.attrs.get('revealed', False)]
            if unrevealed:
                suggestions.append(f"待揭示的伏笔: {', '.join(unrevealed[:3])}")
    
    if not suggestions:
        suggestions.append("暂无特定建议，可根据剧情需要自由发展")
    
    return ToolResult(
        success=True,
        content="下一步发展建议:\n" + "\n".join(f"├──{s}" for s in suggestions),
        suggestions=suggestions
    )


# =============== 工具注册 ===============

def get_all_tools() -> dict[str, Tool]:
    """获取所有可用工具"""
    return {
        "query_character": Tool(
            name="query_character",
            description="查询角色的详细信息，包括能力、状态、备注等",
            tool_type=ToolType.QUERY,
            parameters={
                "character_id": "角色ID或名称"
            },
            execute=query_character
        ),
        "query_location": Tool(
            name="query_location",
            description="查询地点的详细信息，包括层级关系、相邻地点、当前在场角色",
            tool_type=ToolType.QUERY,
            parameters={
                "location_id": "地点ID或名称"
            },
            execute=query_location
        ),
        "query_timeline": Tool(
            name="query_timeline",
            description="查询时间轴信息，可查询单个时间点或整个时间轴",
            tool_type=ToolType.QUERY,
            parameters={
                "point_id": "时间点ID（可选）"
            },
            execute=query_timeline
        ),
        "query_events": Tool(
            name="query_events",
            description="查询事件列表",
            tool_type=ToolType.QUERY,
            parameters={
                "event_type": "事件类型过滤（可选）"
            },
            execute=query_events
        ),
        "query_relationships": Tool(
            name="query_relationships",
            description="查询角色之间的关系网络",
            tool_type=ToolType.QUERY,
            parameters={
                "character_id": "角色ID或名称"
            },
            execute=query_relationships
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
                "ability_reveal": "揭示能力名称（可选）"
            },
            execute=update_character
        ),
        "update_location": Tool(
            name="update_location",
            description="更新角色当前位置",
            tool_type=ToolType.UPDATE,
            parameters={
                "character_id": "角色ID或名称",
                "location_id": "目标地点ID或名称"
            },
            execute=update_location
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
                "time_point_id": "时间点（可选）"
            },
            execute=add_event
        ),
        "check_consistency": Tool(
            name="check_consistency",
            description="快速一致性检查，检测位置、时间等问题",
            tool_type=ToolType.HELPER,
            parameters={
                "check_type": "检查类型: all/position/timeline/character"
            },
            execute=check_consistency
        ),
        "suggest_next": Tool(
            name="suggest_next",
            description="基于当前状态建议下一步发展方向",
            tool_type=ToolType.HELPER,
            parameters={
                "current_situation": "当前情境描述（可选）"
            },
            execute=suggest_next
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
