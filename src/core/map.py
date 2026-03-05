"""地图系统"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LocationType(Enum):
    """地点类型"""
    WORLD = "world"           # 世界
    CONTINENT = "continent"   # 大陆
    COUNTRY = "country"       # 国家
    REGION = "region"         # 区域
    CITY = "city"             # 城市
    DISTRICT = "district"     # 区/区域
    BUILDING = "building"     # 建筑
    ROOM = "room"             # 房间
    OTHER = "other"           # 其他


class LocationRelation(Enum):
    """地点关系类型"""
    CONTAINS = "contains"     # 包含（父级）
    ADJACENT = "adjacent"     # 相邻
    CONNECTED = "connected"   # 可达（有路径）


@dataclass
class Location:
    """地点"""
    id: str
    name: str
    type: LocationType = LocationType.OTHER
    description: str = ""
    parent_id: str | None = None        # 父级地点（层级关系）
    attrs: dict[str, Any] = field(default_factory=dict)

    def set_parent(self, parent_id: str) -> None:
        """设置父级地点"""
        self.parent_id = parent_id


@dataclass
class LocationEdge:
    """地点关系边"""
    id: str
    type: LocationRelation
    source_id: str
    target_id: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldMap:
    """世界地图"""
    locations: dict[str, Location] = field(default_factory=dict)
    edges: dict[str, LocationEdge] = field(default_factory=dict)

    def add_location(self, location: Location) -> None:
        """添加地点"""
        self.locations[location.id] = location

    def get_location(self, location_id: str) -> Location | None:
        """获取地点"""
        return self.locations.get(location_id)

    def remove_location(self, location_id: str) -> bool:
        """删除地点"""
        if location_id not in self.locations:
            return False
        del self.locations[location_id]
        # 删除相关的边
        self.edges = {
            eid: e for eid, e in self.edges.items()
            if e.source_id != location_id and e.target_id != location_id
        }
        return True

    def add_edge(self, edge: LocationEdge) -> None:
        """添加地点关系"""
        self.edges[edge.id] = edge

    def get_edge(self, edge_id: str) -> LocationEdge | None:
        """获取地点关系"""
        return self.edges.get(edge_id)

    def remove_edge(self, edge_id: str) -> bool:
        """删除地点关系"""
        if edge_id not in self.edges:
            return False
        del self.edges[edge_id]
        return True

    def get_children(self, location_id: str) -> list[Location]:
        """获取子地点"""
        return [loc for loc in self.locations.values() if loc.parent_id == location_id]

    def get_parent(self, location_id: str) -> Location | None:
        """获取父地点"""
        loc = self.get_location(location_id)
        if loc and loc.parent_id:
            return self.get_location(loc.parent_id)
        return None

    def get_ancestors(self, location_id: str) -> list[Location]:
        """获取所有祖先地点（从近到远）"""
        ancestors = []
        loc = self.get_location(location_id)
        while loc and loc.parent_id:
            parent = self.get_location(loc.parent_id)
            if parent:
                ancestors.append(parent)
                loc = parent
            else:
                break
        return ancestors

    def get_descendants(self, location_id: str) -> list[Location]:
        """获取所有后代地点"""
        result = []
        children = self.get_children(location_id)
        for child in children:
            result.append(child)
            result.extend(self.get_descendants(child.id))
        return result

    def get_adjacent_locations(self, location_id: str) -> list[Location]:
        """获取相邻地点"""
        result = []
        for edge in self.edges.values():
            if edge.type == LocationRelation.ADJACENT:
                if edge.source_id == location_id:
                    loc = self.get_location(edge.target_id)
                    if loc:
                        result.append(loc)
                elif edge.target_id == location_id:
                    loc = self.get_location(edge.source_id)
                    if loc:
                        result.append(loc)
        return result

    def find_location_by_name(self, name: str) -> Location | None:
        """按名称查找地点"""
        for loc in self.locations.values():
            if loc.name == name:
                return loc
        return None

    def find_locations_by_type(self, loc_type: LocationType) -> list[Location]:
        """按类型查找地点"""
        return [loc for loc in self.locations.values() if loc.type == loc_type]
