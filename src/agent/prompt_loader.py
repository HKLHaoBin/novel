"""提示词加载器 - 从 markdown 文件加载 Agent 提示词"""

from pathlib import Path
from typing import Any

import yaml


def load_prompt_template(prompt_name: str) -> dict[str, Any]:
    """
    从 markdown 文件加载提示词模板
    
    Args:
        prompt_name: 提示词名称（如 'designer', 'writer', 'auditor', 'polisher'）
        
    Returns:
        包含元数据和内容的字典
    """
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_file = prompt_dir / f"{prompt_name}.md"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"提示词文件不存在: {prompt_file}")
    
    content = prompt_file.read_text(encoding="utf-8")
    
    # 解析 YAML front matter
    metadata: dict[str, Any] = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            front_matter = parts[1].strip()
            metadata = yaml.safe_load(front_matter) or {}
            main_content = parts[2].strip()
        else:
            main_content = content
    else:
        main_content = content
    
    return {
        "metadata": metadata,
        "content": main_content,
        "name": metadata.get("name", prompt_name),
        "description": metadata.get("description", ""),
        "color": metadata.get("color", "default"),
    }


def get_system_prompt(prompt_name: str) -> str:
    """
    获取系统提示词（完整的 markdown 内容）
    
    Args:
        prompt_name: 提示词名称
        
    Returns:
        系统提示词文本
    """
    template = load_prompt_template(prompt_name)
    return template["content"]


def get_agent_info(prompt_name: str) -> dict[str, str]:
    """
    获取 Agent 基本信息
    
    Args:
        prompt_name: 提示词名称
        
    Returns:
        包含 name, description, color 的字典
    """
    template = load_prompt_template(prompt_name)
    metadata = template["metadata"]
    return {
        "name": metadata.get("name", prompt_name),
        "description": metadata.get("description", ""),
        "color": metadata.get("color", "default"),
    }


# 预定义的提示词名称
PROMPT_NAMES = ["designer", "writer", "auditor", "polisher"]


def list_available_prompts() -> list[str]:
    """列出所有可用的提示词"""
    return PROMPT_NAMES.copy()


class PromptLibrary:
    """提示词库"""
    
    _instance = None
    _prompts: dict[str, dict] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get(self, name: str) -> dict[str, Any]:
        """获取提示词（带缓存）"""
        if name not in self._prompts:
            self._prompts[name] = load_prompt_template(name)
        return self._prompts[name]
    
    def get_system_prompt(self, name: str) -> str:
        """获取系统提示词"""
        return self.get(name)["content"]
    
    def get_metadata(self, name: str) -> dict[str, Any]:
        """获取元数据"""
        return self.get(name)["metadata"]
    
    def reload(self, name: str | None = None) -> None:
        """重新加载提示词"""
        if name:
            if name in self._prompts:
                del self._prompts[name]
        else:
            self._prompts.clear()


# 全局提示词库实例
prompt_library = PromptLibrary()
