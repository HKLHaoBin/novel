"""小说生成协调器 - 整合所有模块完成生成流程"""

from dataclasses import dataclass, field
from typing import Any

from src.core.character import Ability, CharacterCard
from src.core.graph import Edge, EdgeType, Graph, Node, NodeType, TimePoint, Timeline
from src.core.map import Location, LocationType, WorldMap
from src.core.state import (
    AgentSnapshot,
    GenerationPhase,
    GenerationProgress,
    NovelSnapshot,
    NovelStateManager,
)


@dataclass
class NovelContext:
    """小说运行时上下文"""
    
    # 快照（状态管理）
    snapshot: NovelSnapshot
    
    # 核心数据结构
    graph: Graph = field(default_factory=Graph)
    timeline: Timeline = field(default_factory=Timeline)
    world_map: WorldMap = field(default_factory=WorldMap)
    characters: dict[str, CharacterCard] = field(default_factory=dict)
    
    # Agent 状态
    agent_snapshot: AgentSnapshot = field(default_factory=AgentSnapshot)
    
    # 全局摘要
    global_summary: str = ""


class NovelCoordinator:
    """小说生成协调器"""
    
    def __init__(self, save_dir: str = "./novels"):
        self.state_manager = NovelStateManager(save_dir)
    
    # ========== 创建/加载 ==========
    
    def create_novel(self, title: str, user_prompt: str) -> NovelContext:
        """创建新小说"""
        snapshot = NovelSnapshot(
            id=f"novel_{hash(title) % 1000000:06d}",
            title=title,
            created_at=self._now(),
            updated_at=self._now(),
            user_prompt=user_prompt,
            progress=GenerationProgress(current_phase=GenerationPhase.NOT_STARTED),
        )
        
        context = NovelContext(
            snapshot=snapshot,
            graph=Graph(),
            timeline=Timeline(id="main", name="主线时间轴"),
            world_map=WorldMap(),
            characters={},
            agent_snapshot=AgentSnapshot(),
        )
        
        # 保存初始状态
        self._sync_to_snapshot(context)
        self.state_manager.save_draft(snapshot)
        
        return context
    
    def load_novel(self, title: str) -> NovelContext | None:
        """加载已有小说"""
        snapshot = self.state_manager.load_latest_draft(title)
        
        if not snapshot:
            return None
        
        context = NovelContext(
            snapshot=snapshot,
            graph=Graph(),
            timeline=Timeline(id="main", name="主线时间轴"),
            world_map=WorldMap(),
            characters={},
            agent_snapshot=snapshot.agent_snapshot,
            global_summary=snapshot.global_summary,
        )
        
        # 从快照恢复
        self._restore_from_snapshot(context)
        
        return context
    
    def save_novel(self, context: NovelContext) -> str:
        """保存小说状态"""
        # 同步运行时数据到快照
        self._sync_to_snapshot(context)
        
        # 保存半成品
        return self.state_manager.save_draft(context.snapshot)
    
    # ========== 数据同步 ==========
    
    def _sync_to_snapshot(self, context: NovelContext) -> None:
        """将运行时数据同步到快照"""
        snapshot = context.snapshot
        
        snapshot.updated_at = self._now()
        snapshot.global_summary = context.global_summary
        snapshot.agent_snapshot = context.agent_snapshot
        
        # 序列化图结构
        snapshot.graph_data = {
            "nodes": {
                nid: {
                    "id": n.id,
                    "type": n.type.value,
                    "attrs": n.attrs,
                    "time_point_id": n.time_point_id,
                    "timeline_id": n.timeline_id,
                    "character_card_id": n.character_card_id,
                }
                for nid, n in context.graph.nodes.items()
            },
            "edges": {
                eid: {
                    "id": e.id,
                    "type": e.type.value,
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "attrs": e.attrs,
                }
                for eid, e in context.graph.edges.items()
            },
        }
        
        # 序列化时间轴
        snapshot.timeline_data = {
            "id": context.timeline.id,
            "name": context.timeline.name,
            "head_id": context.timeline.head_id,
            "tail_id": context.timeline.tail_id,
            "points": {
                pid: {
                    "id": p.id,
                    "label": p.label,
                    "prev_id": p.prev_id,
                    "next_id": p.next_id,
                    "node_ids": p.node_ids,
                    "character_locations": p.character_locations,
                    "attrs": p.attrs,
                }
                for pid, p in context.timeline.points.items()
            },
        }
        
        # 序列化地图
        snapshot.world_map_data = {
            "locations": {
                lid: {
                    "id": loc.id,
                    "name": loc.name,
                    "type": loc.type.value,
                    "description": loc.description,
                    "parent_id": loc.parent_id,
                    "attrs": loc.attrs,
                }
                for lid, loc in context.world_map.locations.items()
            },
            "edges": {
                eid: {
                    "id": e.id,
                    "type": e.type.value,
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "attrs": e.attrs,
                }
                for eid, e in context.world_map.edges.items()
            },
        }
        
        # 序列化角色卡
        snapshot.characters_data = {
            cid: {
                "id": c.id,
                "name": c.name,
                "gender": c.gender,
                "age": c.age,
                "personality": c.personality,
                "notes": c.notes,
                "last_action": c.last_action,
                "last_result": c.last_result,
                "attrs": c.attrs,
                "abilities": {
                    aid: {
                        "name": a.name,
                        "is_public": a.is_public,
                        "is_future": a.is_future,
                        "description": a.description,
                        "attrs": a.attrs,
                    }
                    for aid, a in c.abilities.items()
                },
            }
            for cid, c in context.characters.items()
        }
    
    def _restore_from_snapshot(self, context: NovelContext) -> None:
        """从快照恢复运行时数据"""
        snapshot = context.snapshot
        
        # 恢复图结构
        graph_data = snapshot.graph_data
        for nid, n in graph_data.get("nodes", {}).items():
            node = Node(
                id=n["id"],
                type=NodeType(n["type"]),
                attrs=n.get("attrs", {}),
            )
            node.time_point_id = n.get("time_point_id")
            node.timeline_id = n.get("timeline_id")
            node.character_card_id = n.get("character_card_id")
            context.graph.add_node(node)
        
        for eid, e in graph_data.get("edges", {}).items():
            context.graph.add_edge(Edge(
                id=e["id"],
                type=EdgeType(e["type"]),
                source_id=e["source_id"],
                target_id=e["target_id"],
                attrs=e.get("attrs", {}),
            ))
        
        # 恢复时间轴
        timeline_data = snapshot.timeline_data
        context.timeline.id = timeline_data.get("id", "main")
        context.timeline.name = timeline_data.get("name", "主线时间轴")
        context.timeline.head_id = timeline_data.get("head_id")
        context.timeline.tail_id = timeline_data.get("tail_id")
        
        for pid, p in timeline_data.get("points", {}).items():
            point = TimePoint(
                id=p["id"],
                label=p["label"],
                prev_id=p.get("prev_id"),
                next_id=p.get("next_id"),
                node_ids=p.get("node_ids", []),
                character_locations=p.get("character_locations", {}),
                attrs=p.get("attrs", {}),
            )
            context.timeline.points[point.id] = point
        
        # 恢复地图
        map_data = snapshot.world_map_data
        for lid, loc_data in map_data.get("locations", {}).items():
            from src.core.map import LocationRelation
            
            loc = Location(
                id=loc_data["id"],
                name=loc_data["name"],
                type=LocationType(loc_data["type"]),
                description=loc_data.get("description", ""),
                parent_id=loc_data.get("parent_id"),
                attrs=loc_data.get("attrs", {}),
            )
            context.world_map.add_location(loc)
        
        for eid, e in map_data.get("edges", {}).items():
            from src.core.map import LocationEdge
            context.world_map.add_edge(LocationEdge(
                id=e["id"],
                type=LocationRelation(e["type"]),
                source_id=e["source_id"],
                target_id=e["target_id"],
                attrs=e.get("attrs", {}),
            ))
        
        # 恢复角色卡
        for cid, c in snapshot.characters_data.items():
            card = CharacterCard(
                id=c["id"],
                name=c["name"],
                gender=c.get("gender", ""),
                age=c.get("age", ""),
                personality=c.get("personality", ""),
                notes=c.get("notes", []),
                last_action=c.get("last_action", ""),
                last_result=c.get("last_result", ""),
                attrs=c.get("attrs", {}),
            )
            for aid, a in c.get("abilities", {}).items():
                card.add_ability(Ability(
                    name=a["name"],
                    is_public=a.get("is_public", True),
                    is_future=a.get("is_future", False),
                    description=a.get("description", ""),
                    attrs=a.get("attrs", {}),
                ))
            context.characters[cid] = card
        
        context.global_summary = snapshot.global_summary
    
    # ========== 章节管理 ==========
    
    def complete_chapter(self, context: NovelContext, chapter_num: int, 
                        content: str, title: str = "") -> None:
        """完成章节"""
        self.state_manager.complete_chapter(
            context.snapshot, chapter_num, content, title
        )
        
        # 同步到快照
        self._sync_to_snapshot(context)
    
    def save_checkpoint(self, context: NovelContext) -> str:
        """保存检查点"""
        return self.save_novel(context)
    
    # ========== 列表查询 ==========
    
    def list_novels(self) -> list[dict]:
        """列出所有小说"""
        return self.state_manager.list_novels()
    
    def list_chapters(self, title: str) -> list[dict]:
        """列出成品章节"""
        return self.state_manager.list_chapters(title)
    
    def list_drafts(self, title: str) -> list[dict]:
        """列出局成品"""
        return self.state_manager.list_drafts(title)
    
    def load_chapter(self, title: str, chapter_num: int) -> str | None:
        """加载成品章节"""
        return self.state_manager.load_chapter(title, chapter_num)
    
    # ========== Agent 上下文构建 ==========
    
    def build_agent_context(self, context: NovelContext) -> Any:
        """构建 Agent 执行上下文"""
        from src.agent import AgentContext
        
        # 获取当前时间点
        current_point_id = None
        if context.timeline.points:
            if context.snapshot.progress.current_chapter:
                # 尝试找到对应的时间点
                points = context.timeline.get_ordered_points()
                chapter_idx = context.snapshot.progress.current_chapter - 1
                if 0 <= chapter_idx < len(points):
                    current_point_id = points[chapter_idx].id
            if not current_point_id:
                current_point_id = context.timeline.head_id
        
        return AgentContext(
            graph=context.graph,
            timeline=context.timeline,
            world_map=context.world_map,
            characters=context.characters,
            current_point_id=current_point_id,
            user_input=context.snapshot.user_prompt,
            extra={
                "user_guidance": context.snapshot.user_guidance,
                "global_summary": context.global_summary,
                "chapter_num": context.snapshot.progress.current_chapter,
                "total_chapters": context.snapshot.progress.total_chapters,
            }
        )
    
    def update_agent_state(self, context: NovelContext, agent_name: str,
                          prompt: str = "", response: str = "",
                          summary: str = "") -> None:
        """更新 Agent 状态"""
        context.agent_snapshot.current_agent = agent_name
        if prompt:
            context.agent_snapshot.last_prompt = prompt
        if response:
            context.agent_snapshot.last_response = response
        if summary:
            context.agent_snapshot.context_summary = summary
        context.agent_snapshot.iteration_count += 1
    
    # ========== 工具方法 ==========
    
    def _now(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
    
    def can_resume(self, context: NovelContext) -> bool:
        """是否可以续传"""
        return context.snapshot.progress.current_phase != GenerationPhase.NOT_STARTED
    
    def get_resume_info(self, context: NovelContext) -> dict:
        """获取续传信息"""
        progress = context.snapshot.progress
        phase = progress.current_phase
        
        if phase == GenerationPhase.NOT_STARTED:
            return {"action": "start", "message": "开始新小说"}
        
        elif phase == GenerationPhase.WRITING:
            current = progress.current_chapter
            completed = progress.completed_chapters
            next_chapter = current + 1 if current in completed else current
            
            return {
                "action": "continue_writing",
                "message": f"继续撰写第 {next_chapter} 章",
                "chapter": next_chapter,
                "completed": completed,
            }
        
        elif phase == GenerationPhase.COMPLETED:
            return {"action": "completed", "message": "小说已完成"}
        
        else:
            return {
                "action": f"continue_{phase.value}",
                "message": f"继续 {phase.value} 阶段",
            }