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
                    "progress": "",
                    "current_task": "",
                    "updated_at": "",
                    "started_at": "",
                    "finished_at": "",
                    "iteration_count": 0,
                    "last_tool": {},
                    "last_tool_result": {},
                    "recent_events": [],
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
                "progress": "Agent 已启动",
                "current_task": "准备执行",
                "updated_at": _now(),
                "started_at": _now(),
                "iteration_count": agent.get("iteration_count", 0) + 1,
                "last_tool": {},
                "last_tool_result": {},
                "recent_events": [],
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

    def _push_agent_event(
        self,
        agent: dict[str, Any],
        *,
        event_type: str,
        message: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        recent_events = list(agent.get("recent_events") or [])
        recent_events.append(
            {
                "type": event_type,
                "message": message,
                "timestamp": _now(),
                "meta": meta or {},
            }
        )
        agent["recent_events"] = recent_events[-20:]

    def publish_agent_progress(
        self,
        *,
        agent_name: str,
        message: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        state = self.read_state()
        agent = state["agents"].setdefault(agent_name, {"name": agent_name})
        agent.update(
            {
                "name": agent_name,
                "status": "running",
                "progress": message,
                "current_task": message,
                "updated_at": _now(),
                "meta": {**agent.get("meta", {}), **(meta or {})},
            }
        )
        self._push_agent_event(
            agent,
            event_type="agent_progress",
            message=message,
            meta=meta,
        )
        self._write_state(state)
        self._append_event(
            "agent_progress",
            {
                "agent": agent_name,
                "message": message,
                "meta": meta or {},
            },
        )
        logger.info("[LIVE][%s] agent_progress name=%s message=%s", self.title, agent_name, message)

    def publish_tool_call(
        self,
        *,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        state = self.read_state()
        agent = state["agents"].setdefault(agent_name, {"name": agent_name})
        payload = {
            "name": tool_name,
            "arguments": arguments or {},
            "timestamp": _now(),
        }
        agent.update(
            {
                "name": agent_name,
                "status": "running",
                "current_task": f"调用工具 {tool_name}",
                "progress": f"调用工具 {tool_name}",
                "last_tool": payload,
                "updated_at": _now(),
            }
        )
        self._push_agent_event(
            agent,
            event_type="tool_called",
            message=f"调用工具 {tool_name}",
            meta=payload,
        )
        self._write_state(state)
        self._append_event(
            "tool_called",
            {
                "agent": agent_name,
                "tool": tool_name,
                "arguments": arguments or {},
            },
        )
        logger.info("[LIVE][%s] tool_called agent=%s tool=%s", self.title, agent_name, tool_name)

    def publish_tool_result(
        self,
        *,
        agent_name: str,
        tool_name: str,
        success: bool,
        content: str,
        issues: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        state = self.read_state()
        agent = state["agents"].setdefault(agent_name, {"name": agent_name})
        tool_data = data or {}
        segment_content = str(tool_data.get("segment_content") or "")
        total_so_far = tool_data.get("total_so_far")
        is_end = bool(tool_data.get("is_end", True))
        chapter_title = tool_data.get("chapter_title") or agent.get("meta", {}).get("chapter_title")
        payload = {
            "name": tool_name,
            "success": success,
            "content": content[:2000],
            "issues": issues or [],
            "data": tool_data,
            "timestamp": _now(),
        }
        next_output = agent.get("output", "")
        next_meta = {**agent.get("meta", {})}
        next_current_task = f"工具完成 {tool_name}"
        next_progress = f"工具完成 {tool_name}"

        if tool_name == "complete" and success:
            if segment_content:
                next_output = f"{next_output}{segment_content}"
            if chapter_title:
                next_meta["chapter_title"] = chapter_title
            if is_end:
                next_current_task = "章节分段提交完成"
                next_progress = "章节分段提交完成"
            else:
                total_text = str(total_so_far) if total_so_far is not None else str(len(next_output))
                next_current_task = f"已提交分段，累计 {total_text} 字"
                next_progress = next_current_task

        agent.update(
            {
                "name": agent_name,
                "status": "running",
                "current_task": next_current_task,
                "progress": next_progress,
                "last_tool_result": payload,
                "output": next_output,
                "updated_at": _now(),
                "meta": next_meta,
            }
        )
        self._push_agent_event(
            agent,
            event_type="tool_result",
            message=(
                f"分段提交完成，累计 {total_so_far if total_so_far is not None else len(next_output)} 字"
                if tool_name == "complete" and success and not is_end
                else f"工具完成 {tool_name}"
            ),
            meta=payload,
        )
        self._write_state(state)
        self._append_event(
            "tool_result",
            {
                "agent": agent_name,
                "tool": tool_name,
                "success": success,
                "content": content[:2000],
                "issues": issues or [],
                "data": tool_data,
            },
        )
        logger.info(
            "[LIVE][%s] tool_result agent=%s tool=%s success=%s",
            self.title,
            agent_name,
            tool_name,
            success,
        )

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
                "progress": "执行完成" if status == "completed" else error[:200],
                "current_task": "执行完成" if status == "completed" else "执行失败",
                "updated_at": _now(),
                "finished_at": _now(),
                "meta": meta or agent.get("meta", {}),
            }
        )
        self._push_agent_event(
            agent,
            event_type="agent_finished",
            message="执行完成" if status == "completed" else f"执行失败: {error[:120]}",
            meta=meta,
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
        if error:
            logger.info(
                "[LIVE][%s] agent_finished name=%s status=%s error=%s",
                self.title,
                agent_name,
                status,
                error[:200],
            )
        else:
            logger.info(
                "[LIVE][%s] agent_finished name=%s status=%s",
                self.title,
                agent_name,
                status,
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
                point_label = getattr(point, "label", "") or getattr(point, "name", "") or point.id
                point_desc = ""
                if hasattr(point, "attrs") and isinstance(point.attrs, dict):
                    point_desc = (
                        point.attrs.get("summary")
                        or point.attrs.get("description")
                        or point.attrs.get("event")
                        or ""
                    )
                timeline_lines.append(
                    f"{point_label}: {point_desc}".rstrip(": ")
                )

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
