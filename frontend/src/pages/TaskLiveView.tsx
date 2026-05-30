import { useQuery } from '@tanstack/react-query';
import { Fragment, useEffect, useState } from 'react';
import { Activity, ArrowLeft, ChevronDown, ChevronRight, ExternalLink, Heart, Image as ImageIcon, Video } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader } from '../components/ui/card';

const PAGE_SIZE = 10;

type LiveStatTone = 'sky' | 'emerald' | 'violet' | 'rose';

const liveStatToneClass: Record<LiveStatTone, { border: string; bg: string; icon: string; text: string; stroke: string; track: string }> = {
  sky: {
    border: 'border-[rgba(56,189,248,0.34)]',
    bg: 'bg-[rgba(14,165,233,0.10)]',
    icon: 'text-sky-300',
    text: 'text-sky-100',
    stroke: '#38bdf8',
    track: 'rgba(56,189,248,0.16)',
  },
  emerald: {
    border: 'border-[rgba(52,211,153,0.34)]',
    bg: 'bg-[rgba(16,185,129,0.10)]',
    icon: 'text-emerald-300',
    text: 'text-emerald-100',
    stroke: '#34d399',
    track: 'rgba(52,211,153,0.16)',
  },
  violet: {
    border: 'border-[rgba(167,139,250,0.34)]',
    bg: 'bg-[rgba(139,92,246,0.10)]',
    icon: 'text-violet-300',
    text: 'text-violet-100',
    stroke: '#a78bfa',
    track: 'rgba(167,139,250,0.16)',
  },
  rose: {
    border: 'border-[rgba(251,113,133,0.36)]',
    bg: 'bg-[rgba(244,63,94,0.10)]',
    icon: 'text-rose-300',
    text: 'text-rose-100',
    stroke: '#fb7185',
    track: 'rgba(251,113,133,0.16)',
  },
};

function clampPercent(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function percentFromValue(value: number, baseline: number) {
  if (value <= 0) return 0;
  return clampPercent((value / Math.max(value, baseline)) * 100);
}

function LiveStatCard({
  icon: Icon,
  label,
  value,
  detail,
  percent,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  percent: number;
  tone: LiveStatTone;
}) {
  const toneClass = liveStatToneClass[tone];
  const safePercent = clampPercent(percent);

  return (
    <Card className={`${toneClass.border} ${toneClass.bg}`}>
      <CardContent>
        <div className="flex items-center gap-4">
          <div className="relative h-[72px] w-[72px] shrink-0" aria-hidden="true">
            <svg className="h-[72px] w-[72px]" viewBox="0 0 72 72">
              <circle cx="36" cy="36" r="28" fill="none" stroke={toneClass.track} strokeWidth="8" />
              <circle
                cx="36"
                cy="36"
                r="28"
                fill="none"
                pathLength="100"
                stroke={toneClass.stroke}
                strokeDasharray={`${safePercent} ${100 - safePercent}`}
                strokeLinecap="round"
                strokeWidth="8"
                transform="rotate(-90 36 36)"
              />
            </svg>
            <div className={`absolute inset-0 flex items-center justify-center ${toneClass.icon}`}>
              <Icon className="h-5 w-5" />
            </div>
          </div>
          <div className="min-w-0">
            <div className="text-sm text-muted-foreground">{label}</div>
            <div className={`mt-1 truncate text-3xl font-bold leading-tight ${toneClass.text}`}>{value}</div>
            <div className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{detail}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function displayLiveTaskTitle(task: { title: string; task_type: string }) {
  const title = (task.title || '').trim();
  if (task.task_type === 'benchmark_account') {
    return title.replace(/^对标账号\s*[-—:：]\s*/u, '') || title || '未命名任务';
  }
  return title || '未命名任务';
}

export function TaskLiveView() {
  const { id } = useParams<{ id: string }>();
  const taskId = parseInt(id || '0', 10);
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // 获取任务信息
  const { data: taskData } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.task(taskId),
    refetchInterval: 5000,
  });

  // 获取实时数据流（每 3 秒刷新）
  const { data: streamData, isLoading } = useQuery({
    queryKey: ['task-items-stream', taskId, offset],
    queryFn: () => api.taskItemsStream(taskId, { offset, limit: PAGE_SIZE }),
    refetchInterval: 3000,
  });

  const task = taskData?.task;
  const items = streamData?.items || [];
  const total = streamData?.total || 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  // 统计数据
  const imageCount = items.filter(item => item.media_type === 'photo').length;
  const videoCount = items.filter(item => item.media_type === 'video' || item.media_type === 'animated_gif').length;
  const totalInteractions = items.reduce((sum, item) => sum + item.favorite_count + item.retweet_count + item.reply_count, 0);

  useEffect(() => {
    if (total > 0 && offset >= total) {
      setOffset(Math.max(0, Math.floor((total - 1) / PAGE_SIZE) * PAGE_SIZE));
    }
  }, [offset, total]);

  return (
    <div className="p-6 space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/tasks/${taskId}`)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回任务详情
          </Button>
          <div>
            <h1 className="text-2xl font-bold">实时数据流</h1>
            {task && <p className="text-sm text-muted-foreground">{displayLiveTaskTitle(task)}</p>}
          </div>
        </div>
        {task?.status === 'running' && (
          <div className="flex items-center gap-2 text-sm text-green-600">
            <div className="w-2 h-2 bg-green-600 rounded-full animate-pulse" />
            采集中...
          </div>
        )}
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <LiveStatCard icon={Activity} label="总推文数" value={total.toLocaleString()} detail={`当前显示 ${items.length} 条`} percent={percentFromValue(total, 100)} tone="sky" />
        <LiveStatCard icon={ImageIcon} label="本页图片" value={imageCount.toLocaleString()} detail={`占本页 ${items.length ? Math.round((imageCount / items.length) * 100) : 0}%`} percent={items.length ? (imageCount / items.length) * 100 : 0} tone="emerald" />
        <LiveStatCard icon={Video} label="本页视频" value={videoCount.toLocaleString()} detail={`含动图与视频`} percent={items.length ? (videoCount / items.length) * 100 : 0} tone="violet" />
        <LiveStatCard icon={Heart} label="本页互动" value={totalInteractions.toLocaleString()} detail="点赞、转推、评论合计" percent={percentFromValue(totalInteractions, 1000)} tone="rose" />
      </div>

      {/* 数据表格 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">采集数据</h2>
            <div className="text-sm text-muted-foreground">
              {total ? `显示 ${offset + 1}-${Math.min(offset + PAGE_SIZE, total)} 条，共 ${total} 条` : '共 0 条'}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && items.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">加载中...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">暂无数据</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr className="text-left">
                    <th className="pb-2 font-medium">时间</th>
                    <th className="pb-2 font-medium">用户</th>
                    <th className="pb-2 font-medium">内容</th>
                    <th className="pb-2 font-medium">媒体</th>
                    <th className="pb-2 font-medium text-right">互动</th>
                    <th className="pb-2 font-medium">链接</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <Fragment key={item.id}>
                      <tr className="border-b hover:bg-muted/50">
                        <td className="py-2 pr-3 text-muted-foreground whitespace-nowrap">
                          {item.tweet_date || '-'}
                        </td>
                        <td className="py-2 pr-3">
                          <div className="max-w-[180px]">
                            <div className="truncate font-medium">{item.display_name || '-'}</div>
                            <div className="truncate text-xs text-muted-foreground">@{item.user_name || '-'}</div>
                          </div>
                        </td>
                        <td className="py-2 pr-3 max-w-md">
                          <button
                            type="button"
                            onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                            className="line-clamp-2 min-h-[40px] cursor-pointer break-words text-left leading-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]"
                            aria-expanded={expandedId === item.id}
                          >
                            {item.tweet_content || '无正文内容'}
                          </button>
                        </td>
                        <td className="py-2 pr-3">
                          {item.media_type ? (
                            <div className="flex items-center gap-1 text-xs whitespace-nowrap">
                              {item.media_type === 'photo' && <ImageIcon className="w-3 h-3" />}
                              {(item.media_type === 'video' || item.media_type === 'animated_gif') && <Video className="w-3 h-3" />}
                              {item.media_type}
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </td>
                        <td className="py-2 pr-3 text-right">
                          <div className="flex justify-end gap-2 text-xs whitespace-nowrap">
                            <span>赞 {item.favorite_count}</span>
                            <span>转 {item.retweet_count}</span>
                            <span>评 {item.reply_count}</span>
                          </div>
                        </td>
                        <td className="py-2">
                          <div className="flex items-center gap-2">
                            {item.tweet_url && (
                              <a
                                href={item.tweet_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[hsl(var(--line))] text-[hsl(var(--primary-dark))] hover:bg-[hsl(var(--panel-soft))]"
                                aria-label="打开原文"
                              >
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                            <button
                              type="button"
                              onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[hsl(var(--line))] text-[hsl(var(--muted))] hover:bg-[hsl(var(--panel-soft))]"
                              aria-label={expandedId === item.id ? '收起正文' : '展开正文'}
                            >
                              {expandedId === item.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandedId === item.id && (
                        <tr key={`${item.id}-expanded`} className="border-b bg-[rgba(15,23,42,0.38)]">
                          <td colSpan={6} className="px-3 py-3">
                            <div className="whitespace-pre-wrap break-words text-sm leading-6">{item.tweet_content || '无正文内容'}</div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[hsl(var(--line))] pt-4">
            <div className="text-xs text-muted-foreground">
              {total ? `${offset + 1}-${Math.min(offset + PAGE_SIZE, total)} / ${total}` : '0 / 0'}
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={!canPrev} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>上一页</Button>
              <Button variant="secondary" size="sm" disabled={!canNext} onClick={() => setOffset(offset + PAGE_SIZE)}>下一页</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
