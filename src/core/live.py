"""Web 实时运行态存储。"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("novel.live")


def _now() -> str:
    return datetime.now().isoformat()


def _safe_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


class LiveStateStore:
    """将 Agent 运行态持续写入磁盘，供 Web 实时读取。"""

    AGENT_NAMES = ["Designer", "Planner", "Writer", "Auditor", "Polisher"]

    def __init__(self, save_dir: str, title: str):
        self.save_dir = Path(save_dir)
        self.title = title
        self.live_dir = self.save_dir / title / "live"
        self.state_path = self.live_dir / "current.json"
        self.events_path = self.live_dir / "events.jsonl"

        if not self.state_path.exists():
            _safe_write_json(self.state_path, self._build_default_state())

    def _build_default_state(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "updated_at": _now(),
            "status": {
                "stage": "idle",
                "message": "等待运行",
                "running": False,
            },
            "overview": {
                "user_prompt": "",
                "user_guidance": "",
                "global_summary": "",
                "current_phase": "",
                "current_chapter": 0,
                "total_chapters": 0,
                "completed_chapters": [],
            },
            "sections": {
                "outline": "",
                "guidance": "",
                "characters": "",
                "world": "",
                "plots": "",
                "map": "",
                "timeline": "",
            },
            "agents": {
                name: {
                    "name": name,
                    "status": "idle",
                    "context": "",
                    "prompt": "",
                    "output": "",
                    "error": "",
                    "updated_at": "",
                    "started_at": "",
                    "finished_at": "",
                    "iteration_count": 0,
                    "meta": {},
                }
                for name in self.AGENT_NAMES
            },
            "event_seq": 0,
        }

    def read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._build_default_state()
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now()
        _safe_write_json(self.state_path, state)

    def _append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        state = self.read_state()
        state["event_seq"] = state.get("event_seq", 0) + 1
        event = {
            "seq": state["event_seq"],
            "type": event_type,
            "timestamp": _now(),
            **payload,
        }
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._write_state(state)

    def publish_progress(
        self,
        stage: str,
        message: str,
        *,
        running: bool | None = None,
    ) -> None:
        state = self.read_state()
        state["status"]["stage"] = stage
        state["status"]["message"] = message
        if running is not None:
            state["status"]["running"] = running
        self._write_state(state)
        self._append_event(
            "progress",
            {
                "stage": stage,
                "message": message,
                "running": state["status"]["running"],
            },
        )
        logger.info("[LIVE][%s] progress stage=%s message=%s", self.title, stage, message)

    def publish_snapshot(self, novel_ctx: Any) -> None:
        snapshot = novel_ctx.snapshot
        state = self.read_state()
        state["overview"] = {
            "user_prompt": snapshot.user_prompt,
            "user_guidance": snapshot.user_guidance,
            "global_summary": novel_ctx.global_summary,
            "current_phase": snapshot.progress.current_phase.value,
            "current_chapter": snapshot.progress.current_chapter,
            "total_chapters": snapshot.progress.total_chapters,
            "completed_chapters": snapshot.progress.completed_chapters,
        }
        state["sections"] = self._build_sections(novel_ctx)
        self._write_state(state)

    def publish_agent_start(
        self,
        *,
        agent_name: str,
        context_summary: str,
        prompt: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        state = self.read_state()
        agent = state["agents"].setdefault(agent_name, {"name": agent_name})
        agent.update(
            {
                "name": agent_name,
                "status": "running",
                "context": context_summary,
                "prompt": prompt,
                "error": "",
                "updated_at": _now(),
                "started_at": _now(),
                "iteration_count": agent.get("iteration_count", 0) + 1,
                "meta": meta or {},
            }
        )
        self._write_state(state)
        self._append_event(
            "agent_started",
            {
                "agent": agent_name,
                "context": context_summary,
                "prompt": prompt,
                "meta": meta or {},
            },
        )
        logger.info("[LIVE][%s] agent_started name=%s meta=%s", self.title, agent_name, meta or {})

    def publish_agent_result(
        self,
        *,
        agent_name: str,
        status: str,
        output: str = "",
        error: str = "",
        meta: dict[str, Any] | None = None,
    ) -> None:
        state = self.read_state()
        agent = state["agents"].setdefault(agent_name, {"name": agent_name})
        agent.update(
            {
                "name": agent_name,
                "status": status,
                "output": output,
                "error": error,
                "updated_at": _now(),
                "finished_at": _now(),
                "meta": meta or agent.get("meta", {}),
            }
        )
        self._write_state(state)
        self._append_event(
            "agent_finished",
            {
                "agent": agent_name,
                "status": status,
                "output": output,
                "error": error,
                "meta": meta or {},
            },
        )
        logger.info(
            "[LIVE][%s] agent_finished name=%s status=%s error=%s",
            self.title,
            agent_name,
            status,
            error[:200],
        )

    def _build_sections(self, novel_ctx: Any) -> dict[str, str]:
        snapshot = novel_ctx.snapshot
        extra = snapshot.agent_snapshot.extra or {}

        characters = []
        for name, char in list(novel_ctx.characters.items())[:12]:
            role = char.attrs.get("role", "角色")
            personality = char.personality or "暂无性格描述"
            characters.append(f"[{name}] {role}\n{personality}")

        world_data = extra.get("world", {})
        world_lines = []
        if world_data:
            if world_data.get("setting"):
                world_lines.append(f"背景：{world_data['setting']}")
            if world_data.get("rules"):
                world_lines.append(f"规则：{world_data['rules']}")
            if world_data.get("factions"):
                world_lines.append(f"势力：{world_data['factions']}")

        blueprint = extra.get("blueprint", {})
        plot_lines = []
        for ch_key, item in list(blueprint.items())[:10]:
            if isinstance(item, dict):
                title = item.get("title", f"第{ch_key}章")
                summary = item.get("summary", "")
                plot_lines.append(f"第{ch_key}章 {title}\n{summary}")

        map_lines = []
        if novel_ctx.world_map and novel_ctx.world_map.locations:
            for loc in list(novel_ctx.world_map.locations.values())[:20]:
                map_lines.append(f"{loc.name} ({loc.type.value})")

        timeline_lines = []
        if novel_ctx.timeline and novel_ctx.timeline.points:
            for point in novel_ctx.timeline.get_ordered_points()[:20]:
                timeline_lines.append(f"{point.name}: {point.description}")

        seed = extra.get("seed", {})
        outline_lines = []
        if seed:
            for key in ("core", "conflict", "theme", "tone"):
                value = seed.get(key)
                if value:
                    outline_lines.append(f"{key}: {value}")

        return {
            "outline": novel_ctx.global_summary or "\n".join(outline_lines),
            "guidance": snapshot.user_guidance,
            "characters": "\n\n".join(characters),
            "world": "\n".join(world_lines),
            "plots": "\n\n".join(plot_lines),
            "map": "\n".join(map_lines),
            "timeline": "\n".join(timeline_lines),
        }


def snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    """为 API 提供可序列化快照。"""
    if hasattr(snapshot, "__dataclass_fields__"):
        return asdict(snapshot)
    return snapshot
