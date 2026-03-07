"""
Novel Canvas Pro - FastAPI 后端服务
提供前端静态文件服务和 API 接口
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn

# 创建 FastAPI 应用实例
app = FastAPI(
    title="Novel Canvas Pro API",
    description="小说创作画布后端服务",
    version="1.0.0"
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
        "description": "AI 小说创作画布"
    }


# ===== 静态文件服务 =====

# 挂载 dist 目录为静态文件
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
    # 优先尝试查找静态文件
    file_path = DIST_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    
    # 否则返回 index.html（支持前端路由）
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    
    raise HTTPException(status_code=404, detail="页面未找到")


# ===== 启动入口 =====

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
