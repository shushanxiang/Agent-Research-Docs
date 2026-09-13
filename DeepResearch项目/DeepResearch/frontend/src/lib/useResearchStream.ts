// 基于 SSE 的研究流 hook
// 与 @langchain/langgraph-sdk 的 useStream 并存，用于异步任务场景

import { useState, useRef, useCallback } from "react";

const API_BASE_URL = "";

interface ResearchEvent {
  generate_plan?: { plan: string };
  generate_query?: { search_query: string[] };
  web_research?: { sources_gathered: any[] };
  reflection?: any;
  finalize_answer?: any;
  task_paused?: boolean;
  token?: { text: string; node: string };
  error?: string;
}

interface UseResearchStreamReturn {
  events: ResearchEvent[];
  messages: any[];
  isLoading: boolean;
  /** 当前正在流式输出的节点名称（null 表示非流式状态） */
  streamingNode: string | null;
  /** 当前节点已流式输出的累计文本 */
  streamingContent: string;
  submit: (input: string, effort: string, model: string, extra?: { plan?: string; planStatus?: string }) => Promise<void>;
  stop: () => void;
}

export function useResearchStream(): UseResearchStreamReturn {
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingNode, setStreamingNode] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);
  const messageIdCounter = useRef(0);
  const planRef = useRef("");  // 缓存 generate_plan 中的计划内容
  const taskIdRef = useRef<string>("");  // 保存首次任务响应的 task_id，后续提交复用

  // 流式状态 refs（避免闭包过期问题）
  const streamingNodeRef = useRef<string | null>(null);
  const streamingContentRef = useRef("");

  /** 重置流式状态 */
  const _resetStreaming = useCallback(() => {
    streamingNodeRef.current = null;
    streamingContentRef.current = "";
    setStreamingNode(null);
    setStreamingContent("");
  }, []);

  const submit = useCallback(
    async (input: string, effort: string, model: string, extra?: { plan?: string; planStatus?: string }) => {
      if (!input.trim()) return;

      // 停止之前的连接
      stop();

      setIsLoading(true);
      setEvents([]);
      planRef.current = "";
      _resetStreaming();

      // 首次提交时清空 taskIdRef，让后端生成新 task_id
      const isFirstSubmit = messages.length === 0;
      if (isFirstSubmit) {
        taskIdRef.current = "";
      }

      const humanMsg = {
        type: "human",
        content: input,
        id: String(++messageIdCounter.current),
      };
      setMessages(prev => [...prev, humanMsg]);

      let initial_search_query_count: number;
      let max_research_loops: number;
      switch (effort) {
        case "low":
          initial_search_query_count = 1;
          max_research_loops = 1;
          break;
        case "medium":
        default:
          initial_search_query_count = 3;
          max_research_loops = 3;
          break;
        case "high":
          initial_search_query_count = 5;
          max_research_loops = 10;
          break;
      }

      try {
        // 构建请求体（包含完整对话历史和 plan 状态）
        const body: any = {
          messages: [...messages, humanMsg],
          initial_search_query_count,
          max_research_loops,
          reasoning_model: model,
        };
        if (extra?.plan) {
          body.plan = extra.plan;
          body.plan_status = extra.planStatus || "confirmed";
        }
        // 后续提交回传同一个 task_id，使后端复用 LangGraph checkpoint
        if (taskIdRef.current) {
          body.task_id = taskIdRef.current;
        }

        // 1. 提交任务，立即拿到 task_id
        const res = await fetch(`${API_BASE_URL}/api/research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || `HTTP ${res.status}`);
        }

        const { stream_url, task_id } = await res.json();

        // 保存 task_id 供后续提交复用
        if (task_id) {
          taskIdRef.current = task_id;
        }

        // 2. 建立 SSE 连接接收事件
        const es = new EventSource(`${API_BASE_URL}${stream_url}`);
        eventSourceRef.current = es;

        es.onmessage = (e) => {
          try {
            const raw = JSON.parse(e.data);

            // ── 处理 token 流式事件 ──────────────────────────
            if (raw.token) {
              const { text, node } = raw.token as { text: string; node: string };
              if (node !== streamingNodeRef.current) {
                // 新节点开始流式
                streamingNodeRef.current = node;
                streamingContentRef.current = text;
                setStreamingNode(node);
                setStreamingContent(text);
              } else {
                // 同一节点继续追加
                streamingContentRef.current += text;
                setStreamingContent(prev => prev + text);
              }
              return; // token 事件不需要进一步处理
            }

            const event: ResearchEvent = raw;

            if (event.error) {
              setIsLoading(false);
              setEvents(prev => [...prev, event]);
              _resetStreaming();
              es.close();
              return;
            }

            setEvents(prev => [...prev, event]);

            // 节点完成事件到达 → 清空对应节点的流式 buffer
            if (event.generate_plan) {
              planRef.current = event.generate_plan.plan || "";
              if (streamingNodeRef.current === "generate_plan") {
                _resetStreaming();
              }
            }

            // finalize_answer 时结束
            if (event.finalize_answer) {
              setIsLoading(false);
              // 使用后端 Post.extract_pattern 清洗后的内容（不含 markdown fence）
              const finalContent = (event.finalize_answer as any)?.messages?.[0]?.content || "";
              setMessages(prev => [
                ...prev,
                {
                  type: "ai",
                  content: finalContent,
                  id: String(++messageIdCounter.current),
                },
              ]);
              _resetStreaming();
              es.close();
            }

            // task_paused 时结束（等待 Plan 确认，后续继续用本 hook 提交确认）
            if (event.task_paused) {
              setIsLoading(false);
              _resetStreaming();
              // 从缓存的 generate_plan 事件中获取计划内容
              const planContent = planRef.current;
              setMessages(prev => [
                ...prev,
                {
                  type: "ai",
                  content: planContent,
                  id: String(++messageIdCounter.current),
                },
              ]);
              es.close();
            }
          } catch {
            // 忽略解析错误
          }
        };

        es.onerror = () => {
          setIsLoading(false);
          _resetStreaming();
          es.close();
        };
      } catch (err: any) {
        setIsLoading(false);
        _resetStreaming();
        setEvents(prev => [
          ...prev,
          { error: err.message || "提交失败" } as ResearchEvent,
        ]);
      }
    },
    [_resetStreaming]
  );

  const stop = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setIsLoading(false);
    _resetStreaming();
  }, [_resetStreaming]);

  return { events, messages, isLoading, streamingNode, streamingContent, submit, stop };
}
