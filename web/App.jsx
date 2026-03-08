import React, { useEffect, useState } from 'react';
import {
  Activity,
  BookOpen,
  Clock3,
  FileText,
  Loader2,
  Map,
  MessageSquareText,
  Network,
  ScrollText,
  Sparkles,
  Users,
} from 'lucide-react';

const SECTION_META = {
  outline: { title: '设计大纲', icon: BookOpen },
  guidance: { title: '用户指导', icon: MessageSquareText },
  characters: { title: '角色设定', icon: Users },
  world: { title: '世界观', icon: Sparkles },
  plots: { title: '章节蓝图', icon: Network },
  map: { title: '地图结构', icon: Map },
  timeline: { title: '时间轴', icon: Clock3 },
};

const AGENT_ORDER = ['Designer', 'Planner', 'Writer', 'Auditor', 'Polisher'];

const STATUS_STYLES = {
  idle: 'border-slate-700 bg-slate-900 text-slate-300',
  running: 'border-cyan-500 bg-cyan-500/10 text-cyan-200',
  completed: 'border-emerald-500 bg-emerald-500/10 text-emerald-200',
  failed: 'border-rose-500 bg-rose-500/10 text-rose-200',
};

function SectionCard({ sectionKey, content }) {
  const meta = SECTION_META[sectionKey];
  const Icon = meta.icon;

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-[0_20px_80px_rgba(15,23,42,0.35)]">
      <div className="mb-4 flex items-center gap-3">
        <div className="rounded-2xl border border-slate-700 bg-slate-950 p-2">
          <Icon size={18} className="text-cyan-300" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">{meta.title}</h3>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{sectionKey}</p>
        </div>
      </div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
        {content || '暂无数据'}
      </pre>
    </section>
  );
}

function AgentCard({ name, data }) {
  const status = data?.status || 'idle';
  const style = STATUS_STYLES[status] || STATUS_STYLES.idle;
  const meta = data?.meta || {};

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{name}</h3>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">agent runtime</p>
        </div>
        <div className={`rounded-full border px-3 py-1 text-xs font-semibold ${style}`}>
          {status}
        </div>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 text-xs text-slate-400">
        <div className="rounded-2xl bg-slate-950/80 p-3">
          <div className="mb-1 text-slate-500">更新时间</div>
          <div>{data?.updated_at || '-'}</div>
        </div>
        <div className="rounded-2xl bg-slate-950/80 p-3">
          <div className="mb-1 text-slate-500">迭代次数</div>
          <div>{data?.iteration_count || 0}</div>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Context</div>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-slate-950/80 p-3 text-sm leading-6 text-slate-300">
            {data?.context || '暂无上下文'}
          </pre>
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Prompt</div>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-slate-950/80 p-3 text-sm leading-6 text-slate-300">
            {data?.prompt || '暂无输入'}
          </pre>
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Output</div>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-slate-950/80 p-3 text-sm leading-6 text-slate-200">
            {data?.error || data?.output || '暂无输出'}
          </pre>
        </div>

        <div className="rounded-2xl bg-slate-950/80 p-3 text-xs text-slate-400">
          <div className="mb-2 text-slate-500">Meta</div>
          <pre className="whitespace-pre-wrap break-words">{JSON.stringify(meta, null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}

export default function App() {
  const [novels, setNovels] = useState([]);
  const [selectedTitle, setSelectedTitle] = useState('');
  const [liveState, setLiveState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;

    async function loadNovels() {
      setLoading(true);
      setError('');
      try {
        const response = await fetch('/api/novels');
        const data = await response.json();
        if (!mounted) return;
        const items = data.items || [];
        setNovels(items);
        if (!selectedTitle && items.length > 0) {
          setSelectedTitle(items[0].title);
        }
      } catch (err) {
        if (!mounted) return;
        setError(err.message || '加载小说列表失败');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadNovels();
    return () => {
      mounted = false;
    };
  }, [selectedTitle]);

  useEffect(() => {
    if (!selectedTitle) return undefined;

    let eventSource;
    let cancelled = false;

    async function loadInitial() {
      try {
        const response = await fetch(`/api/novels/${encodeURIComponent(selectedTitle)}/live`);
        if (!response.ok) {
          throw new Error(`加载实时状态失败: ${response.status}`);
        }
        const data = await response.json();
        if (!cancelled) {
          setLiveState(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || '加载实时状态失败');
        }
      }
    }

    loadInitial();

    eventSource = new EventSource(`/api/novels/${encodeURIComponent(selectedTitle)}/events/stream`);
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLiveState(data);
      } catch (err) {
        setError(err.message || '解析实时事件失败');
      }
    };
    eventSource.onerror = () => {
      setError('实时连接中断，等待服务恢复');
    };

    return () => {
      cancelled = true;
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [selectedTitle]);

  const sections = liveState?.sections || {};
  const agents = liveState?.agents || {};
  const overview = liveState?.overview || {};
  const status = liveState?.status || {};

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.15),_transparent_28%),linear-gradient(180deg,_#020617_0%,_#0f172a_45%,_#111827_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1800px] gap-6 p-4 md:p-6">
        <aside className="w-full max-w-xs rounded-[2rem] border border-slate-800 bg-slate-950/80 p-5 backdrop-blur-xl">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 p-3">
              <FileText size={20} className="text-cyan-300" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Novel Agents Live</h1>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">real runtime</p>
            </div>
          </div>

          <div className="mb-4 rounded-3xl border border-slate-800 bg-slate-900/80 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.25em] text-slate-500">状态</span>
              {loading ? <Loader2 size={14} className="animate-spin text-cyan-300" /> : <Activity size={14} className="text-cyan-300" />}
            </div>
            <div className="text-sm text-slate-200">{status.message || '等待数据'}</div>
            <div className="mt-2 text-xs text-slate-500">{status.stage || 'idle'}</div>
          </div>

          <div className="space-y-3">
            {novels.map((novel) => (
              <button
                key={novel.title}
                onClick={() => {
                  setSelectedTitle(novel.title);
                  setError('');
                }}
                className={`w-full rounded-3xl border p-4 text-left transition ${
                  selectedTitle === novel.title
                    ? 'border-cyan-400 bg-cyan-400/10'
                    : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
                }`}
              >
                <div className="mb-2 text-sm font-semibold text-white">{novel.title}</div>
                <div className="text-xs text-slate-400">
                  {novel.chapter_count} 章 / {novel.total_words} 字
                </div>
              </button>
            ))}
          </div>

          {!loading && novels.length === 0 && (
            <div className="mt-6 rounded-3xl border border-dashed border-slate-700 p-4 text-sm text-slate-400">
              还没有小说数据。先运行 `novel create` 或 `novel write`。
            </div>
          )}
        </aside>

        <main className="flex-1 space-y-6">
          <section className="rounded-[2rem] border border-slate-800 bg-slate-950/70 p-6 backdrop-blur-xl">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="mb-2 text-xs uppercase tracking-[0.35em] text-cyan-300">selected novel</p>
                <h2 className="text-3xl font-semibold text-white">{selectedTitle || '未选择小说'}</h2>
              </div>
              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 px-4 py-3 text-right">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-500">最近更新</div>
                <div className="mt-1 text-sm text-slate-300">{liveState?.updated_at || '-'}</div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-3xl bg-slate-900/80 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-500">当前阶段</div>
                <div className="mt-2 text-lg font-semibold text-white">{overview.current_phase || '-'}</div>
              </div>
              <div className="rounded-3xl bg-slate-900/80 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-500">当前章节</div>
                <div className="mt-2 text-lg font-semibold text-white">{overview.current_chapter || 0}</div>
              </div>
              <div className="rounded-3xl bg-slate-900/80 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-500">总章节</div>
                <div className="mt-2 text-lg font-semibold text-white">{overview.total_chapters || 0}</div>
              </div>
              <div className="rounded-3xl bg-slate-900/80 p-4">
                <div className="text-xs uppercase tracking-[0.25em] text-slate-500">已完成章节</div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {(overview.completed_chapters || []).join(', ') || '-'}
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-3xl bg-slate-900/80 p-4">
                <div className="mb-2 text-xs uppercase tracking-[0.25em] text-slate-500">用户需求</div>
                <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
                  {overview.user_prompt || '暂无数据'}
                </pre>
              </div>
              <div className="rounded-3xl bg-slate-900/80 p-4">
                <div className="mb-2 text-xs uppercase tracking-[0.25em] text-slate-500">全局摘要</div>
                <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
                  {overview.global_summary || '暂无数据'}
                </pre>
              </div>
            </div>

            {error && (
              <div className="mt-4 rounded-3xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            )}
          </section>

          <section>
            <div className="mb-4 flex items-center gap-3">
              <ScrollText size={18} className="text-cyan-300" />
              <h2 className="text-xl font-semibold text-white">Agent 实时上下文与输出</h2>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              {AGENT_ORDER.map((name) => (
                <AgentCard key={name} name={name} data={agents[name]} />
              ))}
            </div>
          </section>

          <section>
            <div className="mb-4 flex items-center gap-3">
              <BookOpen size={18} className="text-cyan-300" />
              <h2 className="text-xl font-semibold text-white">当前真实上下文分区</h2>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              {Object.keys(SECTION_META).map((key) => (
                <SectionCard key={key} sectionKey={key} content={sections[key]} />
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
