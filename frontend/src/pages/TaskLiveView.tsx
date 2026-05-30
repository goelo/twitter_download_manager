import { useQuery } from '@tanstack/react-query';
import { Fragment, useEffect, useState } from 'react';
import { ArrowLeft, ChevronDown, ChevronRight, ExternalLink, Image as ImageIcon, Video } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader } from '../components/ui/card';

const PAGE_SIZE = 10;

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
            {task && <p className="text-sm text-muted-foreground">{task.title}</p>}
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
        <Card>
          <CardHeader className="pb-2">
            <div className="text-sm text-muted-foreground">总推文数</div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <div className="text-sm text-muted-foreground flex items-center gap-1">
              <ImageIcon className="w-4 h-4" />
              本页图片
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{imageCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <div className="text-sm text-muted-foreground flex items-center gap-1">
              <Video className="w-4 h-4" />
              本页视频
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{videoCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <div className="text-sm text-muted-foreground">本页互动</div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{totalInteractions.toLocaleString()}</div>
          </CardContent>
        </Card>
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
                          <div className="truncate">{item.tweet_content || '无正文内容'}</div>
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
