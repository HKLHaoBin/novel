"""
Novel Canvas Pro - FastAPI 后端服务
提供前端静态文件服务、实时 Agent 数据接口和 Web 控制台。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core import NovelCoordinator, NovelStateManager
from src.core.live import LiveStateStore
from src.generator import NovelGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


class WebSettings(BaseModel):
    title: str = ""
    prompt: str = ""
    chapters: int = 20
    words: int = 3000
    auto_audit: bool = True
    auto_polish: bool = True
    force_design: bool = False
    llm_type: str = "compatible"
    api_key: str = ""
    base_url: str = ""
    model: str = "deepseek-v3"
    save_dir: str = ""


class StartJobPayload(BaseModel):
    settings: WebSettings


class JobState:
    def __init__(self) -> None:
        self.running = False
        self.title = ""
        self.stage = "idle"
        self.message = "等待启动"
        self.started_at = ""
        self.finished_at = ""
        self.last_error = ""
        self.task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "title": self.title,
            "stage": self.stage,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_error": self.last_error,
        }


app = FastAPI(
    title="Novel Canvas Pro API",
    description="小说创作画布后端服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent
DIST_DIR = BASE_DIR / "web" / "dist"
DEFAULT_SAVE_DIR = BASE_DIR / "novels"
CONFIG_DIR = Path.home() / ".novel"
CONFIG_PATH = CONFIG_DIR / "config.json"
WEB_SETTINGS_PATH = CONFIG_DIR / "web_settings.json"

job_state = JobState()
job_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now().isoformat()


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict[str, Any]) -> None:
    _ensure_config_dir()
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _resolve_save_dir(settings: WebSettings | None = None) -> Path:
    env_dir = os.environ.get("NOVEL_SAVE_DIR")
    configured = settings.save_dir if settings and settings.save_dir else ""
    return Path(configured or env_dir or str(DEFAULT_SAVE_DIR))


def _state_manager(save_dir: Path | None = None) -> NovelStateManager:
    return NovelStateManager(str(save_dir or _resolve_save_dir()))


def _coordinator(save_dir: Path | None = None) -> NovelCoordinator:
    return NovelCoordinator(str(save_dir or _resolve_save_dir()))


def _default_settings() -> dict[str, Any]:
    cli_config = _load_json(CONFIG_PATH)
    return WebSettings(
        llm_type=cli_config.get("llm_type", "compatible"),
        api_key=os.environ.get("NOVEL_API_KEY", cli_config.get("api_key", "")),
        base_url=os.environ.get("NOVEL_BASE_URL", cli_config.get("base_url", "")),
        model=os.environ.get("NOVEL_MODEL", cli_config.get("model", "deepseek-v3")),
        save_dir=os.environ.get("NOVEL_SAVE_DIR", str(DEFAULT_SAVE_DIR)),
    ).model_dump()


def load_web_settings() -> WebSettings:
    defaults = _default_settings()
    stored = _load_json(WEB_SETTINGS_PATH)
    merged = {**defaults, **stored}
    return WebSettings(**merged)


def save_web_settings(settings: WebSettings) -> None:
    _save_json(WEB_SETTINGS_PATH, settings.model_dump())
    cli_config = _load_json(CONFIG_PATH)
    cli_config.update(
        {
            "llm_type": settings.llm_type,
            "api_key": settings.api_key,
            "base_url": settings.base_url,
            "model": settings.model,
        }
    )
    _save_json(CONFIG_PATH, cli_config)


def _get_live_store(title: str, save_dir: Path | None = None) -> LiveStateStore:
    return LiveStateStore(str(save_dir or _resolve_save_dir()), title)


def _ensure_live_state(title: str, save_dir: Path | None = None) -> dict[str, Any]:
    current_save_dir = save_dir or _resolve_save_dir()
    novel_ctx = _coordinator(current_save_dir).load_novel(title)
    live_store = _get_live_store(title, current_save_dir)
    if not novel_ctx:
        state = live_store.read_state()
        if state.get("title") == title:
            return state
        raise HTTPException(status_code=404, detail=f"未找到小说: {title}")

    state = live_store.read_state()
    if not state.get("overview", {}).get("user_prompt"):
        live_store.publish_snapshot(novel_ctx)
        state = live_store.read_state()

    return state


def _make_llm_config(settings: WebSettings) -> dict[str, Any]:
    return {
        "type": settings.llm_type,
        "api_key": settings.api_key,
        "base_url": settings.base_url,
        "model": settings.model,
    }


async def _run_generation(settings: WebSettings) -> None:
    save_dir = _resolve_save_dir(settings)
    generator = NovelGenerator(
        llm_config=_make_llm_config(settings),
        save_dir=str(save_dir),
    )

    def on_progress(stage: str, message: str) -> None:
        job_state.stage = stage
        job_state.message = message

    generator.on_progress(on_progress)
    job_state.running = True
    job_state.title = settings.title
    job_state.stage = "starting"
    job_state.message = "准备启动生成任务"
    job_state.started_at = _now()
    job_state.finished_at = ""
    job_state.last_error = ""

    try:
        if not settings.api_key:
            raise RuntimeError("缺少 API Key，请先在设置中填写")
        if not settings.title.strip():
            raise RuntimeError("缺少小说标题")
        if not settings.prompt.strip():
            raise RuntimeError("缺少小说需求描述")

        coordinator = _coordinator(save_dir)
        novel_ctx = coordinator.load_novel(settings.title)
        if not novel_ctx:
            await generator.create_novel(
                title=settings.title,
                user_prompt=settings.prompt,
                total_chapters=settings.chapters,
                word_count_per_chapter=settings.words,
            )
        else:
            await generator.load_novel(settings.title)
            if generator.novel_ctx:
                generator.novel_ctx.snapshot.user_prompt = settings.prompt
                generator.novel_ctx.snapshot.progress.total_chapters = settings.chapters
                generator.novel_ctx.snapshot.user_guidance = (
                    f"共{settings.chapters}章，每章约{settings.words}字"
                )

        if not generator.novel_ctx:
            raise RuntimeError("小说上下文初始化失败")

        generator.save_checkpoint()

        needs_design = settings.force_design or not generator.novel_ctx.global_summary
        if needs_design:
            await generator.design()

        chapter_files = generator.coordinator.state_manager.list_chapters(settings.title)
        start_chapter = max((item["chapter_num"] for item in chapter_files), default=0) + 1
        total = generator.novel_ctx.snapshot.progress.total_chapters

        if start_chapter <= total:
            await generator.write_all_chapters(
                start=start_chapter,
                auto_audit=settings.auto_audit,
                auto_polish=settings.auto_polish,
            )

        job_state.stage = "completed"
        job_state.message = "生成任务完成"
    except asyncio.CancelledError:
        job_state.stage = "cancelled"
        job_state.message = "任务已取消"
        raise
    except Exception as exc:
        job_state.stage = "error"
        job_state.message = str(exc)
        job_state.last_error = str(exc)
        live_store = _get_live_store(settings.title, save_dir)
        live_store.publish_progress("error", str(exc), running=False)
    finally:
        job_state.running = False
        job_state.finished_at = _now()
        await generator.close()


def _start_background_job(settings: WebSettings) -> None:
    async def runner() -> None:
        async with job_lock:
            await _run_generation(settings)

    job_state.task = asyncio.create_task(runner())


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "服务运行正常"}


@app.get("/api/info")
async def get_info():
    return {
        "name": "Novel Canvas Pro",
        "version": "1.0.0",
        "description": "AI 小说创作画布",
        "save_dir": str(_resolve_save_dir(load_web_settings())),
    }


@app.get("/api/settings")
async def get_settings():
    return {"settings": load_web_settings().model_dump(), "job": job_state.to_dict()}


@app.put("/api/settings")
async def update_settings(settings: WebSettings):
    save_web_settings(settings)
    return {"settings": settings.model_dump(), "job": job_state.to_dict()}


@app.get("/api/job")
async def get_job():
    return job_state.to_dict()


@app.post("/api/job/start")
async def start_job(payload: StartJobPayload):
    settings = payload.settings
    save_web_settings(settings)

    if job_state.running:
        raise HTTPException(status_code=409, detail="已有生成任务正在运行")

    _start_background_job(settings)
    return {
        "ok": True,
        "message": "生成任务已启动",
        "job": job_state.to_dict(),
    }


@app.get("/api/novels")
async def list_novels():
    settings = load_web_settings()
    items = _state_manager(_resolve_save_dir(settings)).list_novels()
    return {"items": items, "job": job_state.to_dict()}


@app.get("/api/novels/{title}")
async def get_novel(title: str):
    settings = load_web_settings()
    save_dir = _resolve_save_dir(settings)
    novel_ctx = _coordinator(save_dir).load_novel(title)
    if not novel_ctx:
        raise HTTPException(status_code=404, detail=f"未找到小说: {title}")

    live_state = _ensure_live_state(title, save_dir)
    return {
        "title": title,
        "snapshot": {
            "user_prompt": novel_ctx.snapshot.user_prompt,
            "user_guidance": novel_ctx.snapshot.user_guidance,
            "progress": {
                "current_phase": novel_ctx.snapshot.progress.current_phase.value,
                "current_chapter": novel_ctx.snapshot.progress.current_chapter,
                "total_chapters": novel_ctx.snapshot.progress.total_chapters,
                "completed_chapters": novel_ctx.snapshot.progress.completed_chapters,
            },
            "global_summary": novel_ctx.global_summary,
        },
        "live": live_state,
    }


@app.get("/api/novels/{title}/live")
async def get_novel_live(title: str):
    settings = load_web_settings()
    return _ensure_live_state(title, _resolve_save_dir(settings))


@app.get("/api/novels/{title}/events/stream")
async def stream_novel_events(title: str):
    settings = load_web_settings()
    save_dir = _resolve_save_dir(settings)
    live_state = _ensure_live_state(title, save_dir)
    live_store = _get_live_store(title, save_dir)
    state_path = live_store.state_path
    initial_seq = live_state.get("event_seq", 0)

    async def event_generator():
        last_seq = initial_seq
        yield f"data: {json.dumps(live_state, ensure_ascii=False)}\n\n"

        while True:
            await asyncio.sleep(1)
            if not state_path.exists():
                continue

            current = live_store.read_state()
            current_seq = current.get("event_seq", 0)
            if current_seq != last_seq:
                last_seq = current_seq
                yield f"data: {json.dumps(current, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")
else:
    print(f"警告: 静态文件目录不存在: {DIST_DIR}")


@app.get("/")
async def serve_root():
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="前端文件未找到，请先构建前端")


@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    file_path = DIST_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))

    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))

    raise HTTPException(status_code=404, detail="页面未找到")


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
