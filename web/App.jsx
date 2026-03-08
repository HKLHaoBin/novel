import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  BookOpen,
  Clock,
  FileText,
  Globe,
  GitBranch,
  GripHorizontal,
  Loader2,
  MapPin,
  Maximize2,
  MessageSquare,
  Minimize2,
  MousePointer2,
  Play,
  Save,
  Search,
  Settings,
  Users,
  X,
  Zap,
} from 'lucide-react';

const INITIAL_LAYOUT = {
  outline: { x: 100, y: 100, w: 450, h: 350, color: 'blue', title: '设计大纲', icon: BookOpen },
  characters: { x: 600, y: 100, w: 500, h: 450, color: 'emerald', title: '核心角色', icon: Users },
  guidance: { x: 1150, y: 100, w: 350, h: 250, color: 'amber', title: '用户指导', icon: MessageSquare },
  world: { x: 100, y: 500, w: 450, h: 350, color: 'cyan', title: '世界观设定', icon: Globe },
  plots: { x: 600, y: 600, w: 500, h: 250, color: 'indigo', title: '情节线索', icon: GitBranch },
  map: { x: 1150, y: 400, w: 350, h: 250, color: 'rose', title: '地图结构', icon: MapPin },
  timeline: { x: 1150, y: 700, w: 350, h: 250, color: 'purple', title: '时间轴', icon: Clock },
  agent_designer: { x: 1550, y: 80, w: 380, h: 300, color: 'blue', title: 'Designer', icon: Activity },
  agent_planner: { x: 1960, y: 80, w: 380, h: 300, color: 'indigo', title: 'Planner', icon: Activity },
  agent_writer: { x: 1550, y: 410, w: 380, h: 300, color: 'emerald', title: 'Writer', icon: Activity },
  agent_auditor: { x: 1960, y: 410, w: 380, h: 300, color: 'amber', title: 'Auditor', icon: Activity },
  agent_polisher: { x: 1755, y: 740, w: 380, h: 300, color: 'rose', title: 'Polisher', icon: Activity },
  chapters_panel: { x: 2165, y: 740, w: 520, h: 420, color: 'amber', title: '已生成章节', icon: FileText },
};

const INITIAL_CONTENT = {
  outline: '',
  world: '',
  plots: '',
  characters: '',
  timeline: '',
  map: '',
  guidance: '',
  agent_designer: '',
  agent_planner: '',
  agent_writer: '',
  agent_auditor: '',
  agent_polisher: '',
  chapters_panel: '',
};

const CARD_STYLES = {
  blue: {
    border: 'border-blue-500',
    shadow: 'shadow-blue-500/20',
    text: 'text-blue-500',
    dot: 'bg-blue-500',
    bg: 'bg-blue-500/10',
    ring: 'ring-blue-500/40',
  },
  emerald: {
    border: 'border-emerald-500',
    shadow: 'shadow-emerald-500/20',
    text: 'text-emerald-500',
    dot: 'bg-emerald-500',
    bg: 'bg-emerald-500/10',
    ring: 'ring-emerald-500/40',
  },
  amber: {
    border: 'border-amber-500',
    shadow: 'shadow-amber-500/20',
    text: 'text-amber-500',
    dot: 'bg-amber-500',
    bg: 'bg-amber-500/10',
    ring: 'ring-amber-500/40',
  },
  cyan: {
    border: 'border-cyan-500',
    shadow: 'shadow-cyan-500/20',
    text: 'text-cyan-500',
    dot: 'bg-cyan-500',
    bg: 'bg-cyan-500/10',
    ring: 'ring-cyan-500/40',
  },
  indigo: {
    border: 'border-indigo-500',
    shadow: 'shadow-indigo-500/20',
    text: 'text-indigo-500',
    dot: 'bg-indigo-500',
    bg: 'bg-indigo-500/10',
    ring: 'ring-indigo-500/40',
  },
  rose: {
    border: 'border-rose-500',
    shadow: 'shadow-rose-500/20',
    text: 'text-rose-500',
    dot: 'bg-rose-500',
    bg: 'bg-rose-500/10',
    ring: 'ring-rose-500/40',
  },
  purple: {
    border: 'border-purple-500',
    shadow: 'shadow-purple-500/20',
    text: 'text-purple-500',
    dot: 'bg-purple-500',
    bg: 'bg-purple-500/10',
    ring: 'ring-purple-500/40',
  },
};

const DEFAULT_SETTINGS = {
  title: '',
  prompt: '',
  chapters: 20,
  words: 3000,
  auto_audit: true,
  auto_polish: true,
  force_design: false,
  llm_type: 'compatible',
  api_key: '',
  base_url: '',
  model: 'deepseek-v3',
  save_dir: '',
};

const AGENT_SECTION_MAP = {
  Designer: ['outline', 'characters', 'world', 'plots', 'map', 'timeline'],
  Planner: ['plots', 'timeline'],
  Writer: ['outline', 'guidance'],
  Auditor: ['guidance', 'timeline'],
  Polisher: ['guidance'],
};

const AGENT_CARD_KEY_BY_NAME = {
  Designer: 'agent_designer',
  Planner: 'agent_planner',
  Writer: 'agent_writer',
  Auditor: 'agent_auditor',
  Polisher: 'agent_polisher',
};

const AGENT_NAME_BY_CARD_KEY = Object.fromEntries(
  Object.entries(AGENT_CARD_KEY_BY_NAME).map(([name, key]) => [key, name]),
);

function getStatusLabel(job, liveState) {
  if (liveState?.status?.message) return liveState.status.message;
  if (job?.running) return job.message || '运行中';
  return '云端就绪';
}

function getAuditDimensionStates(agent) {
  const dimensions = ['time', 'space', 'character', 'plot', 'world', 'info'];
  const labels = {
    time: 'Time',
    space: 'Space',
    character: 'Character',
    plot: 'Plot',
    world: 'World',
    info: 'Info',
  };
  const recentEvents = agent?.recent_events || [];

  return dimensions.map((dimension) => {
    const latestEvent = [...recentEvents]
      .reverse()
      .find((event) => event?.meta?.dimension === dimension);
    return {
      key: dimension,
      label: labels[dimension],
      phase: latestEvent?.meta?.phase || 'idle',
      message: latestEvent?.message || '等待审计',
      meta: latestEvent?.meta || {},
    };
  });
}

function buildContentFromLive(liveState) {
  if (!liveState?.sections) return INITIAL_CONTENT;
  return {
    outline: liveState.sections.outline || '',
    world: liveState.sections.world || '',
    plots: liveState.sections.plots || '',
    characters: liveState.sections.characters || '',
    timeline: liveState.sections.timeline || '',
    map: liveState.sections.map || '',
    guidance: liveState.sections.guidance || '',
    agent_designer: '',
    agent_planner: '',
    agent_writer: '',
    agent_auditor: '',
    agent_polisher: '',
    chapters_panel: '',
  };
}

function getAgentPrimaryText(agent) {
  return agent?.error || agent?.output || agent?.prompt || agent?.context || '暂无实时消息';
}

export default function App() {
  const [content, setContent] = useState(INITIAL_CONTENT);
  const [layout, setLayout] = useState(INITIAL_LAYOUT);
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [maximizedKey, setMaximizedKey] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [showGuide, setShowGuide] = useState(true);
  const [isTouchDragging, setIsTouchDragging] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [liveState, setLiveState] = useState(null);
  const [job, setJob] = useState(null);
  const [novels, setNovels] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [selectedTitle, setSelectedTitle] = useState('');
  const [error, setError] = useState('');
  const [banner, setBanner] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);
  const [startingJob, setStartingJob] = useState(false);
  const [updatedSections, setUpdatedSections] = useState({});
  const dragRef = useRef(null);
  const canvasRef = useRef(null);
  const prevLiveRef = useRef(null);
  const updateTimersRef = useRef({});
  const touchRef = useRef({
    startDist: 0,
    startZoom: 1,
    startOffset: { x: 0, y: 0 },
    lastTouch: null,
    longPressTimer: null,
  });

  const aiStatus = useMemo(() => {
    const runningSections = new Set();
    const agents = liveState?.agents || {};
    Object.entries(agents).forEach(([name, agent]) => {
      if (agent?.status === 'running') {
        (AGENT_SECTION_MAP[name] || []).forEach((section) => runningSections.add(section));
        if (AGENT_CARD_KEY_BY_NAME[name]) {
          runningSections.add(AGENT_CARD_KEY_BY_NAME[name]);
        }
      }
    });
    return {
      runningSections: Array.from(runningSections),
      streamingSections: [],
    };
  }, [liveState]);

  useEffect(() => {
    return () => {
      Object.values(updateTimersRef.current).forEach((timer) => window.clearTimeout(timer));
    };
  }, []);

  const refreshNovels = async (preferredTitle = '') => {
    const response = await fetch('/api/novels');
    const data = await response.json();
    const items = data.items || [];
    setNovels(items);
    setJob(data.job || null);

    const titles = items.map((item) => item.title);
    const nextTitle =
      preferredTitle ||
      selectedTitle ||
      settings.title ||
      (titles.length > 0 ? titles[0] : '');
    if (nextTitle && titles.includes(nextTitle)) {
      setSelectedTitle(nextTitle);
    } else if (!selectedTitle && titles.length > 0) {
      setSelectedTitle(titles[0]);
    }
  };

  const loadSettings = async () => {
    const response = await fetch('/api/settings');
    const data = await response.json();
    const nextSettings = { ...DEFAULT_SETTINGS, ...(data.settings || {}) };
    setSettings(nextSettings);
    setJob(data.job || null);
    if (!selectedTitle && nextSettings.title) {
      setSelectedTitle(nextSettings.title);
    }
  };

  const loadLiveState = async (title) => {
    if (!title) return;
    try {
      const response = await fetch(`/api/novels/${encodeURIComponent(title)}/live`);
      if (!response.ok) {
        throw new Error(`加载实时状态失败: ${response.status}`);
      }
      const data = await response.json();
      setLiveState(data);
      setContent(buildContentFromLive(data));
      setError('');
    } catch (err) {
      setLiveState(null);
      setContent(INITIAL_CONTENT);
      setError(err.message || '加载实时状态失败');
    }
  };

  const loadChapterContent = async (title, chapterNum, fallbackMeta = null) => {
    if (!title || !chapterNum) return;
    const response = await fetch(`/api/novels/${encodeURIComponent(title)}/chapters/${chapterNum}`);
    if (!response.ok) {
      throw new Error(`加载章节正文失败: ${response.status}`);
    }
    const data = await response.json();
    setSelectedChapter({
      chapter_num: data.chapter_num,
      title: data.chapter_title || fallbackMeta?.title || '',
      word_count: data.word_count || fallbackMeta?.word_count || 0,
      content: data.content || '',
    });
  };

  const loadChapters = async (title) => {
    if (!title) {
      setChapters([]);
      setSelectedChapter(null);
      return;
    }
    const response = await fetch(`/api/novels/${encodeURIComponent(title)}/chapters`);
    if (!response.ok) {
      throw new Error(`加载章节列表失败: ${response.status}`);
    }
    const data = await response.json();
    const items = data.items || [];
    setChapters(items);
    const preferred =
      items.find((item) => item.chapter_num === selectedChapter?.chapter_num) ||
      items[items.length - 1] ||
      null;
    if (preferred) {
      await loadChapterContent(title, preferred.chapter_num, preferred);
    } else {
      setSelectedChapter(null);
    }
  };

  useEffect(() => {
    loadSettings().catch((err) => setError(err.message || '加载设置失败'));
    refreshNovels().catch((err) => setError(err.message || '加载小说列表失败'));
  }, []);

  useEffect(() => {
    if (!selectedTitle) return undefined;

    let cancelled = false;
    const eventSource = new EventSource(`/api/novels/${encodeURIComponent(selectedTitle)}/events/stream`);

    loadLiveState(selectedTitle);
    loadChapters(selectedTitle).catch((err) => setError(err.message || '加载章节失败'));

    eventSource.onmessage = (event) => {
      if (cancelled) return;
      try {
        const data = JSON.parse(event.data);
        setLiveState(data);
        setContent(buildContentFromLive(data));
      } catch (err) {
        setError(err.message || '解析实时事件失败');
      }
    };

    eventSource.onerror = () => {
      if (!cancelled) {
        setError('实时连接中断，等待服务恢复');
      }
    };

    return () => {
      cancelled = true;
      eventSource.close();
    };
  }, [selectedTitle]);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch('/api/job');
        const data = await response.json();
        setJob(data);
        if (!data.running && settings.title) {
          await refreshNovels(settings.title);
          await loadChapters(settings.title);
        }
      } catch {
        // ignore polling errors
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [settings.title, selectedTitle]);

  useEffect(() => {
    const preventMiddleScroll = (e) => {
      if (e.button === 1) e.preventDefault();
    };
    document.addEventListener('mousedown', preventMiddleScroll);
    return () => document.removeEventListener('mousedown', preventMiddleScroll);
  }, []);

  useEffect(() => {
    if (!liveState) return;
    const prev = prevLiveRef.current;
    const title = liveState.title || selectedTitle || settings.title || 'unknown';

    if (!prev || prev.event_seq !== liveState.event_seq) {
      console.info('[NOVEL_LIVE] state', {
        title,
        eventSeq: liveState.event_seq,
        status: liveState.status,
        overview: liveState.overview,
      });
    }

    const agents = liveState.agents || {};
    const nextUpdatedSections = new Set();
    Object.entries(agents).forEach(([name, agent]) => {
      const prevAgent = prev?.agents?.[name];
      if (!prevAgent || prevAgent.status !== agent.status || prevAgent.updated_at !== agent.updated_at) {
        (AGENT_SECTION_MAP[name] || []).forEach((section) => nextUpdatedSections.add(section));
        if (AGENT_CARD_KEY_BY_NAME[name]) {
          nextUpdatedSections.add(AGENT_CARD_KEY_BY_NAME[name]);
        }
        console.info(`[NOVEL_LIVE][${name}]`, {
          status: agent.status,
          updatedAt: agent.updated_at,
          meta: agent.meta,
          context: agent.context,
          prompt: agent.prompt,
          output: agent.output,
          error: agent.error,
        });
      }
    });

    const prevSections = prev?.sections || {};
    const currentSections = liveState.sections || {};
    Object.keys(currentSections).forEach((section) => {
      if ((currentSections[section] || '') !== (prevSections[section] || '')) {
        nextUpdatedSections.add(section);
      }
    });

    if (nextUpdatedSections.size > 0) {
      setUpdatedSections((current) => {
        const next = { ...current };
        nextUpdatedSections.forEach((section) => {
          next[section] = true;
          if (updateTimersRef.current[section]) {
            window.clearTimeout(updateTimersRef.current[section]);
          }
          updateTimersRef.current[section] = window.setTimeout(() => {
            setUpdatedSections((latest) => {
              const trimmed = { ...latest };
              delete trimmed[section];
              return trimmed;
            });
            delete updateTimersRef.current[section];
          }, 1600);
        });
        return next;
      });
    }

    prevLiveRef.current = liveState;
  }, [liveState, selectedTitle, settings.title]);

  const handleWheel = (e) => {
    if (maximizedKey) return;
    e.preventDefault();

    const zoomSpeed = 0.001;
    const minZoom = 0.2;
    const maxZoom = 3;
    const delta = -e.deltaY;
    const newZoom = Math.min(Math.max(zoom + delta * zoomSpeed, minZoom), maxZoom);

    if (newZoom !== zoom) {
      const rect = canvasRef.current.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const dx = (mouseX - canvasOffset.x) / zoom;
      const dy = (mouseY - canvasOffset.y) / zoom;

      setCanvasOffset({
        x: mouseX - dx * newZoom,
        y: mouseY - dy * newZoom,
      });
      setZoom(newZoom);
    }
  };

  const handleCanvasMouseDown = (e) => {
    const isMiddleClick = e.button === 1;
    const isBackgroundClick = e.target === e.currentTarget;

    if (isMiddleClick || isBackgroundClick) {
      if (isMiddleClick) e.preventDefault();
      setIsPanning(true);
      dragRef.current = { x: e.clientX - canvasOffset.x, y: e.clientY - canvasOffset.y };
    }
  };

  const getTouchDistance = (touches) => {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  };

  const getTouchCenter = (touches) => ({
    x: (touches[0].clientX + touches[1].clientX) / 2,
    y: (touches[0].clientY + touches[1].clientY) / 2,
  });

  const handleTouchStart = (e) => {
    if (maximizedKey) return;
    const touches = e.touches;

    if (touches.length === 2) {
      const dist = getTouchDistance(touches);
      const center = getTouchCenter(touches);
      touchRef.current = {
        ...touchRef.current,
        startDist: dist,
        startZoom: zoom,
        startCenter: center,
        startOffset: { ...canvasOffset },
      };
    } else if (touches.length === 1 && e.target === e.currentTarget) {
      touchRef.current = {
        ...touchRef.current,
        startTouch: { x: touches[0].clientX, y: touches[0].clientY },
        startOffset: { ...canvasOffset },
        isDragging: false,
      };
    }
  };

  const handleTouchMove = (e) => {
    if (maximizedKey) return;
    const touches = e.touches;

    if (touches.length === 2 && touchRef.current.startDist) {
      const dist = getTouchDistance(touches);
      const center = getTouchCenter(touches);
      const scale = dist / touchRef.current.startDist;
      const newZoom = Math.min(Math.max(touchRef.current.startZoom * scale, 0.2), 3);
      const rect = canvasRef.current.getBoundingClientRect();
      const centerX = center.x - rect.left;
      const centerY = center.y - rect.top;
      const dx = (centerX - touchRef.current.startOffset.x) / touchRef.current.startZoom;
      const dy = (centerY - touchRef.current.startOffset.y) / touchRef.current.startZoom;

      setZoom(newZoom);
      setCanvasOffset({
        x: centerX - dx * newZoom,
        y: centerY - dy * newZoom,
      });
    } else if (touches.length === 1 && touchRef.current.startTouch) {
      const dx = touches[0].clientX - touchRef.current.startTouch.x;
      const dy = touches[0].clientY - touchRef.current.startTouch.y;

      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        touchRef.current.isDragging = true;
        setCanvasOffset({
          x: touchRef.current.startOffset.x + dx,
          y: touchRef.current.startOffset.y + dy,
        });
      }
    }
  };

  const handleTouchEnd = () => {
    touchRef.current.startDist = 0;
    touchRef.current.startTouch = null;
    touchRef.current.isDragging = false;
  };

  const performCardDrag = (key, startClientX, startClientY) => {
    const initialPos = { ...layout[key] };

    const onMove = (moveEvent) => {
      const clientX = moveEvent.clientX || (moveEvent.touches && moveEvent.touches[0].clientX);
      const clientY = moveEvent.clientY || (moveEvent.touches && moveEvent.touches[0].clientY);

      setLayout((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          x: initialPos.x + (clientX - startClientX) / zoom,
          y: initialPos.y + (clientY - startClientY) / zoom,
        },
      }));
    };

    const onEnd = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onEnd);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onEnd);
      setIsTouchDragging(false);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('touchend', onEnd);
  };

  const startDraggingCard = (key, e) => {
    if (maximizedKey) return;
    if (e.button !== 0) return;
    e.stopPropagation();
    performCardDrag(key, e.clientX, e.clientY);
  };

  const handleCardTouchStart = (key, e) => {
    if (maximizedKey) return;
    const touch = e.touches[0];
    if (touchRef.current.longPressTimer) {
      clearTimeout(touchRef.current.longPressTimer);
    }
    touchRef.current.longPressStart = { x: touch.clientX, y: touch.clientY };
    touchRef.current.longPressTimer = setTimeout(() => {
      setIsTouchDragging(true);
      performCardDrag(key, touch.clientX, touch.clientY);
    }, 500);
  };

  const handleCardTouchMove = (e) => {
    if (touchRef.current.longPressStart && touchRef.current.longPressTimer) {
      const touch = e.touches[0];
      const dx = touch.clientX - touchRef.current.longPressStart.x;
      const dy = touch.clientY - touchRef.current.longPressStart.y;
      if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
        clearTimeout(touchRef.current.longPressTimer);
        touchRef.current.longPressTimer = null;
      }
    }
  };

  const handleCardTouchEnd = () => {
    if (touchRef.current.longPressTimer) {
      clearTimeout(touchRef.current.longPressTimer);
      touchRef.current.longPressTimer = null;
    }
    touchRef.current.longPressStart = null;
  };

  const startResizingCard = (key, e) => {
    e.stopPropagation();
    const isTouch = e.type === 'touchstart';
    const startX = isTouch ? e.touches[0].clientX : e.clientX;
    const startY = isTouch ? e.touches[0].clientY : e.clientY;
    const initialSize = { w: layout[key].w, h: layout[key].h };

    const onMove = (moveEvent) => {
      const clientX = moveEvent.clientX || (moveEvent.touches && moveEvent.touches[0].clientX);
      const clientY = moveEvent.clientY || (moveEvent.touches && moveEvent.touches[0].clientY);

      setLayout((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          w: Math.max(200, initialSize.w + (clientX - startX) / zoom),
          h: Math.max(150, initialSize.h + (clientY - startY) / zoom),
        },
      }));
    };

    const onEnd = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onEnd);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onEnd);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('touchend', onEnd);
  };

  const handleMouseMove = (e) => {
    if (isPanning) {
      setCanvasOffset({
        x: e.clientX - dragRef.current.x,
        y: e.clientY - dragRef.current.y,
      });
    }
  };

  const handleMouseUp = () => setIsPanning(false);
  const toggleMaximize = (key) => setMaximizedKey(maximizedKey === key ? null : key);

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    setError('');
    try {
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (!response.ok) {
        throw new Error(`保存设置失败: ${response.status}`);
      }
      const data = await response.json();
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
      setJob(data.job || null);
      if (settings.title) {
        setSelectedTitle(settings.title);
      }
      setBanner('设置已保存');
      await refreshNovels(settings.title);
    } catch (err) {
      setError(err.message || '保存设置失败');
    } finally {
      setSavingSettings(false);
      window.setTimeout(() => setBanner(''), 1800);
    }
  };

  const startJob = async () => {
    setStartingJob(true);
    setError('');
    try {
      const response = await fetch('/api/job/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `启动失败: ${response.status}`);
      }
      setJob(data.job || null);
      if (settings.title) {
        setSelectedTitle(settings.title);
      }
      setSettingsOpen(false);
      setBanner(data.message || '生成任务已启动');
      await refreshNovels(settings.title);
      await loadLiveState(settings.title);
    } catch (err) {
      setError(err.message || '启动失败');
    } finally {
      setStartingJob(false);
      window.setTimeout(() => setBanner(''), 1800);
    }
  };

  const renderAgentPanel = (agentName) => {
    const agent = liveState?.agents?.[agentName] || null;
    const auditDimensionStates = agentName === 'Auditor' ? getAuditDimensionStates(agent) : [];

    return (
      <div className="flex h-full flex-col bg-slate-900 p-4">
        <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-slate-600">
          {selectedTitle || settings.title || '未选择小说'}
        </div>
        <div className="mb-3 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">当前焦点</div>
              <div className="mt-1 text-sm font-semibold text-slate-200">{agentName}</div>
            </div>
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">
              <span
                className={`h-2 w-2 rounded-full ${
                  agent?.status === 'failed'
                    ? 'bg-rose-400'
                    : agent?.status === 'running'
                      ? 'bg-blue-400 animate-pulse'
                      : agent?.status === 'completed'
                        ? 'bg-emerald-400'
                        : 'bg-slate-600'
                }`}
              />
              <span>{agent?.status || 'idle'}</span>
            </div>
          </div>
          <div className="mt-2 text-[11px] leading-5 text-slate-500">
            {liveState?.status?.message || '暂无阶段消息'}
          </div>
          <div className="mt-2 text-[11px] leading-5 text-slate-400">
            {agent?.current_task || agent?.progress || '暂无任务'}
          </div>
        </div>
        <div className="mb-3 grid grid-cols-2 gap-2 text-[10px] text-slate-400">
          <div className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
            <div className="uppercase tracking-[0.18em] text-slate-500">Last Tool</div>
            <div className="mt-1 break-all text-slate-300">{agent?.last_tool?.name || '-'}</div>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
            <div className="uppercase tracking-[0.18em] text-slate-500">Tool Result</div>
            <div className="mt-1 break-all text-slate-300">
              {agent?.last_tool_result?.name
                ? `${agent.last_tool_result.name} / ${agent.last_tool_result.success ? 'ok' : 'failed'}`
                : '-'}
            </div>
          </div>
        </div>
        {agentName === 'Auditor' && (
          <div className="mb-3">
            <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">Audit Dimensions</div>
            <div className="grid grid-cols-2 gap-2">
              {auditDimensionStates.map((item) => {
                const phaseTone = item.phase === 'completed'
                  ? 'border-emerald-500/30 text-emerald-300'
                  : item.phase === 'unparsed'
                    ? 'border-amber-500/30 text-amber-300'
                    : item.phase === 'start'
                      ? 'border-blue-500/30 text-blue-300'
                      : 'border-slate-800 text-slate-400';
                return (
                  <div key={item.key} className={`rounded-xl border bg-slate-900 px-3 py-2 ${phaseTone}`}>
                    <div className="flex items-center justify-between text-[11px] font-semibold">
                      <span>{item.label}</span>
                      <span
                        className={`h-2 w-2 rounded-full ${
                          item.phase === 'completed'
                            ? 'bg-emerald-400'
                            : item.phase === 'unparsed'
                              ? 'bg-amber-400'
                              : item.phase === 'start'
                                ? 'bg-blue-400 animate-pulse'
                                : 'bg-slate-600'
                        }`}
                      />
                    </div>
                    <div className="mt-1 text-[10px] leading-5">{item.message}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        <textarea
          readOnly
          className="flex-1 w-full resize-none rounded-xl border border-slate-800 bg-slate-900 p-3 text-[12px] leading-6 text-slate-300 outline-none"
          value={getAgentPrimaryText(agent)}
        />
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Recent Events</div>
          <div className="mt-2 space-y-2">
            {(agent?.recent_events || []).slice(-4).reverse().map((event, index) => (
              <div key={`${event.timestamp}-${index}`} className="text-[11px] leading-5 text-slate-400">
                <span className="mr-2 uppercase tracking-[0.16em] text-slate-500">{event.type}</span>
                <span>{event.message}</span>
              </div>
            ))}
            {(!agent?.recent_events || agent.recent_events.length === 0) && (
              <div className="text-[11px] text-slate-500">暂无事件</div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const maximizedAgentName = AGENT_NAME_BY_CARD_KEY[maximizedKey];
  const maximizedAgent = maximizedAgentName ? liveState?.agents?.[maximizedAgentName] : null;
  const maximizedValue = maximizedAgentName
    ? getAgentPrimaryText(maximizedAgent)
    : maximizedKey === 'chapters_panel'
      ? (selectedChapter?.content || '暂无章节内容')
      : (content[maximizedKey] || '');
  const maximizedAuditDimensionStates = maximizedAgentName === 'Auditor'
    ? getAuditDimensionStates(maximizedAgent)
    : [];

  return (
    <div className="flex flex-col h-screen w-full bg-slate-950 text-slate-200 overflow-hidden select-none font-sans">
      <header className="h-14 border-b border-slate-800 flex items-center justify-between px-3 md:px-6 bg-slate-900/80 backdrop-blur-xl z-[100]">
        <div className="flex items-center gap-2 md:gap-6">
          <div className="flex items-center gap-2">
            <Zap size={20} className="text-blue-500 fill-blue-500" />
            <h1 className="font-black text-sm md:text-lg tracking-tighter">NOVEL_CANVAS</h1>
          </div>
          <div className="hidden md:flex max-w-[38rem] items-center gap-3 px-3 py-1 bg-slate-950 rounded-full border border-slate-800">
            <div className={`w-2 h-2 rounded-full ${job?.running ? 'bg-blue-500 animate-pulse' : 'bg-emerald-500'}`} />
            <span className="truncate text-[10px] font-bold text-slate-500" title={getStatusLabel(job, liveState)}>
              {getStatusLabel(job, liveState)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 md:gap-4">
          <div className="hidden md:flex items-center gap-2 bg-slate-800/50 px-2 md:px-3 py-1 rounded-md">
            <Search size={14} className="text-slate-500 hidden md:block" />
            <span className="text-xs font-mono text-slate-400">{Math.round(zoom * 100)}%</span>
          </div>
          <div className="hidden lg:block text-[10px] text-slate-600 font-mono tracking-tighter">
            X: {Math.round(canvasOffset.x)} Y: {Math.round(canvasOffset.y)}
          </div>
          <button
            onClick={startJob}
            disabled={startingJob || job?.running}
            className="flex items-center gap-2 rounded-lg bg-blue-500 px-3 py-2 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {startingJob ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            启动
          </button>
          <button
            onClick={() => setSettingsOpen(true)}
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      <main
        ref={canvasRef}
        className={`flex-1 relative overflow-hidden bg-slate-950 ${isPanning ? 'cursor-grabbing' : 'cursor-grab'} touch-none`}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <div
          className="absolute inset-0 pointer-events-none opacity-20"
          style={{
            backgroundImage: 'radial-gradient(#475569 1px, transparent 1px)',
            backgroundSize: `${32 * zoom}px ${32 * zoom}px`,
            backgroundPosition: `${canvasOffset.x}px ${canvasOffset.y}px`,
          }}
        />

        {banner && (
          <div className="absolute top-20 left-1/2 z-[170] -translate-x-1/2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs font-bold uppercase tracking-[0.2em] text-emerald-300 backdrop-blur">
            {banner}
          </div>
        )}

        {error && (
          <div className="absolute top-20 right-6 z-[170] max-w-md rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-200 backdrop-blur">
            {error}
          </div>
        )}

        <div
          className="absolute origin-top-left transition-transform duration-0"
          style={{
            transform: `translate(${canvasOffset.x}px, ${canvasOffset.y}px) scale(${zoom})`,
          }}
        >
          {Object.entries(layout).map(([key, config]) => {
            const isMaximized = maximizedKey === key;
            const Icon = config.icon;
            const isRunning = aiStatus.runningSections.includes(key);
            const isUpdated = Boolean(updatedSections[key]);
            const isStreaming = aiStatus.streamingSections.includes(key);
            const color = CARD_STYLES[config.color];
            const cardBorderClass = isStreaming
              ? `${color.border} ${color.shadow} ring-2 ring-offset-0 ring-slate-950 ring-white/30`
              : isRunning
                ? `${color.border} ${color.shadow}`
                : isUpdated
                  ? `${color.border} ${color.shadow} ring-2 ring-offset-0 ring-slate-950 ${color.ring}`
                  : 'border-slate-800 shadow-black';

            if (isMaximized) return null;

            return (
              <div
                key={key}
                className={`absolute bg-slate-900 rounded-2xl border-2 flex flex-col transition-all duration-300 shadow-2xl ${cardBorderClass}`}
                style={{
                  left: config.x,
                  top: config.y,
                  width: config.w,
                  height: config.h,
                  zIndex: isRunning || isUpdated || isStreaming ? 50 : 10,
                }}
              >
                {isRunning && !isStreaming && (
                  <div
                    className={`pointer-events-none absolute inset-0 rounded-2xl border-2 ${color.border} animate-pulse`}
                  />
                )}
                <div
                  className="p-3 border-b border-slate-800 flex items-center justify-between cursor-move bg-slate-900 rounded-t-2xl select-none"
                  onMouseDown={(e) => startDraggingCard(key, e)}
                  onTouchStart={(e) => handleCardTouchStart(key, e)}
                  onTouchMove={handleCardTouchMove}
                  onTouchEnd={handleCardTouchEnd}
                >
                  <div className="flex items-center gap-2">
                    <Icon size={16} className={color.text} />
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{config.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {(isRunning || isUpdated || isStreaming) && (
                      <div className="flex items-center gap-1 mr-2">
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${color.dot} ${
                            isStreaming ? 'animate-pulse' : isRunning ? 'animate-ping' : ''
                          }`}
                        />
                        <span className={`text-[9px] font-bold ${color.text}`}>
                          {isStreaming ? 'STREAM' : isRunning ? 'RUNNING' : 'UPDATED'}
                        </span>
                      </div>
                    )}
                    <button
                      onClick={() => toggleMaximize(key)}
                      className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-white"
                    >
                      <Maximize2 size={14} />
                    </button>
                  </div>
                </div>

                <div className="flex-1 overflow-hidden relative">
                  {AGENT_NAME_BY_CARD_KEY[key] ? (
                    renderAgentPanel(AGENT_NAME_BY_CARD_KEY[key])
                  ) : key === 'chapters_panel' ? (
                    <div className="flex h-full bg-slate-900">
                      <div className="w-[42%] border-r border-slate-800 p-3">
                        <div className="mb-3 text-[10px] uppercase tracking-[0.2em] text-slate-500">
                          Chapters
                        </div>
                        <div className="space-y-2 overflow-y-auto pr-1" style={{ height: '100%' }}>
                          {chapters.map((chapter) => {
                            const isSelected = selectedChapter?.chapter_num === chapter.chapter_num;
                            return (
                              <button
                                key={chapter.chapter_num}
                                type="button"
                                onClick={() => loadChapterContent(selectedTitle || settings.title, chapter.chapter_num, chapter).catch((err) => setError(err.message || '加载章节正文失败'))}
                                className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                                  isSelected
                                    ? 'border-amber-500/40 bg-slate-800 text-amber-200'
                                    : 'border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800'
                                }`}
                              >
                                <div className="text-[11px] font-semibold">
                                  第{chapter.chapter_num}章
                                </div>
                                <div className="mt-1 text-sm leading-5">
                                  {chapter.title || '未命名章节'}
                                </div>
                                <div className="mt-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">
                                  {chapter.word_count || 0} 字
                                </div>
                              </button>
                            );
                          })}
                          {chapters.length === 0 && (
                            <div className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-4 text-sm text-slate-500">
                              暂无已生成章节
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex-1 p-4">
                        <div className="mb-3 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
                          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">当前章节</div>
                          <div className="mt-1 text-sm font-semibold text-slate-200">
                            {selectedChapter ? `第${selectedChapter.chapter_num}章 ${selectedChapter.title || '未命名章节'}` : '请选择章节'}
                          </div>
                        </div>
                        <textarea
                          readOnly
                          className="h-[calc(100%-4.5rem)] w-full resize-none rounded-xl border border-slate-800 bg-slate-900 p-3 text-[12px] leading-6 text-slate-300 outline-none"
                          value={selectedChapter?.content || '请选择左侧章节查看正文'}
                        />
                      </div>
                    </div>
                  ) : (
                    <textarea
                      readOnly
                      className="w-full h-full bg-transparent p-4 text-sm text-slate-300 outline-none resize-none font-sans leading-relaxed scrollbar-hide"
                      value={content[key] || ''}
                      placeholder="等待实时数据..."
                    />
                  )}
                </div>

                <div
                  className="absolute bottom-1 right-1 cursor-nwse-resize p-2 text-slate-700 hover:text-slate-400 touch-manipulation"
                  onMouseDown={(e) => startResizingCard(key, e)}
                  onTouchStart={(e) => startResizingCard(key, e)}
                >
                  <GripHorizontal size={14} className="rotate-45" />
                </div>
              </div>
            );
          })}
        </div>

        {maximizedKey && (
          <div className="absolute inset-0 z-[200] bg-slate-950 flex items-center justify-center animate-in fade-in zoom-in duration-300">
            <div className={`w-full h-full md:w-[calc(100%-2rem)] md:h-[calc(100%-2rem)] md:max-w-7xl md:rounded-2xl bg-slate-900 border-2 ${CARD_STYLES[layout[maximizedKey].color].border} shadow-2xl flex flex-col`}>
              <div className="p-3 md:p-4 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2 md:gap-3">
                  <div className={`p-1.5 md:p-2 rounded-lg md:rounded-xl ${CARD_STYLES[layout[maximizedKey].color].bg}`}>
                    {React.createElement(layout[maximizedKey].icon, {
                      size: 20,
                      className: `${CARD_STYLES[layout[maximizedKey].color].text} md:w-6 md:h-6`,
                    })}
                  </div>
                  <div>
                    <h2 className="text-base md:text-lg font-bold text-white tracking-tight">{layout[maximizedKey].title}</h2>
                    <p className="hidden md:block text-slate-500 text-xs uppercase tracking-widest font-bold">沉浸式查看模式</p>
                  </div>
                </div>
                <button
                  onClick={() => toggleMaximize(maximizedKey)}
                  className="p-2 md:p-3 bg-slate-800 hover:bg-slate-700 rounded-xl md:rounded-2xl text-white transition-all hover:scale-110"
                >
                  <Minimize2 size={20} className="md:w-6 md:h-6" />
                </button>
              </div>
              {maximizedAgentName ? (
                <div className="flex flex-1 flex-col overflow-hidden p-4 md:p-8">
                  <div className="mb-4 rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-200">{maximizedAgentName}</div>
                      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                        {maximizedAgent?.status || 'idle'}
                      </div>
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-400">
                      {maximizedAgent?.current_task || maximizedAgent?.progress || liveState?.status?.message || '暂无任务'}
                    </div>
                  </div>
                  {maximizedAgentName === 'Auditor' && (
                    <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
                      {maximizedAuditDimensionStates.map((item) => (
                        <div key={item.key} className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
                          <div className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{item.label}</div>
                          <div className="mt-2 text-sm leading-6 text-slate-300">{item.message}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  <textarea
                    readOnly
                    autoFocus
                    className="flex-1 resize-none rounded-2xl border border-slate-800 bg-slate-900 p-4 text-base text-slate-200 outline-none md:p-6 md:text-lg lg:text-xl"
                    value={maximizedValue}
                  />
                </div>
              ) : (
                <textarea
                  readOnly
                  autoFocus
                  className="flex-1 bg-transparent p-4 md:p-8 lg:p-12 text-base md:text-lg lg:text-xl text-slate-200 outline-none resize-none font-serif leading-relaxed md:leading-loose"
                  value={maximizedValue}
                />
              )}
            </div>
          </div>
        )}

        {showGuide && (
          <div className="absolute top-2 md:top-4 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-slate-900/80 border border-slate-800 rounded-full text-[9px] text-slate-400 font-bold uppercase tracking-[0.2em] backdrop-blur flex items-center gap-3 shadow-lg">
            <span className="flex items-center gap-1"><MousePointer2 size={10} /> 拖拽移动</span>
            <div className="w-1 h-1 rounded-full bg-slate-700" />
            <span className="flex items-center gap-1 font-mono">滚轮缩放</span>
            <div className="w-1 h-1 rounded-full bg-slate-700" />
            <span className="font-mono">{selectedTitle || settings.title || '未选择小说'}</span>
            <button
              onClick={() => setShowGuide(false)}
              className="ml-1 p-0.5 hover:bg-slate-700 rounded-full transition-colors"
              title="隐藏提示"
            >
              <X size={10} />
            </button>
          </div>
        )}

        {settingsOpen && (
          <>
            <div
              className="absolute inset-0 z-[180] bg-slate-950/60 backdrop-blur-sm"
              onClick={() => setSettingsOpen(false)}
            />
            <aside className="absolute top-0 right-0 z-[190] h-full w-full max-w-xl border-l border-slate-800 bg-slate-900/95 shadow-2xl">
              <form
                className="flex h-full flex-col"
                onSubmit={(e) => {
                  e.preventDefault();
                  startJob();
                }}
              >
                <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
                  <div>
                    <h2 className="text-lg font-bold text-white">运行设置</h2>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">持久化到本地配置</p>
                  </div>
                  <button onClick={() => setSettingsOpen(false)} className="rounded-lg p-2 hover:bg-slate-800">
                    <X size={18} />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">已有小说</label>
                    <select
                      value={selectedTitle}
                      onChange={(e) => {
                        setSelectedTitle(e.target.value);
                        updateSetting('title', e.target.value);
                      }}
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                    >
                      <option value="">新建或手动填写标题</option>
                      {novels.map((novel) => (
                        <option key={novel.title} value={novel.title}>{novel.title}</option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">小说标题</label>
                      <input
                        value={settings.title}
                        onChange={(e) => updateSetting('title', e.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">保存目录</label>
                      <input
                        value={settings.save_dir}
                        onChange={(e) => updateSetting('save_dir', e.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">小说需求</label>
                    <textarea
                      value={settings.prompt}
                      onChange={(e) => updateSetting('prompt', e.target.value)}
                      rows={6}
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-200 outline-none resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">总章节</label>
                      <input
                        type="number"
                        min="1"
                        value={settings.chapters}
                        onChange={(e) => updateSetting('chapters', Number(e.target.value || 1))}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">每章字数</label>
                      <input
                        type="number"
                        min="500"
                        step="100"
                        value={settings.words}
                        onChange={(e) => updateSetting('words', Number(e.target.value || 500))}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">LLM 类型</label>
                      <input
                        value={settings.llm_type}
                        onChange={(e) => updateSetting('llm_type', e.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">模型</label>
                      <input
                        value={settings.model}
                        onChange={(e) => updateSetting('model', e.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Base URL</label>
                    <input
                      value={settings.base_url}
                      onChange={(e) => updateSetting('base_url', e.target.value)}
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-slate-500">API Key</label>
                    <input
                      type="password"
                      value={settings.api_key}
                      onChange={(e) => updateSetting('api_key', e.target.value)}
                      className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none"
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 px-3 py-3 text-sm text-slate-300">
                      <input type="checkbox" checked={settings.auto_audit} onChange={(e) => updateSetting('auto_audit', e.target.checked)} />
                      自动审计
                    </label>
                    <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 px-3 py-3 text-sm text-slate-300">
                      <input type="checkbox" checked={settings.auto_polish} onChange={(e) => updateSetting('auto_polish', e.target.checked)} />
                      自动润色
                    </label>
                    <label className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 px-3 py-3 text-sm text-slate-300">
                      <input type="checkbox" checked={settings.force_design} onChange={(e) => updateSetting('force_design', e.target.checked)} />
                      强制重设计
                    </label>
                  </div>

                  {job && (
                    <div className="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-300">
                      <div className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-500">后台任务</div>
                      <div>状态: {job.stage || 'idle'}</div>
                      <div className="break-words">消息: {liveState?.status?.message || job.message || '-'}</div>
                      <div>运行中: {job.running ? '是' : '否'}</div>
                    </div>
                  )}
                </div>

                <div className="border-t border-slate-800 px-5 py-4 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={saveSettings}
                    disabled={savingSettings}
                    className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-bold text-slate-200 transition hover:bg-slate-700 disabled:opacity-60"
                  >
                    {savingSettings ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                    保存设置
                  </button>
                  <button
                    type="submit"
                    disabled={startingJob || job?.running}
                    className="flex items-center gap-2 rounded-xl bg-blue-500 px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-400 disabled:opacity-60"
                  >
                    {startingJob ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                    启动生成
                  </button>
                </div>
              </form>
            </aside>
          </>
        )}
      </main>
    </div>
  );
}
