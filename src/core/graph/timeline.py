"""时间线系统 - 链表结构确保有序性"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimePoint:
    """时间点"""

    id: str
    label: str  # 时间表达：如"第三章"、"主角离家后第二天"
    prev_id: str | None = None  # 前一个时间点
    next_id: str | None = None  # 后一个时间点
    node_ids: list[str] = field(default_factory=list)  # 该时间点的节点
    # 角色位置记录：{角色卡ID: 地点ID}
    character_locations: dict[str, str] = field(default_factory=dict)
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Timeline:
    """时间轴 - 双向链表实现"""

    id: str = ""
    name: str = ""  # 时间线名称：主线、支线A...
    points: dict[str, TimePoint] = field(default_factory=dict)
    head_id: str | None = None  # 链表头
    tail_id: str | None = None  # 链表尾

    def append(self, point: TimePoint) -> None:
        """在末尾添加时间点"""
        point.prev_id = self.tail_id
        point.next_id = None
        self.points[point.id] = point

        if self.tail_id:
            self.points[self.tail_id].next_id = point.id
        else:
            self.head_id = point.id
        self.tail_id = point.id

    def prepend(self, point: TimePoint) -> None:
        """在开头添加时间点"""
        point.prev_id = None
        point.next_id = self.head_id
        self.points[point.id] = point

        if self.head_id:
            self.points[self.head_id].prev_id = point.id
        else:
            self.tail_id = point.id
        self.head_id = point.id

    def insert_after(self, target_id: str, point: TimePoint) -> bool:
        """在指定时间点后插入"""
        if target_id not in self.points:
            return False

        target = self.points[target_id]
        point.prev_id = target_id
        point.next_id = target.next_id
        self.points[point.id] = point

        target.next_id = point.id
        if point.next_id:
            self.points[point.next_id].prev_id = point.id
        else:
            self.tail_id = point.id
        return True

    def insert_before(self, target_id: str, point: TimePoint) -> bool:
        """在指定时间点前插入"""
        if target_id not in self.points:
            return False

        target = self.points[target_id]
        point.prev_id = target.prev_id
        point.next_id = target_id
        self.points[point.id] = point

        target.prev_id = point.id
        if point.prev_id:
            self.points[point.prev_id].next_id = point.id
        else:
            self.head_id = point.id
        return True

    def get_point(self, point_id: str) -> TimePoint | None:
        """获取时间点"""
        return self.points.get(point_id)

    def remove_point(self, point_id: str) -> bool:
        """删除时间点并重连链表"""
        if point_id not in self.points:
            return False

        point = self.points[point_id]

        # 重连前驱
        if point.prev_id:
            self.points[point.prev_id].next_id = point.next_id
        else:
            self.head_id = point.next_id

        # 重连后继
        if point.next_id:
            self.points[point.next_id].prev_id = point.prev_id
        else:
            self.tail_id = point.prev_id

        del self.points[point_id]
        return True

    def get_ordered_points(self) -> list[TimePoint]:
        """获取按顺序排列的时间点（遍历链表）"""
        result = []
        current_id = self.head_id
        while current_id:
            point = self.points.get(current_id)
            if point:
                result.append(point)
                current_id = point.next_id
            else:
                break
        return result

    def get_next(self, point_id: str) -> TimePoint | None:
        """获取下一个时间点"""
        point = self.get_point(point_id)
        if point and point.next_id:
            return self.get_point(point.next_id)
        return None

    def get_prev(self, point_id: str) -> TimePoint | None:
        """获取上一个时间点"""
        point = self.get_point(point_id)
        if point and point.prev_id:
            return self.get_point(point.prev_id)
        return None

    def find_point_by_label(self, label: str) -> TimePoint | None:
        """按标签查找时间点"""
        for point in self.points.values():
            if point.label == label:
                return point
        return None

    def add_node_to_point(self, point_id: str, node_id: str) -> bool:
        """将节点添加到时间点"""
        point = self.get_point(point_id)
        if point is None:
            return False
        if node_id not in point.node_ids:
            point.node_ids.append(node_id)
        return True

    def remove_node_from_point(self, point_id: str, node_id: str) -> bool:
        """从时间点移除节点"""
        point = self.get_point(point_id)
        if point is None:
            return False
        if node_id in point.node_ids:
            point.node_ids.remove(node_id)
        return True

    def get_nodes_at(self, point_id: str) -> list[str]:
        """获取某时间点的所有节点"""
        point = self.get_point(point_id)
        return point.node_ids if point else []

    def is_empty(self) -> bool:
        """时间轴是否为空"""
        return len(self.points) == 0

    def __len__(self) -> int:
        return len(self.points)

    # === 角色位置管理 ===

    def set_character_location(
        self, point_id: str, character_id: str, location_id: str
    ) -> bool:
        """设置角色在某时间点的位置"""
        point = self.get_point(point_id)
        if point is None:
            return False
        point.character_locations[character_id] = location_id
        return True

    def get_character_location(self, point_id: str, character_id: str) -> str | None:
        """获取角色在某时间点的位置"""
        point = self.get_point(point_id)
        if point is None:
            return None
        return point.character_locations.get(character_id)

    def remove_character_location(self, point_id: str, character_id: str) -> bool:
        """移除角色在某时间点的位置"""
        point = self.get_point(point_id)
        if point is None:
            return False
        if character_id in point.character_locations:
            del point.character_locations[character_id]
            return True
        return False

    def get_characters_at_location(self, point_id: str, location_id: str) -> list[str]:
        """获取某时间点在某地点的所有角色"""
        point = self.get_point(point_id)
        if point is None:
            return []
        return [
            char_id
            for char_id, loc_id in point.character_locations.items()
            if loc_id == location_id
        ]

    def get_all_locations_at(self, point_id: str) -> dict[str, str]:
        """获取某时间点所有角色的位置"""
        point = self.get_point(point_id)
        return point.character_locations.copy() if point else {}

    def inherit_locations_from_prev(
        self, point_id: str, character_ids: list[str] | None = None
    ) -> bool:
        """从上一个时间点继承角色位置（用于新时间点初始化）"""
        point = self.get_point(point_id)
        if point is None or point.prev_id is None:
            return False

        prev_point = self.get_point(point.prev_id)
        if prev_point is None:
            return False

        # 继承所有或指定角色的位置
        if character_ids:
            for char_id in character_ids:
                if char_id in prev_point.character_locations:
                    point.character_locations[char_id] = prev_point.character_locations[
                        char_id
                    ]
        else:
            point.character_locations = prev_point.character_locations.copy()
        return True
