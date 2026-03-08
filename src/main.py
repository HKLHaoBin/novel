"""
Novel Canvas Pro - FastAPI 后端服务
提供前端静态文件服务和实时 Agent 数据接口。
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.core import NovelCoordinator, NovelStateManager
from src.core.live import LiveStateStore

# 创建 FastAPI 应用实例
app = FastAPI(
    title="Novel Canvas Pro API",
    description="小说创作画布后端服务",
    version="1.0.0",
)

# 配置 CORS（允许跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取项目路径
BASE_DIR = Path(__file__).parent.parent
DIST_DIR = BASE_DIR / "web" / "dist"
SAVE_DIR = Path(os.environ.get("NOVEL_SAVE_DIR", str(BASE_DIR / "novels")))
STATE_MANAGER = NovelStateManager(str(SAVE_DIR))
COORDINATOR = NovelCoordinator(str(SAVE_DIR))


def _get_live_store(title: str) -> LiveStateStore:
    return LiveStateStore(str(SAVE_DIR), title)


def _ensure_live_state(title: str) -> dict:
    novel_ctx = COORDINATOR.load_novel(title)
    if not novel_ctx:
        raise HTTPException(status_code=404, detail=f"未找到小说: {title}")

    live_store = _get_live_store(title)
    state = live_store.read_state()
    if not state.get("overview", {}).get("user_prompt"):
        live_store.publish_snapshot(novel_ctx)
        state = live_store.read_state()

    return state


# ===== API 路由 =====


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "服务运行正常"}


@app.get("/api/info")
async def get_info():
    """获取应用信息"""
    return {
        "name": "Novel Canvas Pro",
        "version": "1.0.0",
        "description": "AI 小说创作画布",
        "save_dir": str(SAVE_DIR),
    }


@app.get("/api/novels")
async def list_novels():
    """列出所有小说。"""
    return {"items": STATE_MANAGER.list_novels()}


@app.get("/api/novels/{title}")
async def get_novel(title: str):
    """获取小说详情。"""
    novel_ctx = COORDINATOR.load_novel(title)
    if not novel_ctx:
        raise HTTPException(status_code=404, detail=f"未找到小说: {title}")

    live_state = _ensure_live_state(title)
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
    """获取当前小说的实时状态。"""
    return _ensure_live_state(title)


@app.get("/api/novels/{title}/events/stream")
async def stream_novel_events(title: str):
    """通过 SSE 推送小说实时状态。"""
    live_state = _ensure_live_state(title)
    live_store = _get_live_store(title)
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


# ===== 静态文件服务 =====

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")
else:
    print(f"警告: 静态文件目录不存在: {DIST_DIR}")


@app.get("/")
async def serve_root():
    """提供前端主页"""
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="前端文件未找到，请先构建前端")


@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    """处理前端路由（SPA 支持）"""
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
