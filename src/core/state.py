"""小说状态管理 - 保存、加载、断点续传

设计：
- 成品：小说名目录/章节.txt
- 半成品：小说名目录/drafts/小说名_章节数.novel（gzip压缩JSON）
- 最多保留最近10个存档
"""

import gzip
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
import uuid


class GenerationPhase(Enum):
    """生成阶段"""
    NOT_STARTED = "not_started"
    ARCHITECTURE = "architecture"
    CHARACTERS = "characters"
    WORLD = "world"
    PLOT = "plot"
    BLUEPRINT = "blueprint"
    WRITING = "writing"
    COMPLETED = "completed"


@dataclass
class ChapterStatus:
    """章节状态"""
    chapter_num: int
    title: str
    is_generated: bool = False
    is_polished: bool = False
    is_audited: bool = False
    content: str = ""
    word_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class GenerationProgress:
    """生成进度"""
    current_phase: GenerationPhase = GenerationPhase.NOT_STARTED
    current_chapter: int = 0
    total_chapters: int = 0
    completed_chapters: list[int] = field(default_factory=list)
    
    architecture_done: bool = False
    characters_done: bool = False
    world_done: bool = False
    plot_done: bool = False
    blueprint_done: bool = False
    
    last_error: str = ""
    retry_count: int = 0


@dataclass
class AgentSnapshot:
    """Agent 状态快照"""
    current_agent: str = ""           # 当前运行的 Agent
    last_prompt: str = ""             # 最后的提示词
    last_response: str = ""           # 最后的响应
    context_summary: str = ""         # 上下文摘要
    iteration_count: int = 0          # 迭代次数
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class NovelSnapshot:
    """小说完整快照 - 用于序列化"""
    # 基本信息
    id: str
    title: str
    created_at: str
    updated_at: str
    
    # 用户输入
    user_prompt: str = ""
    user_guidance: str = ""
    
    # 生成进度
    progress: GenerationProgress = field(default_factory=GenerationProgress)
    
    # 章节状态
    chapters: dict[int, ChapterStatus] = field(default_factory=dict)
    
    # Agent 状态
    agent_snapshot: AgentSnapshot = field(default_factory=AgentSnapshot)
    
    # 全局摘要
    global_summary: str = ""
    
    # === 核心数据结构 ===
    graph_data: dict = field(default_factory=dict)      # 图结构
    timeline_data: dict = field(default_factory=dict)   # 时间轴
    world_map_data: dict = field(default_factory=dict)  # 地图
    characters_data: dict = field(default_factory=dict) # 角色卡
    
    def __post_init__(self):
        if not self.id:
            self.id = f"novel_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class NovelStateManager:
    """小说状态管理器"""
    
    MAX_DRAFTS = 10  # 最多保留的半成品数量
    
    def __init__(self, save_dir: str = "./novels"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
    
    # ========== 成品管理 ==========
    
    def _get_novel_dir(self, title: str) -> Path:
        """获取小说目录"""
        return self.save_dir / title
    
    def _get_drafts_dir(self, title: str) -> Path:
        """获取半成品目录"""
        return self._get_novel_dir(title) / "drafts"
    
    def save_chapter(self, title: str, chapter_num: int, content: str, chapter_title: str = "") -> str:
        """保存成品章节
        
        Args:
            title: 小说名
            chapter_num: 章节号
            content: 章节内容
            chapter_title: 章节标题（可选）
            
        Returns:
            文件路径
        """
        novel_dir = self._get_novel_dir(title)
        novel_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件名格式：第1章 章节名.txt
        if chapter_title:
            filename = f"第{chapter_num}章 {chapter_title}.txt"
        else:
            filename = f"第{chapter_num}章.txt"
        
        chapter_file = novel_dir / filename
        
        with open(chapter_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(chapter_file)
    
    def load_chapter(self, title: str, chapter_num: int) -> str | None:
        """加载成品章节
        
        Args:
            title: 小说名
            chapter_num: 章节号
            
        Returns:
            章节内容，不存在返回 None
        """
        novel_dir = self._get_novel_dir(title)
        
        # 查找匹配的章节文件（第N章 *.txt）
        for f in novel_dir.glob(f"第{chapter_num}章*.txt"):
            return f.read_text(encoding='utf-8')
        
        return None
    
    def list_chapters(self, title: str) -> list[dict]:
        """列出所有成品章节
        
        Returns:
            [{"chapter_num": 1, "title": "初入江湖", "filename": "第1章 初入江湖.txt", "word_count": 3000}, ...]
        """
        novel_dir = self._get_novel_dir(title)
        chapters: list[dict] = []
        
        if not novel_dir.exists():
            return chapters
        
        import re
        
        for f in sorted(novel_dir.glob("第*章*.txt")):
            # 解析文件名：第1章 标题.txt 或 第1章.txt
            match = re.match(r"第(\d+)章\s*(.*?)\.txt$", f.name)
            if match:
                chapter_num = int(match.group(1))
                chapter_title = match.group(2).strip()
                content = f.read_text(encoding='utf-8')
                chapters.append({
                    "chapter_num": chapter_num,
                    "title": chapter_title,
                    "filename": f.name,
                    "word_count": len(content),
                })
        
        return sorted(chapters, key=lambda x: x["chapter_num"])
    
    # ========== 半成品管理 ==========
    
    def save_draft(self, snapshot: NovelSnapshot) -> str:
        """保存半成品状态（gzip压缩JSON）"""
        drafts_dir = self._get_drafts_dir(snapshot.title)
        drafts_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件名：小说名_章节数.novel
        chapter_num = snapshot.progress.current_chapter or len(snapshot.chapters)
        filename = f"{snapshot.title}_第{chapter_num}章.novel"
        filepath = drafts_dir / filename
        
        # 序列化
        data = self._serialize_snapshot(snapshot)
        json_str = json.dumps(data, ensure_ascii=False)
        
        # gzip 压缩写入
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            f.write(json_str)
        
        # 清理旧的存档，只保留最近10个
        self._cleanup_old_drafts(drafts_dir)
        
        return str(filepath)
    
    def load_draft(self, title: str, filename: str | None = None) -> NovelSnapshot | None:
        """加载半成品状态"""
        drafts_dir = self._get_drafts_dir(title)
        
        if filename:
            filepath = drafts_dir / filename
        else:
            # 加载最新的
            drafts = sorted(drafts_dir.glob("*.novel"), reverse=True)
            if not drafts:
                return None
            filepath = drafts[0]
        
        if not filepath.exists():
            return None
        
        # gzip 解压读取
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            data = json.load(f)
        
        return self._deserialize_snapshot(data)
    
    def load_latest_draft(self, title: str) -> NovelSnapshot | None:
        """加载最新的半成品"""
        return self.load_draft(title)
    
    def list_drafts(self, title: str) -> list[dict]:
        """列出所有半成品"""
        drafts_dir = self._get_drafts_dir(title)
        drafts: list[dict] = []
        
        if not drafts_dir.exists():
            return drafts
        
        for f in sorted(drafts_dir.glob("*.novel"), reverse=True):
            # 解压读取元数据
            with gzip.open(f, 'rt', encoding='utf-8') as fp:
                data = json.load(fp)
            
            drafts.append({
                "filename": f.name,
                "updated_at": data.get("updated_at", ""),
                "phase": data.get("progress", {}).get("current_phase", ""),
                "chapter": data.get("progress", {}).get("current_chapter", 0),
                "size_kb": f.stat().st_size // 1024,
            })
        
        return drafts
    
    def delete_draft(self, title: str, filename: str) -> bool:
        """删除指定半成品"""
        filepath = self._get_drafts_dir(title) / filename
        
        if filepath.exists():
            filepath.unlink()
            return True
        return False
    
    def _cleanup_old_drafts(self, drafts_dir: Path) -> None:
        """清理旧的存档，只保留最近 MAX_DRAFTS 个"""
        drafts = sorted(drafts_dir.glob("*.novel"), reverse=True)
        
        for old_draft in drafts[self.MAX_DRAFTS:]:
            old_draft.unlink()
    
    # ========== 小说管理 ==========
    
    def list_novels(self) -> list[dict]:
        """列出所有小说"""
        novels = []
        
        for novel_dir in self.save_dir.iterdir():
            if novel_dir.is_dir():
                title = novel_dir.name
                chapters = self.list_chapters(title)
                drafts = self.list_drafts(title)
                
                novels.append({
                    "title": title,
                    "chapter_count": len(chapters),
                    "total_words": sum(c["word_count"] for c in chapters),
                    "draft_count": len(drafts),
                    "last_draft": drafts[0] if drafts else None,
                })
        
        return sorted(novels, key=lambda x: x.get("last_draft", {}).get("updated_at", "") or "", reverse=True)
    
    def delete_novel(self, title: str) -> bool:
        """删除整本小说（包括成品和半成品）"""
        novel_dir = self._get_novel_dir(title)
        
        if not novel_dir.exists():
            return False
        
        import shutil
        shutil.rmtree(novel_dir)
        return True
    
    # ========== 序列化方法 ==========
    
    def _serialize_snapshot(self, snapshot: NovelSnapshot) -> dict:
        """序列化快照"""
        return {
            "id": snapshot.id,
            "title": snapshot.title,
            "created_at": snapshot.created_at,
            "updated_at": snapshot.updated_at,
            "user_prompt": snapshot.user_prompt,
            "user_guidance": snapshot.user_guidance,
            "progress": {
                "current_phase": snapshot.progress.current_phase.value,
                "current_chapter": snapshot.progress.current_chapter,
                "total_chapters": snapshot.progress.total_chapters,
                "completed_chapters": snapshot.progress.completed_chapters,
                "architecture_done": snapshot.progress.architecture_done,
                "characters_done": snapshot.progress.characters_done,
                "world_done": snapshot.progress.world_done,
                "plot_done": snapshot.progress.plot_done,
                "blueprint_done": snapshot.progress.blueprint_done,
                "last_error": snapshot.progress.last_error,
                "retry_count": snapshot.progress.retry_count,
            },
            "chapters": {
                str(k): {
                    "chapter_num": v.chapter_num,
                    "title": v.title,
                    "is_generated": v.is_generated,
                    "is_polished": v.is_polished,
                    "is_audited": v.is_audited,
                    "content": v.content,
                    "word_count": v.word_count,
                    "created_at": v.created_at,
                    "updated_at": v.updated_at,
                }
                for k, v in snapshot.chapters.items()
            },
            "agent_snapshot": {
                "current_agent": snapshot.agent_snapshot.current_agent,
                "last_prompt": snapshot.agent_snapshot.last_prompt,
                "last_response": snapshot.agent_snapshot.last_response,
                "context_summary": snapshot.agent_snapshot.context_summary,
                "iteration_count": snapshot.agent_snapshot.iteration_count,
                "extra": snapshot.agent_snapshot.extra,
            },
            "global_summary": snapshot.global_summary,
            "graph_data": snapshot.graph_data,
            "timeline_data": snapshot.timeline_data,
            "world_map_data": snapshot.world_map_data,
            "characters_data": snapshot.characters_data,
        }
    
    def _deserialize_snapshot(self, data: dict) -> NovelSnapshot:
        """反序列化快照"""
        progress_data = data.get("progress", {})
        progress = GenerationProgress(
            current_phase=GenerationPhase(progress_data.get("current_phase", "not_started")),
            current_chapter=progress_data.get("current_chapter", 0),
            total_chapters=progress_data.get("total_chapters", 0),
            completed_chapters=progress_data.get("completed_chapters", []),
            architecture_done=progress_data.get("architecture_done", False),
            characters_done=progress_data.get("characters_done", False),
            world_done=progress_data.get("world_done", False),
            plot_done=progress_data.get("plot_done", False),
            blueprint_done=progress_data.get("blueprint_done", False),
            last_error=progress_data.get("last_error", ""),
            retry_count=progress_data.get("retry_count", 0),
        )
        
        chapters = {}
        for k, v in data.get("chapters", {}).items():
            chapters[int(k)] = ChapterStatus(
                chapter_num=v.get("chapter_num", int(k)),
                title=v.get("title", ""),
                is_generated=v.get("is_generated", False),
                is_polished=v.get("is_polished", False),
                is_audited=v.get("is_audited", False),
                content=v.get("content", ""),
                word_count=v.get("word_count", 0),
                created_at=v.get("created_at", ""),
                updated_at=v.get("updated_at", ""),
            )
        
        agent_data = data.get("agent_snapshot", {})
        agent_snapshot = AgentSnapshot(
            current_agent=agent_data.get("current_agent", ""),
            last_prompt=agent_data.get("last_prompt", ""),
            last_response=agent_data.get("last_response", ""),
            context_summary=agent_data.get("context_summary", ""),
            iteration_count=agent_data.get("iteration_count", 0),
            extra=agent_data.get("extra", {}),
        )
        
        return NovelSnapshot(
            id=data.get("id", ""),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            user_prompt=data.get("user_prompt", ""),
            user_guidance=data.get("user_guidance", ""),
            progress=progress,
            chapters=chapters,
            agent_snapshot=agent_snapshot,
            global_summary=data.get("global_summary", ""),
            graph_data=data.get("graph_data", {}),
            timeline_data=data.get("timeline_data", {}),
            world_map_data=data.get("world_map_data", {}),
            characters_data=data.get("characters_data", {}),
        )
    
    # ========== 快捷方法 ==========
    
    def update_progress(self, snapshot: NovelSnapshot, phase: GenerationPhase | None = None, 
                        chapter: int | None = None, error: str | None = None) -> None:
        """更新进度"""
        snapshot.updated_at = datetime.now().isoformat()
        
        if phase:
            snapshot.progress.current_phase = phase
            if phase == GenerationPhase.ARCHITECTURE:
                snapshot.progress.architecture_done = True
            elif phase == GenerationPhase.CHARACTERS:
                snapshot.progress.characters_done = True
            elif phase == GenerationPhase.WORLD:
                snapshot.progress.world_done = True
            elif phase == GenerationPhase.PLOT:
                snapshot.progress.plot_done = True
            elif phase == GenerationPhase.BLUEPRINT:
                snapshot.progress.blueprint_done = True
        
        if chapter is not None:
            snapshot.progress.current_chapter = chapter
        
        if error:
            snapshot.progress.last_error = error
            snapshot.progress.retry_count += 1
    
    def complete_chapter(self, snapshot: NovelSnapshot, chapter_num: int, 
                        content: str, title: str = "") -> None:
        """完成章节"""
        chapter = ChapterStatus(
            chapter_num=chapter_num,
            title=title or f"第{chapter_num}章",
            content=content,
            word_count=len(content),
            is_generated=True,
            updated_at=datetime.now().isoformat(),
        )
        snapshot.chapters[chapter_num] = chapter
        
        if chapter_num not in snapshot.progress.completed_chapters:
            snapshot.progress.completed_chapters.append(chapter_num)
        
        snapshot.updated_at = datetime.now().isoformat()
        
        # 保存成品（传入章节标题）
        self.save_chapter(snapshot.title, chapter_num, content, chapter_title=title)
        
        # 保存半成品
        self.save_draft(snapshot)