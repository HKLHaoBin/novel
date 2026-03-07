"""角色卡系统"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Ability:
    """能力"""

    name: str
    is_public: bool = True  # 是否公开
    is_future: bool = False  # 是否将来获得
    description: str = ""  # 能力描述
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class CharacterCard:
    """角色卡"""

    id: str
    name: str
    gender: str = ""
    age: str = ""  # 年龄（可以是具体数字或描述）
    personality: str = ""  # 性格

    # 能力列表
    abilities: dict[str, Ability] = field(default_factory=dict)

    # 备注（详细状态描述）
    notes: list[str] = field(default_factory=list)

    # 最近一次行为和结果
    last_action: str = ""
    last_result: str = ""

    # 其他属性
    attrs: dict[str, Any] = field(default_factory=dict)

    def add_ability(self, ability: Ability) -> None:
        """添加能力"""
        self.abilities[ability.name] = ability

    def get_ability(self, name: str) -> Ability | None:
        """获取能力"""
        return self.abilities.get(name)

    def remove_ability(self, name: str) -> bool:
        """移除能力"""
        if name in self.abilities:
            del self.abilities[name]
            return True
        return False

    def get_public_abilities(self) -> list[Ability]:
        """获取公开能力"""
        return [a for a in self.abilities.values() if a.is_public and not a.is_future]

    def get_hidden_abilities(self) -> list[Ability]:
        """获取未公开能力"""
        return [
            a for a in self.abilities.values() if not a.is_public and not a.is_future
        ]

    def get_future_abilities(self) -> list[Ability]:
        """获取将来能力"""
        return [a for a in self.abilities.values() if a.is_future]

    def reveal_ability(self, name: str) -> bool:
        """揭示能力（未公开→公开）"""
        ability = self.get_ability(name)
        if ability and not ability.is_public:
            ability.is_public = True
            return True
        return False

    def unlock_ability(self, name: str) -> bool:
        """解锁能力（将来→现在）"""
        ability = self.get_ability(name)
        if ability and ability.is_future:
            ability.is_future = False
            return True
        return False

    def add_note(self, note: str) -> None:
        """添加备注"""
        self.notes.append(note)

    def clear_notes(self) -> None:
        """清空备注"""
        self.notes.clear()

    def update_last_action(self, action: str, result: str) -> None:
        """更新最近行为和结果"""
        self.last_action = action
        self.last_result = result

    def set_age(self, age: str) -> None:
        """设置年龄"""
        self.age = age

    def set_personality(self, personality: str) -> None:
        """设置性格"""
        self.personality = personality

    def update_attr(self, key: str, value: Any) -> None:
        """更新自定义属性"""
        self.attrs[key] = value

    def get_attr(self, key: str, default: Any = None) -> Any:
        """获取自定义属性"""
        return self.attrs.get(key, default)
