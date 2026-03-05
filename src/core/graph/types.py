"""图结构的基础类型定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(Enum):
    """节点类型枚举"""
    WORLD = "world"
    CHARACTER = "character"
    MAIN_PLOT = "main_plot"
    SUB_PLOT = "sub_plot"
    EVENT = "event"
    TIMELINE = "timeline"
    LOCATION = "location"
    FORESHADOW = "foreshadow"


class EdgeType(Enum):
    """边类型枚举"""
    BELONGS_TO = "belongs_to"
    INVOLVES = "involves"
    CAUSES = "causes"
    HAPPENS_AT = "happens_at"
    FORESHADOWS = "foreshadows"
    RELATES = "relates"


@dataclass
class Node:
    """图节点"""
    id: str
    type: NodeType
    attrs: dict[str, Any] = field(default_factory=dict)
    # 时间归属（双向关联 Timeline）
    time_point_id: str | None = None
    timeline_id: str | None = None
    # 角色卡关联（仅 CHARACTER 类型节点使用，单向绑定）
    character_card_id: str | None = None


@dataclass
class Edge:
    """图边"""
    id: str
    type: EdgeType
    source_id: str
    target_id: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph:
    """图结构"""
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """添加节点"""
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> Node | None:
        """获取节点"""
        return self.nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        """删除节点（同时删除相关的边）"""
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        # 删除相关的边
        self.edges = {
            eid: e for eid, e in self.edges.items()
            if e.source_id != node_id and e.target_id != node_id
        }
        return True

    def add_edge(self, edge: Edge) -> None:
        """添加边"""
        self.edges[edge.id] = edge

    def get_edge(self, edge_id: str) -> Edge | None:
        """获取边"""
        return self.edges.get(edge_id)

    def remove_edge(self, edge_id: str) -> bool:
        """删除边"""
        if edge_id not in self.edges:
            return False
        del self.edges[edge_id]
        return True

    def find_nodes_by_type(self, node_type: NodeType) -> list[Node]:
        """按类型查找节点"""
        return [n for n in self.nodes.values() if n.type == node_type]

    def find_edges_by_source(self, source_id: str) -> list[Edge]:
        """查找从指定节点出发的边"""
        return [e for e in self.edges.values() if e.source_id == source_id]

    def find_edges_by_target(self, target_id: str) -> list[Edge]:
        """查找指向指定节点的边"""
        return [e for e in self.edges.values() if e.target_id == target_id]

    def find_neighbors(self, node_id: str) -> list[str]:
        """查找相邻节点"""
        neighbors = set()
        for e in self.edges.values():
            if e.source_id == node_id:
                neighbors.add(e.target_id)
            elif e.target_id == node_id:
                neighbors.add(e.source_id)
        return list(neighbors)
