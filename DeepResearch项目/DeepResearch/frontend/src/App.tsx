import { useStream } from "@langchain/langgraph-sdk/react";
import { useResearchStream } from "@/lib/useResearchStream";
import type { Message } from "@langchain/langgraph-sdk";
import { useState, useEffect, useRef, useCallback } from "react";
import { ProcessedEvent } from "@/components/ActivityTimeline";
import { WelcomeScreen } from "@/components/WelcomeScreen";
import { ChatMessagesView } from "@/components/ChatMessagesView";
import { ResearchStreamChatView } from "@/components/ResearchStreamChatView";
import { Button } from "@/components/ui/button";

export default function App() {
  const [processedEventsTimeline, setProcessedEventsTimeline] = useState<
    ProcessedEvent[]
  >([]);
  const [historicalActivities, setHistoricalActivities] = useState<
    Record<string, ProcessedEvent[]>
  >({});
  const [awaitingPlanConfirmation, setAwaitingPlanConfirmation] = useState("unconfirmed");
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const hasFinalizeEventOccurredRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [savedEffort, setSavedEffort] = useState("medium");
  const [savedModel, setSavedModel] = useState("qwen-plus-latest");
  const thread = useStream<{
    messages: Message[];
    initial_search_query_count: number;
    max_research_loops: number;
    reasoning_model: string;
    plan_status: string;
  }>({
    apiUrl: "",
    assistantId: "agent",
    messagesKey: "messages",
    onUpdateEvent: (event: any) => {
      let processedEvent: ProcessedEvent | null = null;
      if (event.generate_plan){
        processedEvent = {
          title: "生成计划",
          data: event.generate_plan?.plan || "No Plan to generate"
        }
        setAwaitingPlanConfirmation("unconfirmed");
        hasFinalizeEventOccurredRef.current = true;
      }
      else if (event.generate_query) {
        processedEvent = {
          title: "生成搜索查询",
          data: event.generate_query?.search_query?.join(", ") || "",
        };
      } else if (event.web_research) {
        const sources = event.web_research.sources_gathered || [];
        const numSources = sources.length;
        const uniqueLabels = [
          ...new Set(sources.map((s: any) => s.label).filter(Boolean)),
        ];
        const exampleLabels = uniqueLabels.slice(0, 3).join(", ");
        processedEvent = {
          title: "网络研究",
          data: `Gathered ${numSources} sources. Related to: ${
            exampleLabels || "N/A"
          }.`,
        };
      } else if (event.reflection) {
        processedEvent = {
          title: "反思和分析",
          data: "Analysing Web Research Results",
        };
      } else if (event.finalize_answer) {
        processedEvent = {
          title: "最终确定答案",
          data: "Composing and presenting the final answer.",
        };
        hasFinalizeEventOccurredRef.current = true;
      }
      if (processedEvent) {
        setProcessedEventsTimeline((prevEvents) => [
          ...prevEvents,
          processedEvent!,
        ]);
      }
    },
    onError: (error: any) => {
      setError(error.message);
    },
  });

  // 异步任务通道（首次提交走此通道，Plan 确认后切回 useStream）
  const researchStream = useResearchStream();

  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollViewport = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollViewport) {
        scrollViewport.scrollTop = scrollViewport.scrollHeight;
      }
    }
  }, [thread.messages]);

  useEffect(() => {
    if (
      hasFinalizeEventOccurredRef.current &&
      !thread.isLoading &&
      thread.messages.length > 0
    ) {
      const lastMessage = thread.messages[thread.messages.length - 1];
      if (lastMessage && lastMessage.type === "ai" && lastMessage.id) {
        setHistoricalActivities((prev) => ({
          ...prev,
          [lastMessage.id!]: [...processedEventsTimeline],
        }));
      }
      hasFinalizeEventOccurredRef.current = false;
    }
  }, [thread.messages, thread.isLoading, processedEventsTimeline]);

  // 将异步通道的事件汇入 ActivityTimeline（与 useStream 的 onUpdateEvent 逻辑一致）
  useEffect(() => {
    for (const event of researchStream.events) {
      let processedEvent: ProcessedEvent | null = null;
      if (event.generate_plan) {
        processedEvent = {
          title: "生成计划",
          data: event.generate_plan.plan || "No Plan to generate",
        };
        setAwaitingPlanConfirmation("confirmed");
        hasFinalizeEventOccurredRef.current = true;
      } else if (event.generate_query) {
        processedEvent = {
          title: "生成搜索查询",
          data: (event.generate_query as any)?.search_query?.join(", ") || "",
        };
      } else if (event.web_research) {
        const sources = (event.web_research as any)?.sources_gathered || [];
        const uniqueLabels = [
          ...new Set(sources.map((s: any) => s.label).filter(Boolean)),
        ];
        processedEvent = {
          title: "网络研究",
          data: `Gathered ${sources.length} sources. Related to: ${uniqueLabels.slice(0, 3).join(", ") || "N/A"}.`,
        };
      } else if (event.reflection) {
        processedEvent = {
          title: "反思和分析",
          data: "Analysing Web Research Results",
        };
      } else if (event.finalize_answer) {
        processedEvent = {
          title: "最终确定答案",
          data: "Composing and presenting the final answer.",
        };
        hasFinalizeEventOccurredRef.current = true;
      }
      if (processedEvent) {
        setProcessedEventsTimeline(prev => [...prev, processedEvent]);
      }
    }
  }, [researchStream.events]);

  const handleSubmit = useCallback(
    (submittedInputValue: string, effort: string, model: string) => {
      console.log('handleSubmit exectued.....', submittedInputValue, effort, model);
      if (!submittedInputValue.trim()) return;
      setProcessedEventsTimeline([]);
      hasFinalizeEventOccurredRef.current = false;

      // 保存 effort/model 以备后续使用
      if (effort) setSavedEffort(effort);
      if (model) setSavedModel(model);

      // 场景 1: 首次提交 → 走 task queue / SSE 通道
      if (thread.messages.length === 0 && researchStream.messages.length === 0) {
        researchStream.submit(submittedInputValue, effort, model);
        return;
      }

      // 场景 2: Plan 确认（用户点击"需求确认"或输入"需求确认"）→ 传递 "confirmed" 让后端进入研究
      if (researchStream.messages.length > 0
          && (submittedInputValue.includes("需求确认") || submittedInputValue.includes("开始研究"))
          && researchStream.messages.some(m => m.type === "ai")) {
        const lastAiMsg = [...researchStream.messages].reverse().find(m => m.type === "ai");
        const planContent = lastAiMsg?.content || "";
        researchStream.submit(submittedInputValue, savedEffort, savedModel, {
          plan: planContent,
          planStatus: "confirmed",
        });
        return;
      }

      // 场景 3: 后续追问/需求补充 → 传递已有 plan + confirmed，跳过 generate_plan，进入 confirm_plan 评估
      if (researchStream.messages.length > 0) {
        const lastAiMsg = [...researchStream.messages].reverse().find(m => m.type === "ai");
        const planContent = lastAiMsg?.content || "";
        researchStream.submit(submittedInputValue, savedEffort, savedModel, {
          plan: planContent,
          planStatus: "confirmed",
        });
        return;
      }

      // 场景 4: thread 通道的后续对话（已废弃，保留作为 fallback）
      let initial_search_query_count = 0;
      let max_research_loops = 0;
      switch (savedEffort) {
        case "low":
          initial_search_query_count = 1;
          max_research_loops = 1;
          break;
        case "medium":
          initial_search_query_count = 3;
          max_research_loops = 3;
          break;
        case "high":
          initial_search_query_count = 5;
          max_research_loops = 10;
          break;
      }

      const newMessages: Message[] = [
        ...(thread.messages || []),
        {
          type: "human",
          content: submittedInputValue,
          id: Date.now().toString(),
        },
      ];
      console.log('handleSubmit submit:', newMessages);
      thread.submit({
        messages: newMessages,
        initial_search_query_count: initial_search_query_count,
        max_research_loops: max_research_loops,
        reasoning_model: savedModel,
        plan_status: awaitingPlanConfirmation,
      } as any);
    },
    [thread, researchStream, savedEffort, savedModel, awaitingPlanConfirmation]
  );

  const handleCancel = useCallback(() => {
    thread.stop();
    window.location.reload();
  }, [thread]);

  return (
    <div className="flex h-screen bg-neutral-800 text-neutral-100 font-sans antialiased">
      <main className="h-full w-full max-w-4xl mx-auto">
          {thread.messages.length === 0 && researchStream.messages.length === 0 ? (
            <WelcomeScreen
              handleSubmit={handleSubmit}
              isLoading={thread.isLoading}
              onCancel={handleCancel}
            />
          ) : thread.messages.length > 0 ? (
            error ? (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="flex flex-col items-center justify-center gap-4">
                  <h1 className="text-2xl text-red-400 font-bold">错误：</h1>
                  <p className="text-red-400">{JSON.stringify(error)}</p>
                  <Button
                    variant="destructive"
                    onClick={() => window.location.reload()}
                  >
                    重试，或请联系你的系统管理员
                  </Button>
                </div>
              </div>
            ) : (
              <ChatMessagesView
                messages={thread.messages}
                isLoading={thread.isLoading}
                scrollAreaRef={scrollAreaRef}
                onSubmit={handleSubmit}
                onCancel={handleCancel}
                liveActivityEvents={processedEventsTimeline}
                historicalActivities={historicalActivities}
              />
            )
          ) : (
            // researchStream 通道显示（首次 plan 生成 + plan 确认后的后续流程）
            <ResearchStreamChatView
              messages={researchStream.messages}
              isLoading={researchStream.isLoading}
              liveActivityEvents={processedEventsTimeline}
              streamingNode={researchStream.streamingNode}
              streamingContent={researchStream.streamingContent}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              scrollAreaRef={scrollAreaRef}
            />
          )}
      </main>
    </div>
  );
}
