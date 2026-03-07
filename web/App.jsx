import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  BookOpen, Globe, GitBranch, Users, Clock, MapPin, 
  MessageSquare, Zap, Activity, ChevronRight, 
  Settings, Maximize2, Minimize2, MousePointer2, Loader2, GripHorizontal, Search
} from 'lucide-react';

// --- 初始布局数据 ---
const INITIAL_LAYOUT = {
  outline: { x: 100, y: 100, w: 450, h: 350, color: 'blue', title: '设计大纲', icon: BookOpen },
  characters: { x: 600, y: 100, w: 500, h: 450, color: 'emerald', title: '核心角色', icon: Users },
  guidance: { x: 1150, y: 100, w: 350, h: 250, color: 'amber', title: '用户指导', icon: MessageSquare },
  world: { x: 100, y: 500, w: 450, h: 350, color: 'cyan', title: '世界观设定', icon: Globe },
  plots: { x: 600, y: 600, w: 500, h: 250, color: 'indigo', title: '情节线索', icon: GitBranch },
  map: { x: 1150, y: 400, w: 350, h: 250, color: 'rose', title: '地图结构', icon: MapPin },
  timeline: { x: 1150, y: 700, w: 350, h: 250, color: 'purple', title: '时间轴', icon: Clock },
};

const INITIAL_CONTENT = {
  outline: "在一片被永恒风暴包围的悬浮群岛上，少年云歌意外发现了一艘能够穿梭风暴的古船...",
  world: "【悬浮界】规则：浮力取决于核心矿石的纯度；风暴每12小时循环一次。势力：风暴议会、流浪者联盟。",
  plots: "主线：云歌启动古船引来追杀。支线：苏苏的真实身份是教团圣女。",
  characters: "[云歌] - 主角\n特质: 勇敢、修理工\n状态: 活跃\n\n[苏苏] - 圣女\n特质: 沉稳、暗影操纵\n状态: 潜伏",
  timeline: "序章：古船重启 -> 第一章：遭遇巡逻队 -> 第二章：迫降苍穹岛",
  map: "苍穹岛 (主城)、遗落码头 (遗迹)、风暴眼 (禁区)",
  guidance: "文风硬核奇幻，侧重心理描写，禁止过度口语化。"
};

export default function App() {
  const [content, setContent] = useState(INITIAL_CONTENT);
  const [layout, setLayout] = useState(INITIAL_LAYOUT);
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [maximizedKey, setMaximizedKey] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [aiStatus, setAiStatus] = useState({ activeSections: ['characters', 'outline'] });
  
  const dragRef = useRef(null);
  const canvasRef = useRef(null);

  // --- 画布缩放逻辑 (滚轮) ---
  const handleWheel = (e) => {
    if (maximizedKey) return;
    e.preventDefault();
    
    const zoomSpeed = 0.001;
    const minZoom = 0.2;
    const maxZoom = 3;
    
    const delta = -e.deltaY;
    const newZoom = Math.min(Math.max(zoom + delta * zoomSpeed, minZoom), maxZoom);
    
    if (newZoom !== zoom) {
      // 计算鼠标相对于画布中心的位置，以实现以鼠标为中心缩放
      const rect = canvasRef.current.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // 核心公式：调整偏移量以保持鼠标指向的物理位置不变
      const dx = (mouseX - canvasOffset.x) / zoom;
      const dy = (mouseY - canvasOffset.y) / zoom;
      
      setCanvasOffset({
        x: mouseX - dx * newZoom,
        y: mouseY - dy * newZoom
      });
      setZoom(newZoom);
    }
  };

  // --- 画布平移逻辑 (左键背景或中键任意处) ---
  const handleCanvasMouseDown = (e) => {
    // button 1 是滚轮中键
    const isMiddleClick = e.button === 1;
    const isBackgroundClick = e.target === e.currentTarget;

    if (isMiddleClick || isBackgroundClick) {
      if (isMiddleClick) e.preventDefault(); // 禁止中键自动滚动图标
      setIsPanning(true);
      dragRef.current = { x: e.clientX - canvasOffset.x, y: e.clientY - canvasOffset.y };
    }
  };

  // --- 容器拖动逻辑 ---
  const startDraggingCard = (key, e) => {
    if (maximizedKey) return;
    if (e.button !== 0) return; // 仅左键可拖动容器内容，防止中键冲突
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    const initialPos = { ...layout[key] };

    const onMouseMove = (moveEvent) => {
      setLayout(prev => ({
        ...prev,
        [key]: {
          ...prev[key],
          // 注意：位移量需要除以 zoom，否则缩放后移动速度会不匹配
          x: initialPos.x + (moveEvent.clientX - startX) / zoom,
          y: initialPos.y + (moveEvent.clientY - startY) / zoom
        }
      }));
    };

    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  // --- 容器缩放逻辑 ---
  const startResizingCard = (key, e) => {
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    const initialSize = { w: layout[key].w, h: layout[key].h };

    const onMouseMove = (moveEvent) => {
      setLayout(prev => ({
        ...prev,
        [key]: {
          ...prev[key],
          w: Math.max(200, initialSize.w + (moveEvent.clientX - startX) / zoom),
          h: Math.max(150, initialSize.h + (moveEvent.clientY - startY) / zoom)
        }
      }));
    };

    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  const handleMouseMove = (e) => {
    if (isPanning) {
      setCanvasOffset({
        x: e.clientX - dragRef.current.x,
        y: e.clientY - dragRef.current.y
      });
    }
  };

  const handleMouseUp = () => setIsPanning(false);

  const toggleMaximize = (key) => setMaximizedKey(maximizedKey === key ? null : key);

  const handleContentUpdate = (key, val) => {
    setIsSyncing(true);
    setContent(prev => ({ ...prev, [key]: val }));
    setTimeout(() => setIsSyncing(false), 600);
  };

  // 禁止中键弹出默认的滚动图标
  useEffect(() => {
    const preventMiddleScroll = (e) => {
      if (e.button === 1) e.preventDefault();
    };
    document.addEventListener('mousedown', preventMiddleScroll);
    return () => document.removeEventListener('mousedown', preventMiddleScroll);
  }, []);

  return (
    <div className="flex flex-col h-screen w-full bg-slate-950 text-slate-200 overflow-hidden select-none font-sans">
      {/* --- Header --- */}
      <header className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/80 backdrop-blur-xl z-[100]">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Zap size={20} className="text-blue-500 fill-blue-500" />
            <h1 className="font-black text-lg tracking-tighter">NOVEL_CANVAS_PRO</h1>
          </div>
          <div className="flex items-center gap-3 px-3 py-1 bg-slate-950 rounded-full border border-slate-800">
             <div className={`w-2 h-2 rounded-full ${isSyncing ? 'bg-blue-500 animate-pulse' : 'bg-emerald-500'}`} />
             <span className="text-[10px] font-bold text-slate-500 uppercase">{isSyncing ? '同步中' : '云端就绪'}</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-1 rounded-md">
            <Search size={14} className="text-slate-500" />
            <span className="text-xs font-mono text-slate-400">{Math.round(zoom * 100)}%</span>
          </div>
          <div className="text-[10px] text-slate-600 font-mono tracking-tighter">
            X: {Math.round(canvasOffset.x)} Y: {Math.round(canvasOffset.y)}
          </div>
          <button className="p-2 hover:bg-slate-800 rounded-lg transition-colors"><Settings size={18} /></button>
        </div>
      </header>

      {/* --- Infinite Canvas --- */}
      <main 
        ref={canvasRef}
        className={`flex-1 relative overflow-hidden bg-slate-950 ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        {/* Dot Pattern Background */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-20"
          style={{ 
            backgroundImage: `radial-gradient(#475569 1px, transparent 1px)`,
            backgroundSize: `${32 * zoom}px ${32 * zoom}px`,
            backgroundPosition: `${canvasOffset.x}px ${canvasOffset.y}px`
          }}
        />

        {/* The World Layer */}
        <div 
          className="absolute origin-top-left transition-transform duration-0"
          style={{ 
            transform: `translate(${canvasOffset.x}px, ${canvasOffset.y}px) scale(${zoom})` 
          }}
        >
          {Object.entries(layout).map(([key, config]) => {
            const isMaximized = maximizedKey === key;
            const Icon = config.icon;
            const isActive = aiStatus.activeSections.includes(key);

            if (isMaximized) return null;

            return (
              <div 
                key={key}
                className={`absolute bg-slate-900 rounded-2xl border-2 flex flex-col transition-shadow shadow-2xl ${
                  isActive ? `border-${config.color}-500 shadow-${config.color}-500/20` : 'border-slate-800 shadow-black'
                }`}
                style={{ 
                  left: config.x, top: config.y, width: config.w, height: config.h,
                  zIndex: isActive ? 50 : 10
                }}
              >
                {/* Drag Header */}
                <div 
                  className="p-3 border-b border-slate-800 flex items-center justify-between cursor-move bg-slate-900/50 rounded-t-2xl"
                  onMouseDown={(e) => startDraggingCard(key, e)}
                >
                  <div className="flex items-center gap-2">
                    <Icon size={16} className={`text-${config.color}-500`} />
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{config.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isActive && <div className="flex items-center gap-1 mr-2">
                       <span className={`w-1.5 h-1.5 rounded-full bg-${config.color}-500 animate-ping`} />
                       <span className={`text-[9px] font-bold text-${config.color}-500`}>AI</span>
                    </div>}
                    <button 
                      onClick={() => toggleMaximize(key)}
                      className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-white"
                    >
                      <Maximize2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Content Area */}
                <div className="flex-1 overflow-hidden relative">
                  <textarea
                    className="w-full h-full bg-transparent p-4 text-sm text-slate-300 outline-none resize-none font-sans leading-relaxed scrollbar-hide focus:text-white transition-colors"
                    value={content[key]}
                    onChange={(e) => setContent(prev => ({ ...prev, [key]: e.target.value }))}
                    onBlur={(e) => handleContentUpdate(key, e.target.value)}
                    placeholder="开始创作..."
                  />
                </div>

                {/* Resize Handle */}
                <div 
                  className="absolute bottom-1 right-1 cursor-nwse-resize p-1 text-slate-700 hover:text-slate-400"
                  onMouseDown={(e) => startResizingCard(key, e)}
                >
                  <GripHorizontal size={14} className="rotate-45" />
                </div>
              </div>
            );
          })}
        </div>

        {/* --- Fullscreen Focused Mode Layer --- */}
        {maximizedKey && (
          <div className="absolute inset-0 z-[200] bg-slate-950 flex items-center justify-center p-12 animate-in fade-in zoom-in duration-300">
             <div className={`w-full max-w-5xl h-full bg-slate-900 rounded-3xl border-2 border-${layout[maximizedKey].color}-500/50 shadow-2xl flex flex-col shadow-${layout[maximizedKey].color}-500/20`}>
                <div className="p-6 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl bg-${layout[maximizedKey].color}-500/10`}>
                      {React.createElement(layout[maximizedKey].icon, { size: 24, className: `text-${layout[maximizedKey].color}-500` })}
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white tracking-tight">{layout[maximizedKey].title}</h2>
                      <p className="text-slate-500 text-xs uppercase tracking-widest font-bold">沉浸式编辑模式</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => toggleMaximize(maximizedKey)}
                    className="p-3 bg-slate-800 hover:bg-slate-700 rounded-2xl text-white transition-all hover:scale-110"
                  >
                    <Minimize2 size={24} />
                  </button>
                </div>
                <textarea
                  autoFocus
                  className="flex-1 bg-transparent p-12 text-xl text-slate-200 outline-none resize-none font-serif leading-loose"
                  value={content[maximizedKey]}
                  onChange={(e) => setContent(prev => ({ ...prev, [maximizedKey]: e.target.value }))}
                  onBlur={(e) => handleContentUpdate(maximizedKey, e.target.value)}
                />
             </div>
          </div>
        )}

        {/* --- AI HUD --- */}
        <div className="absolute bottom-6 right-6 w-80 bg-slate-900/90 backdrop-blur-2xl border border-blue-500/20 rounded-2xl shadow-2xl z-[150]">
          <div className="p-3 border-b border-slate-800 flex justify-between items-center px-4">
             <span className="text-blue-400 font-bold text-[10px] tracking-widest">WRITER_AGENT_LIVE</span>
             <Activity size={12} className="text-blue-500 animate-pulse" />
          </div>
          <div className="p-4 bg-slate-950/50">
             <div className="h-16 text-[11px] text-slate-500 italic overflow-hidden">
                "云歌在风暴的中心找到了遗失的罗盘..."
             </div>
          </div>
        </div>

        {/* Canvas Guide */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 px-4 py-2 bg-slate-900/80 border border-slate-800 rounded-full text-[9px] text-slate-400 font-bold uppercase tracking-[0.2em] backdrop-blur pointer-events-none flex items-center gap-4">
          <span className="flex items-center gap-1"><MousePointer2 size={10} /> 左键背景/滚轮中键拖拽</span>
          <div className="w-1 h-1 rounded-full bg-slate-700" />
          <span className="flex items-center gap-1 font-mono">SCROLL 滚轮缩放</span>
        </div>
      </main>
    </div>
  );
}